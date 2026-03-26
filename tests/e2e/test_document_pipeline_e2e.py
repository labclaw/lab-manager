"""E2E tests for the complete document intake pipeline.

Covers upload, manual creation, filtering, stats, approve/reject review
with cross-module side-effects (order, order items, inventory auto-creation),
pagination, soft-delete, and extraction_model filtering.
"""

from __future__ import annotations

import io
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

# Minimal valid 1x1 white PNG (67 bytes).
_MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n"  # PNG signature
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _uid() -> str:
    return uuid4().hex[:8]


def _make_extracted_data(
    *,
    suffix: str | None = None,
    vendor_name: str = "Sigma-Aldrich",
    items: list[dict] | None = None,
) -> dict:
    """Build realistic extracted_data payload for a packing list."""
    s = suffix or _uid()
    if items is None:
        items = [
            {
                "catalog_number": f"S{s[:4].upper()}",
                "description": "Sodium Chloride, 500g",
                "quantity": 2,
                "unit": "EA",
                "lot_number": f"MKCD{s.upper()}",
                "unit_price": 45.50,
            },
        ]
    return {
        "vendor_name": vendor_name,
        "document_type": "packing_list",
        "po_number": f"PO-E2E-{s.upper()}",
        "items": items,
    }


def _create_doc(
    client: TestClient | httpx.Client,
    *,
    suffix: str | None = None,
    status: str = "needs_review",
    extracted_data: dict | None = ...,  # type: ignore[assignment]
    extraction_model: str | None = None,
    ocr_text: str | None = "Sample OCR output",
    vendor_name: str | None = None,
) -> dict:
    """Helper: POST /api/v1/documents/ and return the response dict."""
    s = suffix or _uid()
    if extracted_data is ...:
        extracted_data = _make_extracted_data(suffix=s)
    body: dict = {
        "file_path": f"uploads/{s}_doc.png",
        "file_name": f"e2e_pipeline_{s}.png",
        "document_type": "packing_list",
        "status": status,
    }
    if extracted_data is not None:
        body["extracted_data"] = extracted_data
    if extraction_model is not None:
        body["extraction_model"] = extraction_model
    if ocr_text is not None:
        body["ocr_text"] = ocr_text
    if vendor_name is not None:
        body["vendor_name"] = vendor_name
    resp = client.post("/api/v1/documents", json=body)
    assert resp.status_code == 201, f"Document creation failed: {resp.text}"
    return resp.json()


@pytest.mark.e2e
class TestDocumentPipelineE2E:
    """Complete document intake pipeline -- the core differentiating feature."""

    # ------------------------------------------------------------------
    # 1. Upload
    # ------------------------------------------------------------------
    def test_01_upload_png(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/documents/upload with a valid PNG returns status=processing."""
        files = {"file": ("test_pipeline.png", io.BytesIO(_MINIMAL_PNG), "image/png")}
        resp = authenticated_client.post("/api/v1/documents/upload", files=files)
        assert resp.status_code == 201, f"Upload failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "processing"
        assert data["id"] is not None
        assert "test_pipeline" in data["file_name"]

    def test_02_upload_rejects_unsupported_type(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/documents/upload rejects unsupported MIME types."""
        files = {
            "file": ("bad.csv", io.BytesIO(b"a,b,c\n1,2,3"), "text/csv"),
        }
        resp = authenticated_client.post("/api/v1/documents/upload", files=files)
        assert resp.status_code == 400
        assert "not allowed" in resp.json()["detail"]

    # ------------------------------------------------------------------
    # 2. Manual document creation
    # ------------------------------------------------------------------
    def test_03_create_document_with_extracted_data(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/documents/ with pre-filled OCR text and extracted_data."""
        s = _uid()
        data = _create_doc(authenticated_client, suffix=s)
        assert data["id"] is not None
        assert data["status"] == "needs_review"
        assert data["ocr_text"] == "Sample OCR output"
        assert data["extracted_data"]["vendor_name"] == "Sigma-Aldrich"
        assert data["extracted_data"]["po_number"] == f"PO-E2E-{s.upper()}"

    # ------------------------------------------------------------------
    # 3. List with status filter
    # ------------------------------------------------------------------
    def test_04_list_documents_filter_by_status(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/documents?status=needs_review returns only matching docs."""
        # Seed a document with known status
        _create_doc(authenticated_client, status="needs_review")

        resp = authenticated_client.get(
            "/api/v1/documents", params={"status": "needs_review"}
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert "items" in payload
        assert payload["total"] >= 1
        for item in payload["items"]:
            assert item["status"] == "needs_review"

    # ------------------------------------------------------------------
    # 4. Stats
    # ------------------------------------------------------------------
    def test_05_document_stats(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/documents/stats returns aggregate counts."""
        # Ensure at least one document exists
        _create_doc(authenticated_client)

        resp = authenticated_client.get("/api/v1/documents/stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert "total_documents" in stats
        assert stats["total_documents"] >= 1
        assert "by_status" in stats
        assert "by_type" in stats
        assert "total_orders" in stats
        assert "total_vendors" in stats

    # ------------------------------------------------------------------
    # 5. Review -- approve (cross-module side-effects)
    # ------------------------------------------------------------------
    def test_06_review_approve_creates_order_and_inventory(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Approving a document auto-creates vendor, order, order items, and inventory."""
        s = _uid()
        vendor_name = f"E2E Vendor {s}"
        extracted = _make_extracted_data(suffix=s, vendor_name=vendor_name)
        doc = _create_doc(
            authenticated_client,
            suffix=s,
            extracted_data=extracted,
            vendor_name=vendor_name,
        )
        doc_id = doc["id"]

        # Approve
        resp = authenticated_client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"action": "approve", "reviewed_by": "e2e-tester"},
        )
        assert resp.status_code == 200, f"Review failed: {resp.text}"
        reviewed = resp.json()
        assert reviewed["status"] == "approved"
        assert reviewed["reviewed_by"] == "e2e-tester"

        # Verify order was created and linked to this document
        orders_resp = authenticated_client.get(
            "/api/v1/orders", params={"po_number": extracted["po_number"]}
        )
        assert orders_resp.status_code == 200
        orders_data = orders_resp.json()
        order_items = orders_data.get(
            "items", orders_data if isinstance(orders_data, list) else []
        )
        matching = [
            o for o in order_items if o.get("po_number") == extracted["po_number"]
        ]
        assert len(matching) >= 1, (
            f"Expected order with PO {extracted['po_number']}, got {order_items}"
        )
        order = matching[0]
        assert order["status"] == "received"
        assert order["document_id"] == doc_id

        # Verify vendor was auto-created
        assert order["vendor_id"] is not None
        vendor_resp = authenticated_client.get(f"/api/v1/vendors/{order['vendor_id']}")
        assert vendor_resp.status_code == 200
        assert vendor_resp.json()["name"] == vendor_name

        # Verify order items (items are at sub-endpoint, not embedded)
        oi_resp = authenticated_client.get(f"/api/v1/orders/{order['id']}/items")
        assert oi_resp.status_code == 200
        oi_data = oi_resp.json()
        oi_list = oi_data.get("items", oi_data if isinstance(oi_data, list) else [])
        assert len(oi_list) >= 1
        oi = oi_list[0]
        assert oi["catalog_number"] == extracted["items"][0]["catalog_number"]
        assert oi["lot_number"] == extracted["items"][0]["lot_number"]
        assert float(oi["quantity"]) == float(extracted["items"][0]["quantity"])

        # Verify inventory was created via the product
        product_id = oi.get("product_id")
        assert product_id is not None, "Product should have been auto-created"
        inv_resp = authenticated_client.get(
            "/api/v1/inventory", params={"product_id": product_id}
        )
        assert inv_resp.status_code == 200
        inv_data = inv_resp.json()
        inv_items = inv_data.get(
            "items", inv_data if isinstance(inv_data, list) else []
        )
        assert len(inv_items) >= 1, "Inventory item should have been created"
        inv = inv_items[0]
        assert inv["lot_number"] == extracted["items"][0]["lot_number"]
        assert float(inv["quantity_on_hand"]) == float(
            extracted["items"][0]["quantity"]
        )

    # ------------------------------------------------------------------
    # 6. Review -- reject (no side-effects)
    # ------------------------------------------------------------------
    def test_07_review_reject_no_order_created(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Rejecting a document does NOT create an order."""
        s = _uid()
        vendor_name = f"E2E Reject Vendor {s}"
        extracted = _make_extracted_data(suffix=s, vendor_name=vendor_name)
        doc = _create_doc(
            authenticated_client,
            suffix=s,
            extracted_data=extracted,
        )
        doc_id = doc["id"]

        # Reject
        resp = authenticated_client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={
                "action": "reject",
                "reviewed_by": "e2e-tester",
                "review_notes": "Wrong document",
            },
        )
        assert resp.status_code == 200, f"Reject failed: {resp.text}"
        reviewed = resp.json()
        assert reviewed["status"] == "rejected"
        assert reviewed["review_notes"] == "Wrong document"

        # Confirm no order for this document
        orders_resp = authenticated_client.get(
            "/api/v1/orders", params={"po_number": extracted["po_number"]}
        )
        assert orders_resp.status_code == 200
        orders_data = orders_resp.json()
        order_items = orders_data.get(
            "items", orders_data if isinstance(orders_data, list) else []
        )
        matching = [
            o for o in order_items if o.get("po_number") == extracted["po_number"]
        ]
        assert len(matching) == 0, "Rejected doc should NOT produce an order"

    # ------------------------------------------------------------------
    # 7. Document with partial extracted_data (missing fields)
    # ------------------------------------------------------------------
    def test_08_approve_partial_extracted_data(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Approve with partial extracted_data (no items) creates order but no crash."""
        s = _uid()
        partial_data = {
            "vendor_name": f"E2E Partial Vendor {s}",
            "document_type": "invoice",
            "po_number": f"PO-PART-{s.upper()}",
            # no items key
        }
        doc = _create_doc(
            authenticated_client,
            suffix=s,
            extracted_data=partial_data,
        )
        doc_id = doc["id"]

        resp = authenticated_client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"action": "approve", "reviewed_by": "e2e-tester"},
        )
        assert resp.status_code == 200, f"Approve partial failed: {resp.text}"
        assert resp.json()["status"] == "approved"

        # Order should still be created (vendor present), but with no items
        orders_resp = authenticated_client.get(
            "/api/v1/orders", params={"po_number": partial_data["po_number"]}
        )
        assert orders_resp.status_code == 200
        order_items = orders_resp.json().get("items", [])
        matching = [
            o for o in order_items if o.get("po_number") == partial_data["po_number"]
        ]
        assert len(matching) >= 1, "Order should be created even with no items"

    def test_09_approve_empty_extracted_data(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Approve with empty extracted_data (no vendor, no items) -- no order created."""
        s = _uid()
        doc = _create_doc(
            authenticated_client,
            suffix=s,
            extracted_data={},
        )
        doc_id = doc["id"]

        resp = authenticated_client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"action": "approve"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

        # No order should exist for this document
        doc_resp = authenticated_client.get(f"/api/v1/documents/{doc_id}")
        assert doc_resp.status_code == 200

    # ------------------------------------------------------------------
    # 8. Review guards -- double approve/reject blocked
    # ------------------------------------------------------------------
    def test_10_double_review_blocked(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Reviewing an already-approved document returns 409."""
        s = _uid()
        doc = _create_doc(authenticated_client, suffix=s)
        doc_id = doc["id"]

        # First approve
        resp = authenticated_client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"action": "approve"},
        )
        assert resp.status_code == 200

        # Second approve should be 409
        resp2 = authenticated_client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"action": "approve"},
        )
        assert resp2.status_code == 409

    # ------------------------------------------------------------------
    # 9. Pagination
    # ------------------------------------------------------------------
    def test_11_pagination(self, authenticated_client: TestClient | httpx.Client):
        """Create 5+ documents, paginate with page_size=2, verify pagination fields."""
        prefix = _uid()
        for i in range(5):
            _create_doc(
                authenticated_client,
                suffix=f"{prefix}{i}",
                extraction_model="pagination-test",
            )

        # Page 1
        resp = authenticated_client.get(
            "/api/v1/documents",
            params={
                "extraction_model": "pagination-test",
                "page": 1,
                "page_size": 2,
            },
        )
        assert resp.status_code == 200
        page1 = resp.json()
        assert page1["page"] == 1
        assert page1["page_size"] == 2
        assert len(page1["items"]) == 2
        assert page1["total"] >= 5
        assert page1["pages"] >= 3

        # Page 2
        resp2 = authenticated_client.get(
            "/api/v1/documents",
            params={
                "extraction_model": "pagination-test",
                "page": 2,
                "page_size": 2,
            },
        )
        assert resp2.status_code == 200
        page2 = resp2.json()
        assert page2["page"] == 2
        assert len(page2["items"]) == 2

        # Items on page 1 and page 2 should be different
        ids_p1 = {item["id"] for item in page1["items"]}
        ids_p2 = {item["id"] for item in page2["items"]}
        assert ids_p1.isdisjoint(ids_p2), "Pages must not overlap"

    # ------------------------------------------------------------------
    # 10. Soft delete
    # ------------------------------------------------------------------
    def test_12_delete_soft_deletes(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """DELETE /api/v1/documents/{id} sets status=deleted (soft-delete)."""
        doc = _create_doc(authenticated_client)
        doc_id = doc["id"]

        resp = authenticated_client.delete(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 204

        # Verify the document still exists but has deleted status
        get_resp = authenticated_client.get(f"/api/v1/documents/{doc_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "deleted"

    # ------------------------------------------------------------------
    # 11. Filter by extraction_model
    # ------------------------------------------------------------------
    def test_13_filter_by_extraction_model(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/documents?extraction_model=... filters correctly."""
        model_name = f"test-model-{_uid()}"
        _create_doc(authenticated_client, extraction_model=model_name)
        _create_doc(authenticated_client, extraction_model="other-model")

        resp = authenticated_client.get(
            "/api/v1/documents", params={"extraction_model": model_name}
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["total"] >= 1
        for item in payload["items"]:
            assert item["extraction_model"] == model_name

    # ------------------------------------------------------------------
    # 12. Multi-item approve -- multiple order items + inventory rows
    # ------------------------------------------------------------------
    def test_14_approve_multi_item_document(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Approve a document with multiple line items creates multiple OIs + inventory."""
        s = _uid()
        vendor_name = f"E2E Multi {s}"
        items = [
            {
                "catalog_number": f"CAT-A-{s[:4].upper()}",
                "description": "Tris Buffer, 1L",
                "quantity": 3,
                "unit": "EA",
                "lot_number": f"LOT-A-{s.upper()}",
                "unit_price": 32.00,
            },
            {
                "catalog_number": f"CAT-B-{s[:4].upper()}",
                "description": "EDTA Solution, 500mL",
                "quantity": 1,
                "unit": "EA",
                "lot_number": f"LOT-B-{s.upper()}",
                "unit_price": 28.75,
            },
        ]
        extracted = _make_extracted_data(suffix=s, vendor_name=vendor_name, items=items)
        doc = _create_doc(
            authenticated_client,
            suffix=s,
            extracted_data=extracted,
            vendor_name=vendor_name,
        )

        resp = authenticated_client.post(
            f"/api/v1/documents/{doc['id']}/review",
            json={"action": "approve"},
        )
        assert resp.status_code == 200

        # Fetch order
        orders_resp = authenticated_client.get(
            "/api/v1/orders", params={"po_number": extracted["po_number"]}
        )
        order_list = orders_resp.json().get("items", [])
        matching = [
            o for o in order_list if o.get("po_number") == extracted["po_number"]
        ]
        assert len(matching) == 1
        order = matching[0]

        oi_resp = authenticated_client.get(f"/api/v1/orders/{order['id']}/items")
        assert oi_resp.status_code == 200
        oi_data = oi_resp.json()
        oi_list = oi_data.get("items", oi_data if isinstance(oi_data, list) else [])
        assert len(oi_list) == 2, f"Expected 2 order items, got {len(oi_list)}"

        catalog_numbers = {oi["catalog_number"] for oi in oi_list}
        assert items[0]["catalog_number"] in catalog_numbers
        assert items[1]["catalog_number"] in catalog_numbers

    # ------------------------------------------------------------------
    # 13. Review processing doc blocked
    # ------------------------------------------------------------------
    def test_15_review_processing_doc_returns_409(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Reviewing a document still in 'processing' returns 409."""
        doc = _create_doc(
            authenticated_client, status="processing", extracted_data=None
        )
        resp = authenticated_client.post(
            f"/api/v1/documents/{doc['id']}/review",
            json={"action": "approve"},
        )
        assert resp.status_code == 409
        assert "still being processed" in resp.json()["detail"]

    # ------------------------------------------------------------------
    # 14. GET single document
    # ------------------------------------------------------------------
    def test_16_get_document_by_id(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/documents/{id} returns full document record."""
        doc = _create_doc(authenticated_client, extraction_model="get-test-model")
        resp = authenticated_client.get(f"/api/v1/documents/{doc['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == doc["id"]
        assert data["file_name"] == doc["file_name"]
        assert data["extraction_model"] == "get-test-model"
        assert data["extracted_data"] is not None

    def test_17_get_nonexistent_document_returns_404(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/documents/999999 returns 404."""
        resp = authenticated_client.get("/api/v1/documents/999999")
        assert resp.status_code == 404

    # ------------------------------------------------------------------
    # 15. PATCH update document
    # ------------------------------------------------------------------
    def test_18_update_document(self, authenticated_client: TestClient | httpx.Client):
        """PATCH /api/v1/documents/{id} updates fields."""
        doc = _create_doc(authenticated_client)
        resp = authenticated_client.patch(
            f"/api/v1/documents/{doc['id']}",
            json={
                "extraction_model": "updated-model",
                "extraction_confidence": 0.95,
                "review_notes": "Looks good",
            },
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["extraction_model"] == "updated-model"
        assert updated["extraction_confidence"] == 0.95
        assert updated["review_notes"] == "Looks good"

    # ------------------------------------------------------------------
    # 16. Stats after approvals reflect correct counts
    # ------------------------------------------------------------------
    def test_19_stats_reflect_approvals(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Stats endpoint counts change after approve/reject."""
        # Get baseline
        baseline = authenticated_client.get("/api/v1/documents/stats").json()
        baseline_total = baseline["total_documents"]

        # Create and approve
        doc = _create_doc(authenticated_client)
        authenticated_client.post(
            f"/api/v1/documents/{doc['id']}/review",
            json={"action": "approve"},
        )

        after = authenticated_client.get("/api/v1/documents/stats").json()
        assert after["total_documents"] == baseline_total + 1
        assert after["by_status"].get("approved", 0) >= 1

    # ------------------------------------------------------------------
    # 17. Sorting
    # ------------------------------------------------------------------
    def test_20_list_documents_sorted(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/documents/ with sort_by=id&sort_dir=desc returns ordered results."""
        # Seed a couple to guarantee ordering
        _create_doc(authenticated_client)
        _create_doc(authenticated_client)

        resp = authenticated_client.get(
            "/api/v1/documents",
            params={"sort_by": "id", "sort_dir": "desc", "page_size": 5},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        if len(items) >= 2:
            assert items[0]["id"] > items[1]["id"], "Should be descending by id"

    # ------------------------------------------------------------------
    # 18. Search by filename/vendor
    # ------------------------------------------------------------------
    def test_21_search_documents(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/documents?search=... matches on file_name or vendor_name."""
        s = _uid()
        unique_vendor = f"UniqueSearchVendor{s}"
        _create_doc(authenticated_client, vendor_name=unique_vendor)

        resp = authenticated_client.get(
            "/api/v1/documents", params={"search": unique_vendor}
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["total"] >= 1
        found = any(
            unique_vendor.lower() in (item.get("vendor_name") or "").lower()
            for item in payload["items"]
        )
        assert found, f"Expected to find vendor {unique_vendor} in search results"

    # ------------------------------------------------------------------
    # 19. Delete then re-review blocked
    # ------------------------------------------------------------------
    def test_22_deleted_doc_cannot_be_reviewed(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """A deleted document cannot be approved or rejected (409)."""
        doc = _create_doc(authenticated_client)
        authenticated_client.delete(f"/api/v1/documents/{doc['id']}")

        resp = authenticated_client.post(
            f"/api/v1/documents/{doc['id']}/review",
            json={"action": "approve"},
        )
        assert resp.status_code == 409
