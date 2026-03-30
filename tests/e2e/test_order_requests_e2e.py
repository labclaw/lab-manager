"""E2E tests for order request endpoints.

Tests the full supply request lifecycle: create, approve, reject, cancel.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4


@pytest.mark.e2e
class TestOrderRequestsE2E:
    """End-to-end tests for order request management."""

    def test_create_request(
        self,
        authenticated_client: TestClient,
        test_vendor_id: int,
    ):
        """POST /api/v1/requests/ creates a new supply request."""
        resp = authenticated_client.post(
            "/api/v1/requests/",
            json={
                "vendor_id": test_vendor_id,
                "catalog_number": f"CAT-{uuid4().hex[:6].upper()}",
                "description": "E2E test antibody",
                "quantity": "5",
                "unit": "vial",
                "estimated_price": "199.99",
                "urgency": "normal",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == "pending"
        assert data["description"] == "E2E test antibody"
        assert float(data["quantity"]) == 5

    def test_list_requests(self, authenticated_client: TestClient):
        """GET /api/v1/requests/ returns paginated list."""
        resp = authenticated_client.get("/api/v1/requests/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data or isinstance(data, list)

    def test_get_request_stats(self, authenticated_client: TestClient):
        """GET /api/v1/requests/stats returns status counts."""
        resp = authenticated_client.get("/api/v1/requests/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "pending" in data
        assert "total" in data

    def test_get_request_detail(self, authenticated_client: TestClient):
        """GET /api/v1/requests/{id} returns request detail."""
        create_resp = authenticated_client.post(
            "/api/v1/requests/",
            json={
                "description": "E2E detail test",
                "quantity": "1",
                "urgency": "normal",
            },
        )
        assert create_resp.status_code == 201
        req_id = create_resp.json()["id"]
        resp = authenticated_client.get(f"/api/v1/requests/{req_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == req_id

    def test_approve_request(
        self,
        authenticated_client: TestClient,
        test_vendor_id: int,
    ):
        """POST /api/v1/requests/{id}/approve creates an order."""
        create_resp = authenticated_client.post(
            "/api/v1/requests/",
            json={
                "vendor_id": test_vendor_id,
                "catalog_number": f"CAT-{uuid4().hex[:6].upper()}",
                "description": "E2E approve test",
                "quantity": "2",
                "urgency": "normal",
            },
        )
        assert create_resp.status_code == 201
        req_id = create_resp.json()["id"]

        resp = authenticated_client.post(
            f"/api/v1/requests/{req_id}/approve",
            json={"note": "Approved by E2E test"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "approved"
        assert data["order_id"] is not None, "Approval should create an order"

    def test_reject_request(self, authenticated_client: TestClient):
        """POST /api/v1/requests/{id}/reject rejects the request."""
        create_resp = authenticated_client.post(
            "/api/v1/requests/",
            json={
                "description": "E2E reject test",
                "quantity": "1",
                "urgency": "normal",
            },
        )
        assert create_resp.status_code == 201
        req_id = create_resp.json()["id"]

        resp = authenticated_client.post(
            f"/api/v1/requests/{req_id}/reject",
            json={"note": "Over budget"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "rejected"
        assert data["review_note"] == "Over budget"

    def test_cancel_request(self, authenticated_client: TestClient):
        """POST /api/v1/requests/{id}/cancel cancels own request."""
        create_resp = authenticated_client.post(
            "/api/v1/requests/",
            json={
                "description": "E2E cancel test",
                "quantity": "1",
                "urgency": "normal",
            },
        )
        assert create_resp.status_code == 201
        req_id = create_resp.json()["id"]

        resp = authenticated_client.post(f"/api/v1/requests/{req_id}/cancel")
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "cancelled"

    def test_approve_without_vendor_fails(self, authenticated_client: TestClient):
        """Approving a request without vendor_id returns 400."""
        create_resp = authenticated_client.post(
            "/api/v1/requests/",
            json={
                "description": "No vendor test",
                "quantity": "1",
            },
        )
        assert create_resp.status_code == 201
        req_id = create_resp.json()["id"]

        resp = authenticated_client.post(
            f"/api/v1/requests/{req_id}/approve",
            json={"note": "Try approve"},
        )
        assert resp.status_code == 400

    def test_approve_non_pending_fails(
        self,
        authenticated_client: TestClient,
        test_vendor_id: int,
    ):
        """Cannot approve an already approved request."""
        create_resp = authenticated_client.post(
            "/api/v1/requests/",
            json={
                "vendor_id": test_vendor_id,
                "description": "Double approve test",
                "quantity": "1",
            },
        )
        assert create_resp.status_code == 201
        req_id = create_resp.json()["id"]

        approve_resp = authenticated_client.post(
            f"/api/v1/requests/{req_id}/approve",
            json={"note": "First approval"},
        )
        assert approve_resp.status_code == 200

        resp = authenticated_client.post(
            f"/api/v1/requests/{req_id}/approve",
            json={"note": "Second approval"},
        )
        assert resp.status_code == 409

    def test_quantity_boundary(self, authenticated_client: TestClient):
        """Quantity must be > 0."""
        resp = authenticated_client.post(
            "/api/v1/requests/",
            json={
                "description": "Zero qty test",
                "quantity": "0",
            },
        )
        assert resp.status_code == 422

    def test_404_for_nonexistent_request(self, authenticated_client: TestClient):
        """GET /api/v1/requests/99999 returns 404."""
        resp = authenticated_client.get("/api/v1/requests/99999")
        assert resp.status_code == 404
