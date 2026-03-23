"""E2E tests for orders edge cases and error handling.

Tests receive endpoint, item operations, and edge cases.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.mark.e2e
class TestOrdersPagination:
    """Tests for orders pagination."""

    def test_pagination_default_params(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/orders/ returns paginated results."""
        resp = authenticated_client.get("/api/v1/orders/")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "items" in data, f"Response missing 'items': {data.keys()}"
        assert "total" in data, f"Response missing 'total': {data.keys()}"

    def test_pagination_with_status_filter(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/orders/ with status filter."""
        resp = authenticated_client.get("/api/v1/orders/", params={"status": "pending"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "pending", (
                f"Expected status=pending, got {item['status']}"
            )

    def test_pagination_with_vendor_filter(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_vendor_id: int,
    ):
        """GET /api/v1/orders/ with vendor filter."""
        resp = authenticated_client.get(
            "/api/v1/orders/", params={"vendor_id": test_vendor_id}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        for item in data["items"]:
            assert item["vendor_id"] == test_vendor_id, (
                f"Expected vendor_id={test_vendor_id}, got {item['vendor_id']}"
            )


@pytest.mark.e2e
class TestOrdersReceive:
    """Tests for order receive endpoint."""

    def test_receive_order(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_order_id: int,
        test_product_id: int,
    ):
        """POST /api/v1/orders/{id}/receive receives order."""
        add_resp = authenticated_client.post(
            f"/api/v1/orders/{test_order_id}/items",
            json={"product_id": test_product_id, "quantity": 1},
        )
        assert add_resp.status_code == 201, f"Expected 201, got {add_resp.status_code}"

        resp = authenticated_client.post(
            f"/api/v1/orders/{test_order_id}/receive",
            json={
                "received_by": "E2E Test",
                "items": [{"product_id": test_product_id, "quantity": 1}],
            },
        )
        assert resp.status_code in (200, 201), (
            f"Expected 200 or 201, got {resp.status_code}"
        )

    def test_receive_nonexistent_order(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/orders/{id}/receive rejects non-existent orders."""
        resp = authenticated_client.post(
            "/api/v1/orders/999999/receive",
            json={"received_by": "E2E Test", "items": [{"product_id": 1, "quantity": 1}]},
        )
        assert resp.status_code in (404, 422), (
            f"Expected 404 or 422, got {resp.status_code}"
        )

    def test_receive_with_items(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_order_id: int,
        test_product_id: int,
    ):
        """POST /api/v1/orders/{id}/receive with item details."""
        # Add item first
        add_resp = authenticated_client.post(
            f"/api/v1/orders/{test_order_id}/items",
            json={
                "product_id": test_product_id,
                "quantity": 10,
                "unit_price": 99.99,
            },
        )
        assert add_resp.status_code == 201, f"Expected 201, got {add_resp.status_code}"

        resp = authenticated_client.post(
            f"/api/v1/orders/{test_order_id}/receive",
            json={
                "received_by": "E2E Test",
                "items": [{"product_id": test_product_id, "quantity": 10}],
            },
        )
        assert resp.status_code in (200, 201), (
            f"Expected 200 or 201, got {resp.status_code}"
        )


@pytest.mark.e2e
class TestOrderItems:
    """Tests for order items operations."""

    def test_list_items(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_order_id: int,
    ):
        """GET /api/v1/orders/{id}/items returns items."""
        resp = authenticated_client.get(f"/api/v1/orders/{test_order_id}/items")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "items" in data or isinstance(data, list), (
            f"Response should have 'items' or be a list: {type(data)}"
        )

    def test_add_item_invalid_product(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_order_id: int,
    ):
        """POST /api/v1/orders/{id}/items handles invalid product."""
        resp = authenticated_client.post(
            f"/api/v1/orders/{test_order_id}/items",
            json={
                "product_id": 999999,
                "quantity": 10,
            },
        )
        assert resp.status_code in (201, 422), (
            f"Expected 201 or 422, got {resp.status_code}"
        )

    def test_add_item_negative_quantity(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_order_id: int,
        test_product_id: int,
    ):
        """POST /api/v1/orders/{id}/items rejects negative quantity."""
        resp = authenticated_client.post(
            f"/api/v1/orders/{test_order_id}/items",
            json={
                "product_id": test_product_id,
                "quantity": -5,
            },
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_add_item_zero_quantity(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_order_id: int,
        test_product_id: int,
    ):
        """POST /api/v1/orders/{id}/items rejects zero quantity."""
        resp = authenticated_client.post(
            f"/api/v1/orders/{test_order_id}/items",
            json={
                "product_id": test_product_id,
                "quantity": 0,
            },
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_update_item(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_order_id: int,
        test_product_id: int,
    ):
        """PATCH /api/v1/orders/{id}/items/{item_id} updates item."""
        # Add item first
        add_resp = authenticated_client.post(
            f"/api/v1/orders/{test_order_id}/items",
            json={"product_id": test_product_id, "quantity": 10},
        )
        assert add_resp.status_code == 201, f"Expected 201, got {add_resp.status_code}"
        items = authenticated_client.get(f"/api/v1/orders/{test_order_id}/items").json()
        item_id = items["items"][0]["id"]

        resp = authenticated_client.patch(
            f"/api/v1/orders/{test_order_id}/items/{item_id}",
            json={"quantity": 20},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_delete_item(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_order_id: int,
        test_product_id: int,
    ):
        """DELETE /api/v1/orders/{id}/items/{item_id} removes item."""
        # Add item first
        add_resp = authenticated_client.post(
            f"/api/v1/orders/{test_order_id}/items",
            json={"product_id": test_product_id, "quantity": 5},
        )
        assert add_resp.status_code == 201, f"Expected 201, got {add_resp.status_code}"
        items = authenticated_client.get(f"/api/v1/orders/{test_order_id}/items").json()
        item_id = items["items"][0]["id"]

        resp = authenticated_client.delete(
            f"/api/v1/orders/{test_order_id}/items/{item_id}"
        )
        assert resp.status_code == 204, f"Expected 204, got {resp.status_code}"

    def test_get_item_by_id(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_order_id: int,
        test_product_id: int,
    ):
        """GET /api/v1/orders/{id}/items/{item_id} returns item."""
        # Add item first
        add_resp = authenticated_client.post(
            f"/api/v1/orders/{test_order_id}/items",
            json={"product_id": test_product_id, "quantity": 5},
        )
        assert add_resp.status_code == 201, f"Expected 201, got {add_resp.status_code}"
        items = authenticated_client.get(f"/api/v1/orders/{test_order_id}/items").json()
        item_id = items["items"][0]["id"]

        resp = authenticated_client.get(
            f"/api/v1/orders/{test_order_id}/items/{item_id}"
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_get_nonexistent_item(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_order_id: int,
    ):
        """GET /api/v1/orders/{id}/items/{item_id} returns 404."""
        resp = authenticated_client.get(f"/api/v1/orders/{test_order_id}/items/999999")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"


@pytest.mark.e2e
class TestOrderStatusTransitions:
    """Tests for order status transitions."""

    def test_pending_to_approved(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_vendor_id: int,
    ):
        """Order transition request from pending to approved is handled safely."""
        # Create order
        create_resp = authenticated_client.post(
            "/api/v1/orders/",
            json={
                "po_number": "E2E-STATUS-001",
                "vendor_id": test_vendor_id,
                "status": "pending",
            },
        )
        assert create_resp.status_code == 201, (
            f"Expected 201, got {create_resp.status_code}"
        )
        order_id = create_resp.json().get("order", create_resp.json())["id"]

        # Update to approved
        resp = authenticated_client.patch(
            f"/api/v1/orders/{order_id}",
            json={"status": "approved"},
        )
        assert resp.status_code in (200, 422), (
            f"Expected 200 or 422, got {resp.status_code}"
        )

    def test_approved_to_ordered(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_vendor_id: int,
    ):
        """Order transition request to ordered is handled safely."""
        # Create order in default pending state.
        create_resp = authenticated_client.post(
            "/api/v1/orders/",
            json={
                "po_number": "E2E-STATUS-002",
                "vendor_id": test_vendor_id,
            },
        )
        assert create_resp.status_code == 201, (
            f"Expected 201, got {create_resp.status_code}"
        )
        order_id = create_resp.json().get("order", create_resp.json())["id"]

        resp = authenticated_client.patch(
            f"/api/v1/orders/{order_id}",
            json={"status": "ordered"},
        )
        assert resp.status_code in (200, 422), (
            f"Expected 200 or 422, got {resp.status_code}"
        )

    def test_ordered_to_received(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_vendor_id: int,
    ):
        """Order transition request to received is handled safely."""
        create_resp = authenticated_client.post(
            "/api/v1/orders/",
            json={
                "po_number": "E2E-STATUS-003",
                "vendor_id": test_vendor_id,
                "status": "shipped",
            },
        )
        assert create_resp.status_code == 201, (
            f"Expected 201, got {create_resp.status_code}"
        )
        order_id = create_resp.json().get("order", create_resp.json())["id"]

        resp = authenticated_client.patch(
            f"/api/v1/orders/{order_id}",
            json={"status": "received"},
        )
        assert resp.status_code in (200, 422), (
            f"Expected 200 or 422, got {resp.status_code}"
        )

    def test_invalid_status_transition(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_order_id: int,
    ):
        """Invalid status transition handled gracefully."""
        # Try to set invalid status
        resp = authenticated_client.patch(
            f"/api/v1/orders/{test_order_id}",
            json={"status": "invalid_status"},
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"


@pytest.mark.e2e
class TestOrderValidation:
    """Tests for order validation."""

    def test_create_without_vendor(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/orders/ handles missing vendor."""
        resp = authenticated_client.post(
            "/api/v1/orders/",
            json={"po_number": "E2E-NO-VENDOR"},
        )
        assert resp.status_code in (201, 422), (
            f"Expected 201 or 422, got {resp.status_code}"
        )

    def test_create_duplicate_po_number(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_vendor_id: int,
    ):
        """POST /api/v1/orders/ handles duplicate PO number according to API contract."""
        po_number = "E2E-DUPLICATE-PO"
        # First create
        first_resp = authenticated_client.post(
            "/api/v1/orders/",
            json={"po_number": po_number, "vendor_id": test_vendor_id},
        )
        assert first_resp.status_code == 201, (
            f"Expected 201, got {first_resp.status_code}"
        )
        # Second create with same PO
        resp = authenticated_client.post(
            "/api/v1/orders/",
            json={"po_number": po_number, "vendor_id": test_vendor_id},
        )
        assert resp.status_code in (201, 409), (
            f"Expected 201 or 409 for duplicate, got {resp.status_code}"
        )

    def test_update_nonexistent_order(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """PATCH /api/v1/orders/{id} rejects invalid/non-existent updates."""
        resp = authenticated_client.patch(
            "/api/v1/orders/999999",
            json={"status": "shipped"},
        )
        assert resp.status_code in (404, 422), (
            f"Expected 404 or 422, got {resp.status_code}"
        )

    def test_delete_nonexistent_order(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """DELETE /api/v1/orders/{id} returns 404 for non-existent."""
        resp = authenticated_client.delete("/api/v1/orders/999999")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"


@pytest.mark.e2e
class TestOrderSearch:
    """Tests for order search/filter."""

    def test_search_by_po_number(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/orders/ searches by PO number."""
        resp = authenticated_client.get("/api/v1/orders/", params={"search": "E2E-PO"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_filter_by_date_range(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/orders/ filters by date range."""
        resp = authenticated_client.get(
            "/api/v1/orders/",
            params={
                "start_date": "2024-01-01",
                "end_date": "2026-12-31",
            },
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
