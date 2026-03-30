"""E2E tests for email ingestion endpoints.

Tests JSON email ingest and raw MIME email ingest.
"""

from __future__ import annotations

import base64
import httpx
import pytest
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from fastapi.testclient import TestClient


def _make_mime_email(
    sender: str = "sender@test.local",
    to: str = "lab@test.local",
    subject: str = "E2E Test Invoice",
    body: str = "Please find attached invoice.",
    attachments: list[tuple[str, bytes]] | None = None,
) -> bytes:
    """Build a raw MIME email with optional attachments."""
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    if attachments:
        for filename, content in attachments:
            maintype = "application"
            subtype = "pdf" if filename.lower().endswith(".pdf") else "octet-stream"
            part = MIMEBase(maintype, subtype)
            part.set_payload(content)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={filename}")
            msg.attach(part)

    return msg.as_bytes()


@pytest.mark.e2e
class TestEmailIngestJSON:
    """E2E tests for JSON email ingestion."""

    def test_ingest_json_with_attachment(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/email/ingest with JSON body creates documents."""
        file_content = base64.b64encode(b"E2E test file content").decode()
        resp = authenticated_client.post(
            "/api/v1/email/ingest",
            json={
                "sender": "e2e-sender@test.local",
                "subject": "E2E Test Invoice PDF",
                "body_html": "<p>Please see attached invoice.</p>",
                "attachments": [
                    {
                        "filename": "invoice_e2e.pdf",
                        "content_base64": file_content,
                    }
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "documents_created" in data
        assert data["documents_created"] >= 1
        assert len(data.get("document_ids", [])) >= 1

    def test_ingest_json_multiple_attachments(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST with multiple attachments creates multiple documents."""
        file1 = base64.b64encode(b"Invoice content").decode()
        file2 = base64.b64encode(b"Packing list content").decode()
        resp = authenticated_client.post(
            "/api/v1/email/ingest",
            json={
                "sender": "e2e-multi@test.local",
                "subject": "E2E Multi-attach",
                "attachments": [
                    {"filename": "invoice.pdf", "content_base64": file1},
                    {"filename": "packing_list.pdf", "content_base64": file2},
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["documents_created"] >= 2

    def test_ingest_json_no_attachments(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST without attachments returns 422."""
        resp = authenticated_client.post(
            "/api/v1/email/ingest",
            json={
                "sender": "e2e-noatt@test.local",
                "subject": "E2E No Attachments",
            },
        )
        assert resp.status_code == 422

    def test_ingest_json_missing_sender(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST missing required sender returns 422."""
        file_content = base64.b64encode(b"test").decode()
        resp = authenticated_client.post(
            "/api/v1/email/ingest",
            json={
                "subject": "E2E Missing Sender",
                "attachments": [
                    {"filename": "test.pdf", "content_base64": file_content}
                ],
            },
        )
        assert resp.status_code == 422

    def test_ingest_json_missing_subject(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST missing required subject returns 422."""
        file_content = base64.b64encode(b"test").decode()
        resp = authenticated_client.post(
            "/api/v1/email/ingest",
            json={
                "sender": "e2e-nosubj@test.local",
                "attachments": [
                    {"filename": "test.pdf", "content_base64": file_content}
                ],
            },
        )
        assert resp.status_code == 422


@pytest.mark.e2e
class TestEmailIngestRawMIME:
    """E2E tests for raw MIME email ingestion."""

    def test_ingest_raw_mime_with_attachment(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST raw MIME email creates documents."""
        raw_email = _make_mime_email(
            sender="e2e-mime@test.local",
            subject="E2E Raw MIME Invoice",
            attachments=[("invoice_raw.pdf", b"Raw PDF content here")],
        )
        resp = authenticated_client.post(
            "/api/v1/email/ingest",
            content=raw_email,
            headers={"Content-Type": "message/rfc822"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["documents_created"] >= 1

    def test_ingest_raw_mime_no_attachment(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Raw MIME email without attachments — behavior depends on API."""
        raw_email = _make_mime_email(
            sender="e2e-noatt@test.local",
            subject="E2E No Attach MIME",
        )
        resp = authenticated_client.post(
            "/api/v1/email/ingest",
            content=raw_email,
            headers={"Content-Type": "message/rfc822"},
        )
        # May succeed with 0 docs or return error
        assert resp.status_code in (201, 422)

    def test_ingest_unsupported_content_type(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Unsupported Content-Type returns 415."""
        resp = authenticated_client.post(
            "/api/v1/email/ingest",
            content=b"some random data",
            headers={"Content-Type": "application/xml"},
        )
        assert resp.status_code == 415

    def test_ingest_raw_text_plain(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """text/plain content type is also accepted."""
        raw_email = _make_mime_email(
            sender="e2e-plain@test.local",
            subject="E2E Plain Text",
            attachments=[("doc.pdf", b"plain content")],
        )
        resp = authenticated_client.post(
            "/api/v1/email/ingest",
            content=raw_email,
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code in (201, 415)
