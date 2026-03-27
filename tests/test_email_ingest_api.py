"""Tests for email ingestion API endpoints."""

import base64

from email.message import EmailMessage
from fastapi.testclient import TestClient


def _b64(filename: str = "test.pdf", data: bytes = b"%PDF-fake") -> dict:
    return {"filename": filename, "content_base64": base64.b64encode(data).decode()}


class TestEmailIngestContentType:
    """Content-type routing."""

    def test_unsupported_content_type_returns_415(self, client: TestClient):
        r = client.post(
            "/api/v1/email/ingest",
            content=b"<xml/>",
            headers={"content-type": "application/xml"},
        )
        assert r.status_code == 415
        assert "Unsupported Content-Type" in r.json()["detail"]

    def test_multipart_form_returns_415(self, client: TestClient):
        r = client.post(
            "/api/v1/email/ingest",
            content=b"data",
            headers={"content-type": "multipart/form-data"},
        )
        assert r.status_code == 415


class TestEmailIngestJSON:
    """JSON email ingestion."""

    def test_no_attachments_returns_422(self, client: TestClient):
        r = client.post(
            "/api/v1/email/ingest",
            json={
                "sender": "a@b.com",
                "subject": "Test",
                "attachments": [],
            },
        )
        assert r.status_code == 422
        assert "No attachments" in r.json()["detail"]

    def test_invalid_payload_returns_422(self, client: TestClient):
        r = client.post(
            "/api/v1/email/ingest",
            json={"garbage": True},
        )
        assert r.status_code == 422

    def test_pdf_attachment_creates_document(self, client: TestClient):
        r = client.post(
            "/api/v1/email/ingest",
            json={
                "sender": "orders@vendor.com",
                "subject": "Invoice",
                "attachments": [_b64("invoice.pdf")],
            },
        )
        assert r.status_code == 201
        assert r.json()["documents_created"] >= 1

    def test_png_attachment_creates_document(self, client: TestClient):
        r = client.post(
            "/api/v1/email/ingest",
            json={
                "sender": "a@b.com",
                "subject": "Label",
                "attachments": [_b64("label.png", b"\x89PNG\r\n\x1a\n")],
            },
        )
        assert r.status_code == 201
        assert r.json()["documents_created"] >= 1

    def test_jpeg_attachment(self, client: TestClient):
        r = client.post(
            "/api/v1/email/ingest",
            json={
                "sender": "a@b.com",
                "subject": "Photo",
                "attachments": [_b64("photo.jpg", b"\xff\xd8\xff\xe0")],
            },
        )
        assert r.status_code == 201

    def test_unsupported_extension_returns_zero_docs(self, client: TestClient):
        r = client.post(
            "/api/v1/email/ingest",
            json={
                "sender": "a@b.com",
                "subject": "Doc",
                "attachments": [_b64("report.docx", b"PK\x03\x04")],
            },
        )
        assert r.status_code == 201
        assert r.json()["documents_created"] == 0

    def test_multiple_attachments(self, client: TestClient):
        r = client.post(
            "/api/v1/email/ingest",
            json={
                "sender": "a@b.com",
                "subject": "Multi",
                "attachments": [_b64("a.pdf"), _b64("b.png", b"\x89PNG")],
            },
        )
        assert r.status_code == 201
        assert r.json()["documents_created"] == 2

    def test_mixed_supported_unsupported(self, client: TestClient):
        r = client.post(
            "/api/v1/email/ingest",
            json={
                "sender": "a@b.com",
                "subject": "Mixed",
                "attachments": [_b64("good.pdf"), _b64("bad.docx", b"PK")],
            },
        )
        assert r.status_code == 201
        assert r.json()["documents_created"] == 1

    def test_bad_base64_returns_zero_docs(self, client: TestClient):
        r = client.post(
            "/api/v1/email/ingest",
            json={
                "sender": "a@b.com",
                "subject": "Bad",
                "attachments": [
                    {"filename": "bad.pdf", "content_base64": "!!!invalid!!!"},
                ],
            },
        )
        assert r.status_code == 201
        assert r.json()["documents_created"] == 0


class TestEmailIngestRaw:
    """Raw MIME email ingestion."""

    def _make_raw(self, has_pdf: bool = True) -> str:
        msg = EmailMessage()
        msg["From"] = "vendor@example.com"
        msg["Subject"] = "Test"
        msg["Date"] = "Thu, 27 Mar 2026 12:00:00 +0000"
        msg.set_content("See attached.")
        if has_pdf:
            msg.add_attachment(
                b"%PDF-fake",
                maintype="application",
                subtype="pdf",
                filename="inv.pdf",
            )
        return msg.as_string()

    def test_raw_with_attachment(self, client: TestClient):
        r = client.post(
            "/api/v1/email/ingest",
            content=self._make_raw(True),
            headers={"content-type": "message/rfc822"},
        )
        assert r.status_code == 201
        assert r.json()["documents_created"] >= 1

    def test_raw_no_attachment(self, client: TestClient):
        r = client.post(
            "/api/v1/email/ingest",
            content=self._make_raw(False),
            headers={"content-type": "message/rfc822"},
        )
        assert r.status_code == 201
        assert r.json()["documents_created"] == 0

    def test_raw_text_plain(self, client: TestClient):
        r = client.post(
            "/api/v1/email/ingest",
            content="From: t@t.com\nSubject: Hi\n\nBody",
            headers={"content-type": "text/plain"},
        )
        assert r.status_code == 201
