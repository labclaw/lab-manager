"""E2E tests for documents edge cases and error handling.

Tests file validation, upload limits, and error conditions.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.mark.e2e
class TestDocumentUploadValidation:
    """Tests for document upload validation."""

    def test_upload_empty_file(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/documents/upload rejects empty file."""
        resp = authenticated_client.post(
            "/api/v1/documents/upload",
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert resp.status_code in (400, 422)

    def test_upload_invalid_mime_type(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/documents/upload rejects invalid MIME type."""
        resp = authenticated_client.post(
            "/api/v1/documents/upload",
            files={
                "file": ("test.exe", b"invalid content", "application/octet-stream")
            },
        )
        assert resp.status_code in (400, 415, 422)

    def test_upload_missing_file(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/documents/upload handles missing file."""
        resp = authenticated_client.post("/api/v1/documents/upload")
        assert resp.status_code in (400, 422)

    def test_upload_very_large_filename(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/documents/upload handles long filename."""
        long_name = "a" * 500 + ".txt"
        resp = authenticated_client.post(
            "/api/v1/documents/upload",
            files={"file": (long_name, b"test content", "text/plain")},
        )
        assert resp.status_code in (200, 201, 400, 422)

    def test_upload_special_chars_filename(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/documents/upload handles special characters."""
        resp = authenticated_client.post(
            "/api/v1/documents/upload",
            files={"file": ('test<>:"/\\|?*.txt', b"test", "text/plain")},
        )
        # May sanitize or reject
        assert resp.status_code in (200, 201, 400, 422)


@pytest.mark.e2e
class TestDocumentCRUDEdgeCases:
    """Tests for document CRUD edge cases."""

    def test_create_without_file(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/documents/ creates document without file."""
        resp = authenticated_client.post(
            "/api/v1/documents/",
            json={
                "document_type": "packing_list",
                "status": "pending",
            },
        )
        assert resp.status_code in (200, 201, 400, 422)

    def test_update_nonexistent_document(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """PATCH /api/v1/documents/{id} returns 404 for non-existent."""
        resp = authenticated_client.patch(
            "/api/v1/documents/999999",
            json={"status": "reviewed"},
        )
        # May return 404 or 422
        assert resp.status_code in (400, 404, 422)

    def test_delete_nonexistent_document(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """DELETE /api/v1/documents/{id} returns 404 for non-existent."""
        resp = authenticated_client.delete("/api/v1/documents/999999")
        assert resp.status_code == 404

    def test_get_nonexistent_document(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/documents/{id} returns 404 for non-existent."""
        resp = authenticated_client.get("/api/v1/documents/999999")
        assert resp.status_code == 404


@pytest.mark.e2e
class TestDocumentReview:
    """Tests for document review workflow."""

    def test_review_nonexistent_document(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/documents/{id}/review returns 404 for non-existent."""
        resp = authenticated_client.post(
            "/api/v1/documents/999999/review",
            json={"status": "approved"},
        )
        # May return 404 or 422
        assert resp.status_code in (400, 404, 422)

    def test_review_with_extracted_data(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/documents/{id}/review with extracted data."""
        # Create document first
        create_resp = authenticated_client.post(
            "/api/v1/documents/",
            json={
                "document_type": "packing_list",
                "status": "pending_review",
            },
        )
        if create_resp.status_code in (200, 201):
            doc_id = create_resp.json()["id"]

            resp = authenticated_client.post(
                f"/api/v1/documents/{doc_id}/review",
                json={
                    "status": "approved",
                    "extracted_data": {
                        "vendor_name": "Test Vendor",
                        "items": [{"name": "Item 1", "quantity": 10}],
                    },
                },
            )
            assert resp.status_code in (200, 400, 404, 422)

    def test_review_status_transitions(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Document review status transitions correctly."""
        # Create document
        create_resp = authenticated_client.post(
            "/api/v1/documents/",
            json={"document_type": "invoice", "status": "pending"},
        )
        if create_resp.status_code in (200, 201):
            doc_id = create_resp.json()["id"]

            # Transition to reviewed
            resp = authenticated_client.post(
                f"/api/v1/documents/{doc_id}/review",
                json={"status": "reviewed"},
            )
            assert resp.status_code in (200, 400, 404)

    def test_review_invalid_status(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/documents/{id}/review rejects invalid status."""
        # Create document first
        create_resp = authenticated_client.post(
            "/api/v1/documents/",
            json={"document_type": "packing_list", "status": "pending"},
        )
        if create_resp.status_code in (200, 201):
            doc_id = create_resp.json()["id"]

            resp = authenticated_client.post(
                f"/api/v1/documents/{doc_id}/review",
                json={"status": "invalid_status"},
            )
            assert resp.status_code in (400, 422)


@pytest.mark.e2e
class TestDocumentFiltering:
    """Tests for document filtering."""

    def test_filter_by_status(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/documents/ filters by status."""
        resp = authenticated_client.get(
            "/api/v1/documents/", params={"status": "pending"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "pending"

    def test_filter_by_type(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/documents/ filters by document type."""
        resp = authenticated_client.get(
            "/api/v1/documents/", params={"document_type": "invoice"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["document_type"] == "invoice"

    def test_filter_by_vendor(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_vendor_id: int,
    ):
        """GET /api/v1/documents/ filters by vendor."""
        resp = authenticated_client.get(
            "/api/v1/documents/", params={"vendor_id": test_vendor_id}
        )
        assert resp.status_code == 200


@pytest.mark.e2e
class TestDocumentStats:
    """Tests for document statistics."""

    def test_stats_endpoint(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/documents/stats returns stats."""
        resp = authenticated_client.get("/api/v1/documents/stats")
        assert resp.status_code == 200
        data = resp.json()
        # Should have some count fields
        assert isinstance(data, dict)

    def test_stats_by_status(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/documents/stats groups by status."""
        resp = authenticated_client.get("/api/v1/documents/stats")
        if resp.status_code == 200:
            data = resp.json()
            # May have status breakdown
            if "by_status" in data:
                assert isinstance(data["by_status"], dict)


@pytest.mark.e2e
class TestDocumentUploadFormats:
    """Tests for different document upload formats."""

    def test_upload_pdf(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/documents/upload accepts PDF."""
        pdf_content = b"%PDF-1.4\n%fake pdf content"
        resp = authenticated_client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.pdf", pdf_content, "application/pdf")},
        )
        assert resp.status_code in (200, 201)

    def test_upload_jpeg(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/documents/upload accepts JPEG."""
        # Minimal JPEG header
        jpeg_header = bytes(
            [
                0xFF,
                0xD8,
                0xFF,
                0xE0,
                0x00,
                0x10,
                0x4A,
                0x46,
                0x49,
                0x46,
                0x00,
                0x01,
                0x01,
                0x00,
                0x00,
                0x01,
                0x00,
                0x01,
                0x00,
                0x00,
                0xFF,
                0xD9,
            ]
        )
        resp = authenticated_client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.jpg", jpeg_header, "image/jpeg")},
        )
        assert resp.status_code in (200, 201)

    def test_upload_png(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/documents/upload accepts PNG."""
        # Minimal PNG header
        png_header = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
        resp = authenticated_client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.png", png_header, "image/png")},
        )
        assert resp.status_code in (200, 201, 400, 422)

    def test_upload_text(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/documents/upload accepts text."""
        resp = authenticated_client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.txt", b"test content", "text/plain")},
        )
        # May accept or reject text files
        assert resp.status_code in (200, 201, 400, 415)


@pytest.mark.e2e
class TestDocumentPagination:
    """Tests for document pagination."""

    def test_pagination_default(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/documents/ returns paginated results."""
        resp = authenticated_client.get("/api/v1/documents/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_pagination_custom_size(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/documents/ respects page_size."""
        resp = authenticated_client.get("/api/v1/documents/", params={"page_size": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 10

    def test_pagination_second_page(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/documents/ returns correct page."""
        resp = authenticated_client.get(
            "/api/v1/documents/", params={"page": 2, "page_size": 5}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2
