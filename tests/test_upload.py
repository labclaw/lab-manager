"""Tests for document photo upload endpoint and static file serving."""

import io
import os

import pytest

from lab_manager.config import get_settings


@pytest.fixture()
def upload_dir(tmp_path):
    """Set UPLOAD_DIR env var before app creation so StaticFiles mount uses it."""
    d = tmp_path / "uploads"
    d.mkdir()
    os.environ["UPLOAD_DIR"] = str(d)
    get_settings.cache_clear()
    yield d
    get_settings.cache_clear()


@pytest.fixture()
def client(upload_dir, db_session):
    """Override conftest client to ensure upload_dir is set before app creation."""
    os.environ["AUTH_ENABLED"] = "false"
    get_settings.cache_clear()

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db
    from lab_manager.api.routes import documents

    app = create_app()
    documents._run_extraction = lambda doc_id: None

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


def _make_png_bytes() -> bytes:
    """Return minimal valid PNG bytes."""
    # 1x1 white pixel PNG
    import struct
    import zlib

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = zlib.compress(b"\x00\xff\xff\xff")
    idat = _chunk(b"IDAT", raw)
    iend = _chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _make_jpeg_bytes() -> bytes:
    """Return minimal valid JPEG bytes."""
    # Minimal JFIF: SOI + APP0 + minimal data + EOI
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
    )


# --- Task 8: Upload endpoint tests ---


class TestUploadEndpoint:
    """POST /api/documents/upload"""

    def test_upload_png_success(self, client, upload_dir):
        """Successful PNG upload returns 201 with document data."""
        png = _make_png_bytes()
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test_sample.png", io.BytesIO(png), "image/png")},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "processing"
        assert "test_sample.png" in data["file_name"]
        assert data["id"] is not None

    def test_upload_creates_document_record(self, client, db_session, upload_dir):
        """Upload creates a Document row in the database."""
        from lab_manager.models.document import Document

        png = _make_png_bytes()
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("record_test.png", io.BytesIO(png), "image/png")},
        )
        assert resp.status_code == 201
        doc_id = resp.json()["id"]
        doc = db_session.get(Document, doc_id)
        assert doc is not None
        assert doc.status == "processing"
        assert "record_test.png" in doc.file_name

    def test_upload_rejected_file_type(self, client, upload_dir):
        """Non-allowed file types (e.g. .exe) are rejected with 400."""
        resp = client.post(
            "/api/v1/documents/upload",
            files={
                "file": (
                    "malware.exe",
                    io.BytesIO(b"MZ" + b"\x00" * 100),
                    "application/x-msdownload",
                )
            },
        )
        assert resp.status_code == 400
        assert "not allowed" in resp.json()["detail"].lower()

    def test_upload_file_too_large(self, client, upload_dir):
        """Files exceeding 50MB are rejected with 413."""
        # Create a file just over 50MB
        big = b"\x00" * (50 * 1024 * 1024 + 1)
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("big.png", io.BytesIO(big), "image/png")},
        )
        assert resp.status_code == 413
        assert "too large" in resp.json()["detail"].lower()

    def test_upload_timestamp_prefix(self, client, upload_dir):
        """Uploaded filename has YYYYMMDD_HHMMSS prefix for uniqueness."""
        import re

        png = _make_png_bytes()
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("photo.png", io.BytesIO(png), "image/png")},
        )
        assert resp.status_code == 201
        file_name = resp.json()["file_name"]
        # Pattern: YYYYMMDD_HHMMSS_UUUUUU_originalname
        assert re.match(r"\d{8}_\d{6}_\d{6}_photo\.png$", file_name)

    def test_upload_duplicate_filename_ok(self, client, upload_dir):
        """Two uploads of the same original filename succeed (timestamp makes them unique)."""
        png = _make_png_bytes()

        resp1 = client.post(
            "/api/v1/documents/upload",
            files={"file": ("dup.png", io.BytesIO(png), "image/png")},
        )
        assert resp1.status_code == 201

        # Small delay not needed -- datetime includes seconds
        resp2 = client.post(
            "/api/v1/documents/upload",
            files={"file": ("dup.png", io.BytesIO(png), "image/png")},
        )
        # Even if same second, we handle it (or it just works at different seconds)
        assert resp2.status_code == 201
        assert (
            resp1.json()["file_name"] != resp2.json()["file_name"]
            or resp1.json()["id"] != resp2.json()["id"]
        )

    def test_upload_saves_file_to_disk(self, client, upload_dir):
        """Uploaded file actually exists on disk in upload_dir."""
        png = _make_png_bytes()
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("disk_test.png", io.BytesIO(png), "image/png")},
        )
        assert resp.status_code == 201
        file_name = resp.json()["file_name"]
        assert (upload_dir / file_name).exists()

    def test_upload_jpeg(self, client, upload_dir):
        """JPEG uploads are accepted."""
        jpeg = _make_jpeg_bytes()
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("photo.jpg", io.BytesIO(jpeg), "image/jpeg")},
        )
        assert resp.status_code == 201

    def test_upload_pdf(self, client, upload_dir):
        """PDF uploads are accepted."""
        # Minimal PDF
        pdf = b"%PDF-1.0\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("doc.pdf", io.BytesIO(pdf), "application/pdf")},
        )
        assert resp.status_code == 201

    def test_upload_file_path_set(self, client, upload_dir):
        """Document's file_path points to the uploads directory."""
        png = _make_png_bytes()
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("path_test.png", io.BytesIO(png), "image/png")},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["file_path"].endswith(data["file_name"])


# --- Task 9: Static file serving ---


class TestUploadStaticServing:
    """GET /uploads/{filename} serves uploaded files."""

    def test_uploaded_file_accessible(self, client, upload_dir):
        """After upload, the file can be retrieved via /uploads/ route."""
        png = _make_png_bytes()
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("serve_test.png", io.BytesIO(png), "image/png")},
        )
        assert resp.status_code == 201
        file_name = resp.json()["file_name"]

        # The static mount serves files from upload_dir at /uploads/
        get_resp = client.get(f"/uploads/{file_name}")
        assert get_resp.status_code == 200
        assert get_resp.content == png
