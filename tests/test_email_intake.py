"""Tests for the email-to-intake pipeline.

Covers: parse_email, extract_attachments, process_email, JSON API, raw MIME API.
"""

from __future__ import annotations

import base64
import os
import struct
import zlib
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import patch

import pytest

from lab_manager.config import get_settings
from lab_manager.models.document import DocumentStatus
from lab_manager.services.email_intake import (
    Attachment,
    ParsedEmail,
    extract_attachments,
    parse_email,
    process_email,
    process_email_json,
)


@pytest.fixture(autouse=True)
def _email_test_settings(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("ADMIN_SECRET_KEY", "test-secret-key-not-for-production")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-password-not-for-production")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _make_png() -> bytes:
    """Minimal valid 1x1 PNG."""

    def _chunk(ct: bytes, data: bytes) -> bytes:
        c = ct + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = zlib.compress(b"\x00\xff\xff\xff")
    idat = _chunk(b"IDAT", raw)
    iend = _chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _make_pdf() -> bytes:
    """Minimal valid PDF."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n183\n%%EOF\n"
    )


def _build_email_with_pdf(
    sender: str = "vendor@sigma.com",
    subject: str = "Your Order Shipped - PO-12345",
    body: str = "Your order has shipped. Please find packing list attached.",
    filename: str = "packing_list.pdf",
    attachment_data: bytes | None = None,
) -> str:
    """Build a MIME email with a PDF attachment."""
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = "pi@lab.edu"
    msg["Subject"] = subject
    msg["Date"] = "Mon, 24 Mar 2026 10:00:00 -0400"

    msg.attach(MIMEText(body, "plain"))

    data = attachment_data or _make_pdf()
    att = MIMEApplication(data, _subtype="pdf")
    att.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(att)

    return msg.as_string()


def _build_email_with_image(
    sender: str = "vendor@thermo.com",
    subject: str = "Shipment Confirmation",
    filename: str = "receipt.png",
) -> str:
    """Build a MIME email with a PNG image attachment."""
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = "pi@lab.edu"
    msg["Subject"] = subject

    msg.attach(MIMEText("See attached receipt image.", "plain"))

    png_data = _make_png()
    att = MIMEImage(png_data, _subtype="png")
    att.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(att)

    return msg.as_string()


def _build_email_no_attachments() -> str:
    """Build a MIME email with no attachments."""
    msg = MIMEMultipart()
    msg["From"] = "person@example.com"
    msg["To"] = "pi@lab.edu"
    msg["Subject"] = "Just a text email"
    msg.attach(MIMEText("No attachments here.", "plain"))
    return msg.as_string()


class TestParseEmail:
    """Test parse_email() with various MIME structures."""

    def test_parse_simple_email_with_pdf(self):
        """Parse email with PDF attachment extracts sender, subject, body, and attachment."""
        raw = _build_email_with_pdf()
        parsed = parse_email(raw)

        assert parsed.sender == "vendor@sigma.com"
        assert parsed.subject == "Your Order Shipped - PO-12345"
        assert "order has shipped" in parsed.body_text
        assert parsed.date is not None
        assert len(parsed.attachments) == 1
        assert parsed.attachments[0].filename == "packing_list.pdf"
        assert parsed.attachments[0].content_type == "application/pdf"

    def test_parse_email_with_image(self):
        """Parse email with PNG image attachment."""
        raw = _build_email_with_image()
        parsed = parse_email(raw)

        assert parsed.sender == "vendor@thermo.com"
        assert parsed.subject == "Shipment Confirmation"
        assert len(parsed.attachments) == 1
        assert parsed.attachments[0].filename == "receipt.png"
        assert parsed.attachments[0].content_type == "image/png"
        assert parsed.attachments[0].data == _make_png()

    def test_parse_email_no_attachments(self):
        """Parse plain text email with no attachments."""
        raw = _build_email_no_attachments()
        parsed = parse_email(raw)

        assert parsed.sender == "person@example.com"
        assert parsed.subject == "Just a text email"
        assert "No attachments" in parsed.body_text
        assert len(parsed.attachments) == 0

    def test_parse_email_html_body(self):
        """Parse email with HTML body content."""
        msg = MIMEMultipart("alternative")
        msg["From"] = "vendor@example.com"
        msg["Subject"] = "HTML Email"
        msg.attach(MIMEText("Plain text version", "plain"))
        msg.attach(MIMEText("<h1>HTML version</h1>", "html"))

        parsed = parse_email(msg.as_string())
        assert parsed.body_text == "Plain text version"
        assert "<h1>HTML version</h1>" in parsed.body_html


class TestExtractAttachments:
    """Test extract_attachments() filtering."""

    def test_filters_supported_types(self):
        """Only PDF and image attachments pass the filter."""
        parsed = ParsedEmail(
            sender="test@example.com",
            subject="Test",
            date=None,
            body_text="",
            body_html="",
            attachments=[
                Attachment(
                    filename="doc.pdf", content_type="application/pdf", data=b"pdf"
                ),
                Attachment(filename="photo.png", content_type="image/png", data=b"png"),
                Attachment(filename="data.csv", content_type="text/csv", data=b"csv"),
                Attachment(
                    filename="archive.zip",
                    content_type="application/zip",
                    data=b"zip",
                ),
            ],
        )

        supported = extract_attachments(parsed)
        assert len(supported) == 2
        filenames = {a.filename for a in supported}
        assert filenames == {"doc.pdf", "photo.png"}

    def test_empty_attachments(self):
        """No attachments returns empty list."""
        parsed = ParsedEmail(
            sender="test@example.com",
            subject="Test",
            date=None,
            body_text="",
            body_html="",
            attachments=[],
        )

        assert extract_attachments(parsed) == []


class TestProcessEmail:
    """Test process_email() end-to-end pipeline."""

    def test_process_email_creates_documents(self, db_session, tmp_path):
        """Process email with PDF attachment creates Document record."""
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        os.environ["UPLOAD_DIR"] = str(upload_dir)
        get_settings.cache_clear()

        raw = _build_email_with_pdf()
        docs = process_email(raw, db_session)

        assert len(docs) == 1
        doc = docs[0]
        assert doc.id is not None
        assert doc.status == DocumentStatus.processing
        assert "Email intake" in doc.review_notes
        assert "vendor@sigma.com" in doc.review_notes
        assert doc.extracted_data["source"] == "email"
        assert doc.extracted_data["email_from"] == "vendor@sigma.com"
        assert doc.extracted_data["email_subject"] == "Your Order Shipped - PO-12345"

        # File was saved to disk
        from pathlib import Path

        assert Path(doc.file_path).exists()

        get_settings.cache_clear()

    def test_process_email_no_supported_attachments(self, db_session, tmp_path):
        """Email with no supported attachments creates zero documents."""
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        os.environ["UPLOAD_DIR"] = str(upload_dir)
        get_settings.cache_clear()

        raw = _build_email_no_attachments()
        docs = process_email(raw, db_session)

        assert len(docs) == 0

        get_settings.cache_clear()

    def test_process_email_multiple_attachments(self, db_session, tmp_path):
        """Email with multiple supported attachments creates one Document per attachment."""
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        os.environ["UPLOAD_DIR"] = str(upload_dir)
        get_settings.cache_clear()

        # Build email with PDF + image
        msg = MIMEMultipart()
        msg["From"] = "vendor@bio-rad.com"
        msg["To"] = "pi@lab.edu"
        msg["Subject"] = "Order Documents"
        msg.attach(MIMEText("Multiple documents attached.", "plain"))

        pdf_att = MIMEApplication(_make_pdf(), _subtype="pdf")
        pdf_att.add_header("Content-Disposition", "attachment", filename="invoice.pdf")
        msg.attach(pdf_att)

        img_att = MIMEImage(_make_png(), _subtype="png")
        img_att.add_header("Content-Disposition", "attachment", filename="label.png")
        msg.attach(img_att)

        raw = msg.as_string()
        docs = process_email(raw, db_session)

        assert len(docs) == 2
        filenames = {d.file_name for d in docs}
        assert any("invoice" in f for f in filenames)
        assert any("label" in f for f in filenames)

        get_settings.cache_clear()


class TestProcessEmailJson:
    """Test process_email_json() with base64 attachments."""

    def test_json_with_pdf(self, db_session, tmp_path):
        """JSON email with base64 PDF creates Document."""
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        os.environ["UPLOAD_DIR"] = str(upload_dir)
        get_settings.cache_clear()

        pdf_data = _make_pdf()
        pdf_b64 = base64.b64encode(pdf_data).decode()

        docs = process_email_json(
            sender="vendor@fisher.com",
            subject="Invoice #INV-2026-001",
            body_html="<p>Invoice attached</p>",
            attachments_b64=[
                {"filename": "invoice.pdf", "content_base64": pdf_b64},
            ],
            db=db_session,
        )

        assert len(docs) == 1
        doc = docs[0]
        assert doc.status == DocumentStatus.processing
        assert "vendor@fisher.com" in doc.review_notes
        assert doc.extracted_data["source"] == "email"

        get_settings.cache_clear()

    def test_json_unsupported_extension_skipped(self, db_session, tmp_path):
        """JSON email with unsupported file extension creates no documents."""
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        os.environ["UPLOAD_DIR"] = str(upload_dir)
        get_settings.cache_clear()

        docs = process_email_json(
            sender="vendor@example.com",
            subject="Spreadsheet",
            body_html="",
            attachments_b64=[
                {
                    "filename": "data.xlsx",
                    "content_base64": base64.b64encode(b"xlsx data").decode(),
                },
            ],
            db=db_session,
        )

        assert len(docs) == 0

        get_settings.cache_clear()

    def test_json_invalid_base64_skipped(self, db_session, tmp_path):
        """Invalid base64 content is skipped without crashing."""
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        os.environ["UPLOAD_DIR"] = str(upload_dir)
        get_settings.cache_clear()

        docs = process_email_json(
            sender="vendor@example.com",
            subject="Bad attachment",
            body_html="",
            attachments_b64=[
                {"filename": "doc.pdf", "content_base64": "not-valid-base64!!!"},
            ],
            db=db_session,
        )

        assert len(docs) == 0

        get_settings.cache_clear()


class TestEmailIngestAPI:
    """Test POST /api/v1/email/ingest endpoint."""

    @pytest.fixture
    def upload_dir(self, tmp_path):
        d = tmp_path / "uploads"
        d.mkdir()
        os.environ["UPLOAD_DIR"] = str(d)
        get_settings.cache_clear()
        yield d
        get_settings.cache_clear()

    @pytest.fixture
    def email_client(self, upload_dir, db_session):
        os.environ["AUTH_ENABLED"] = "false"
        get_settings.cache_clear()

        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db

        app = create_app()

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        from fastapi.testclient import TestClient

        with TestClient(app) as c:
            yield c

    @patch("lab_manager.api.routes.email_ingest._trigger_extraction")
    def test_json_ingest_creates_documents(self, mock_extract, email_client):
        """JSON email ingest creates documents and returns IDs."""
        pdf_b64 = base64.b64encode(_make_pdf()).decode()
        resp = email_client.post(
            "/api/v1/email/ingest",
            json={
                "sender": "vendor@sigma.com",
                "subject": "PO-12345 Shipped",
                "body_html": "<p>Shipped</p>",
                "attachments": [
                    {"filename": "packing_list.pdf", "content_base64": pdf_b64},
                ],
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["documents_created"] == 1
        assert len(data["document_ids"]) == 1
        mock_extract.assert_called_once()

    @patch("lab_manager.api.routes.email_ingest._trigger_extraction")
    def test_raw_mime_ingest(self, mock_extract, email_client):
        """Raw MIME email ingest creates documents."""
        raw = _build_email_with_pdf()
        resp = email_client.post(
            "/api/v1/email/ingest",
            content=raw.encode("utf-8"),
            headers={"Content-Type": "message/rfc822"},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["documents_created"] == 1
        assert len(data["document_ids"]) == 1

    def test_unsupported_content_type(self, email_client):
        """Unsupported Content-Type returns 415."""
        resp = email_client.post(
            "/api/v1/email/ingest",
            content=b"<xml>not email</xml>",
            headers={"Content-Type": "application/xml"},
        )

        assert resp.status_code == 415

    def test_json_no_attachments_returns_422(self, email_client):
        """JSON email with no attachments returns 422."""
        resp = email_client.post(
            "/api/v1/email/ingest",
            json={
                "sender": "vendor@example.com",
                "subject": "No docs",
                "attachments": [],
            },
        )

        assert resp.status_code == 422


class TestEmailPoller:
    """Test email_poller module."""

    def test_poll_once_not_configured(self):
        """poll_once returns 0 when IMAP not configured."""
        os.environ.pop("EMAIL_IMAP_HOST", None)
        os.environ.pop("EMAIL_IMAP_USER", None)

        from lab_manager.services.email_poller import poll_once

        result = poll_once()
        assert result == 0

    def test_poll_once_with_mock_imap(self, db_session, tmp_path):
        """poll_once processes emails from mocked IMAP connection."""
        from contextlib import contextmanager

        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        os.environ["UPLOAD_DIR"] = str(upload_dir)
        os.environ["EMAIL_IMAP_HOST"] = "imap.example.com"
        os.environ["EMAIL_IMAP_USER"] = "lab@example.com"
        os.environ["EMAIL_IMAP_PASSWORD"] = "secret"
        get_settings.cache_clear()

        raw_email_str = _build_email_with_pdf()

        mock_conn = type(
            "MockIMAP",
            (),
            {
                "login": lambda self, u, p: None,
                "select": lambda self, f: ("OK", [b"1"]),
                "search": lambda self, charset, criteria: ("OK", [b"1"]),
                "fetch": lambda self, num, parts: (
                    "OK",
                    [(b"1 (RFC822 {1234})", raw_email_str.encode("utf-8"))],
                ),
                "logout": lambda self: None,
            },
        )()

        @contextmanager
        def fake_db_session():
            yield db_session

        with (
            patch(
                "lab_manager.services.email_poller._connect_imap",
                return_value=mock_conn,
            ),
            patch(
                "lab_manager.database.get_db_session",
                side_effect=fake_db_session,
            ),
            patch("lab_manager.api.routes.documents._run_extraction") as mock_extract,
        ):
            from lab_manager.services.email_poller import poll_once

            result = poll_once()

        assert result == 1
        mock_extract.assert_called_once()

        # Clean up env
        os.environ.pop("EMAIL_IMAP_HOST", None)
        os.environ.pop("EMAIL_IMAP_USER", None)
        os.environ.pop("EMAIL_IMAP_PASSWORD", None)
        get_settings.cache_clear()
