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
        """POST /api/v1/documents/upload rejects empty file with 400."""
        resp = authenticated_client.post(
            "/api/v1/documents/upload",
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert resp.status_code == 400, (
            f"Expected 400 for empty file, got {resp.status_code}"
        )

    def test_upload_invalid_mime_type(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/documents/upload rejects executable with 400."""
        resp = authenticated_client.post(
            "/api/v1/documents/upload",
            files={
                "file": ("test.exe", b"invalid content", "application/octet-stream")
            },
        )
        assert resp.status_code == 400, (
            f"Expected 400 for invalid MIME, got {resp.status_code}"
        )

    def test_upload_missing_file(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/documents/upload returns 422 without file."""
        resp = authenticated_client.post("/api/v1/documents/upload")
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_upload_very_large_filename(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/documents/upload rejects very long filename with 400."""
        long_name = "a" * 200 + ".txt"  # Very long filename exceeds limit
        resp = authenticated_client.post(
            "/api/v1/documents/upload",
            files={"file": (long_name, b"test content", "text/plain")},
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"


@pytest.mark.e2e
class TestDocumentCRUDEdgeCases:
    """Tests for document CRUD edge cases."""

    def test_update_nonexistent_document(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """PATCH /api/v1/documents/{id} returns 422 for non-existent."""
        resp = authenticated_client.patch(
            "/api/v1/documents/999999",
            json={"status": "reviewed"},
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_delete_nonexistent_document(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """DELETE /api/v1/documents/{id} returns 404 for non-existent."""
        resp = authenticated_client.delete("/api/v1/documents/999999")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"

    def test_get_nonexistent_document(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/documents/{id} returns 404 for non-existent."""
        resp = authenticated_client.get("/api/v1/documents/999999")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"


@pytest.mark.e2e
class TestDocumentReview:
    """Tests for document review workflow."""

    def test_review_nonexistent_document(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/documents/{id}/review rejects missing documents."""
        resp = authenticated_client.post(
            "/api/v1/documents/999999/review",
            json={"action": "approve"},
        )
        assert resp.status_code in (404, 422), (
            f"Expected 404 or 422, got {resp.status_code}"
        )

    def test_review_with_extracted_data(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/documents/{id}/review with extracted data succeeds."""
        # Create document first
        create_resp = authenticated_client.post(
            "/api/v1/documents/",
            json={
                "file_path": "/tmp/review-test.txt",
                "file_name": "review-test.txt",
                "document_type": "packing_list",
                "status": "needs_review",
                "extracted_data": {
                    "vendor_name": "Test Vendor",
                    "items": [{"name": "Item 1", "quantity": 10}],
                },
            },
        )
        assert create_resp.status_code == 201, (
            f"Expected 201, got {create_resp.status_code}"
        )
        doc_id = create_resp.json()["id"]

        resp = authenticated_client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={
                "action": "approve",
                "reviewed_by": "e2e-reviewer",
            },
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_review_invalid_status(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/documents/{id}/review rejects invalid action with 422."""
        # Create document first
        create_resp = authenticated_client.post(
            "/api/v1/documents/",
            json={
                "file_path": "/tmp/review-invalid.txt",
                "file_name": "review-invalid.txt",
                "document_type": "packing_list",
                "status": "needs_review",
            },
        )
        assert create_resp.status_code == 201, (
            f"Expected 201, got {create_resp.status_code}"
        )
        doc_id = create_resp.json()["id"]

        resp = authenticated_client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"action": "invalid_status_xyz"},
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"


@pytest.mark.e2e
class TestDocumentFiltering:
    """Tests for document filtering."""

    def test_filter_by_status(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/documents/ filters by status."""
        resp = authenticated_client.get(
            "/api/v1/documents/", params={"status": "pending"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "pending", (
                f"Expected status=pending, got {item['status']}"
            )

    def test_filter_by_type(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/documents/ filters by document type."""
        resp = authenticated_client.get(
            "/api/v1/documents/", params={"document_type": "invoice"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        for item in data["items"]:
            assert item["document_type"] == "invoice", (
                f"Expected document_type=invoice, got {item['document_type']}"
            )


@pytest.mark.e2e
class TestDocumentStats:
    """Tests for document statistics."""

    def test_stats_endpoint(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/documents/stats returns stats."""
        resp = authenticated_client.get("/api/v1/documents/stats")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"


@pytest.mark.e2e
class TestDocumentUploadFormats:
    """Tests for different document upload formats."""

    def test_upload_pdf(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/documents/upload accepts PDF with 201."""
        pdf_content = b"%PDF-1.4\n%fake pdf content"
        resp = authenticated_client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.pdf", pdf_content, "application/pdf")},
        )
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"

    def test_upload_jpeg(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/documents/upload accepts JPEG with 201."""
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
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"


@pytest.mark.e2e
class TestDocumentPagination:
    """Tests for document pagination."""

    def test_pagination_default(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/documents/ returns paginated results."""
        resp = authenticated_client.get("/api/v1/documents/")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "items" in data, f"Response missing 'items': {data.keys()}"
        assert "total" in data, f"Response missing 'total': {data.keys()}"

    def test_pagination_custom_size(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/documents/ respects page_size."""
        resp = authenticated_client.get("/api/v1/documents/", params={"page_size": 10})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert len(data["items"]) <= 10, (
            f"Expected <=10 items, got {len(data['items'])}"
        )

    def test_pagination_second_page(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/documents/ returns correct page."""
        resp = authenticated_client.get(
            "/api/v1/documents/", params={"page": 2, "page_size": 5}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["page"] == 2, f"Expected page=2, got {data['page']}"
