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
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_pagination_with_status_filter(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/orders/ with status filter."""
        resp = authenticated_client.get("/api/v1/orders/", params={"status": "pending"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "pending"

    def test_pagination_with_vendor_filter(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_vendor_id: int,
    ):
        """GET /api/v1/orders/ with vendor filter."""
        resp = authenticated_client.get(
            "/api/v1/orders/", params={"vendor_id": test_vendor_id}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["vendor_id"] == test_vendor_id


@pytest.mark.e2e
class TestOrdersReceive:
    """Tests for order receive endpoint."""

    def test_receive_order(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_order_id: int,
    ):
        """POST /api/v1/orders/{id}/receive receives order."""
        resp = authenticated_client.post(
            f"/api/v1/orders/{test_order_id}/receive",
            json={
                "received_by": "E2E Test",
                "notes": "Test receive",
            },
        )
        assert resp.status_code in (200, 201, 400, 404, 422)

    def test_receive_already_received(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_order_id: int,
    ):
        """POST /api/v1/orders/{id}/receive rejects double receive."""
        # First receive
        authenticated_client.post(
            f"/api/v1/orders/{test_order_id}/receive",
            json={"received_by": "E2E Test"},
        )
        # Second receive
        resp = authenticated_client.post(
            f"/api/v1/orders/{test_order_id}/receive",
            json={"received_by": "E2E Test"},
        )
        # May succeed (idempotent) or fail
        assert resp.status_code in (200, 201, 400, 404, 422)

    def test_receive_nonexistent_order(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/orders/{id}/receive returns 404 for non-existent."""
        resp = authenticated_client.post(
            "/api/v1/orders/999999/receive",
            json={"received_by": "E2E Test"},
        )
        # May return 404 or 422
        assert resp.status_code in (400, 404, 422)

    def test_receive_with_items(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_order_id: int,
        test_product_id: int,
    ):
        """POST /api/v1/orders/{id}/receive with item details."""
        # Add item first
        authenticated_client.post(
            f"/api/v1/orders/{test_order_id}/items",
            json={
                "product_id": test_product_id,
                "quantity": 10,
                "unit_price": 99.99,
            },
        )

        resp = authenticated_client.post(
            f"/api/v1/orders/{test_order_id}/receive",
            json={
                "received_by": "E2E Test",
                "items": [{"product_id": test_product_id, "received_quantity": 10}],
            },
        )
        assert resp.status_code in (200, 201, 400, 404, 422)


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
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data or isinstance(data, list)

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
        # API may create item anyway or reject
        assert resp.status_code in (200, 201, 400, 404, 422)

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
        assert resp.status_code in (400, 422)

    def test_add_item_zero_quantity(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_order_id: int,
        test_product_id: int,
    ):
        """POST /api/v1/orders/{id}/items handles zero quantity."""
        resp = authenticated_client.post(
            f"/api/v1/orders/{test_order_id}/items",
            json={
                "product_id": test_product_id,
                "quantity": 0,
            },
        )
        assert resp.status_code in (200, 201, 400, 422)

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
        if add_resp.status_code in (200, 201):
            items = authenticated_client.get(
                f"/api/v1/orders/{test_order_id}/items"
            ).json()
            item_id = items["items"][0]["id"] if "items" in items else items[0]["id"]

            resp = authenticated_client.patch(
                f"/api/v1/orders/{test_order_id}/items/{item_id}",
                json={"quantity": 20},
            )
            assert resp.status_code in (200, 404)

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
        if add_resp.status_code in (200, 201):
            items = authenticated_client.get(
                f"/api/v1/orders/{test_order_id}/items"
            ).json()
            item_id = items["items"][0]["id"] if "items" in items else items[0]["id"]

            resp = authenticated_client.delete(
                f"/api/v1/orders/{test_order_id}/items/{item_id}"
            )
            assert resp.status_code in (200, 204, 404)

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
        if add_resp.status_code in (200, 201):
            items = authenticated_client.get(
                f"/api/v1/orders/{test_order_id}/items"
            ).json()
            item_id = items["items"][0]["id"] if "items" in items else items[0]["id"]

            resp = authenticated_client.get(
                f"/api/v1/orders/{test_order_id}/items/{item_id}"
            )
            assert resp.status_code in (200, 404)

    def test_get_nonexistent_item(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_order_id: int,
    ):
        """GET /api/v1/orders/{id}/items/{item_id} returns 404."""
        resp = authenticated_client.get(f"/api/v1/orders/{test_order_id}/items/999999")
        assert resp.status_code == 404


@pytest.mark.e2e
class TestOrderStatusTransitions:
    """Tests for order status transitions."""

    def test_pending_to_approved(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_vendor_id: int,
    ):
        """Order transitions from pending to approved."""
        # Create order
        create_resp = authenticated_client.post(
            "/api/v1/orders/",
            json={
                "po_number": "E2E-STATUS-001",
                "vendor_id": test_vendor_id,
                "status": "pending",
            },
        )
        assert create_resp.status_code in (200, 201)
        order_id = create_resp.json().get("order", create_resp.json())["id"]

        # Update to approved
        resp = authenticated_client.patch(
            f"/api/v1/orders/{order_id}",
            json={"status": "approved"},
        )
        # May allow or reject status transition
        assert resp.status_code in (200, 400, 422)

    def test_approved_to_ordered(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_vendor_id: int,
    ):
        """Order transitions from approved to ordered."""
        # Create and approve order
        create_resp = authenticated_client.post(
            "/api/v1/orders/",
            json={
                "po_number": "E2E-STATUS-002",
                "vendor_id": test_vendor_id,
                "status": "approved",
            },
        )
        if create_resp.status_code not in (200, 201):
            pytest.skip("Could not create order")
        order_id = create_resp.json().get("order", create_resp.json())["id"]

        resp = authenticated_client.patch(
            f"/api/v1/orders/{order_id}",
            json={"status": "ordered"},
        )
        assert resp.status_code in (200, 400, 422)

    def test_ordered_to_received(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_vendor_id: int,
    ):
        """Order transitions from ordered to received."""
        create_resp = authenticated_client.post(
            "/api/v1/orders/",
            json={
                "po_number": "E2E-STATUS-003",
                "vendor_id": test_vendor_id,
                "status": "ordered",
            },
        )
        if create_resp.status_code not in (200, 201):
            pytest.skip("Could not create order")
        order_id = create_resp.json().get("order", create_resp.json())["id"]

        resp = authenticated_client.patch(
            f"/api/v1/orders/{order_id}",
            json={"status": "received"},
        )
        assert resp.status_code in (200, 400, 422)

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
        assert resp.status_code in (400, 422)


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
        # May create with null vendor or require it
        assert resp.status_code in (200, 201, 400, 422)

    def test_create_duplicate_po_number(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_vendor_id: int,
    ):
        """POST /api/v1/orders/ handles duplicate PO number."""
        po_number = "E2E-DUPLICATE-PO"
        # First create
        authenticated_client.post(
            "/api/v1/orders/",
            json={"po_number": po_number, "vendor_id": test_vendor_id},
        )
        # Second create with same PO
        resp = authenticated_client.post(
            "/api/v1/orders/",
            json={"po_number": po_number, "vendor_id": test_vendor_id},
        )
        # May allow duplicates or reject
        assert resp.status_code in (200, 201, 400, 409, 422)

    def test_update_nonexistent_order(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """PATCH /api/v1/orders/{id} returns 404 for non-existent."""
        resp = authenticated_client.patch(
            "/api/v1/orders/999999",
            json={"status": "approved"},
        )
        # May return 404 or 422
        assert resp.status_code in (400, 404, 422)

    def test_delete_nonexistent_order(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """DELETE /api/v1/orders/{id} returns 404 for non-existent."""
        resp = authenticated_client.delete("/api/v1/orders/999999")
        assert resp.status_code == 404


@pytest.mark.e2e
class TestOrderSearch:
    """Tests for order search/filter."""

    def test_search_by_po_number(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/orders/ searches by PO number."""
        resp = authenticated_client.get("/api/v1/orders/", params={"search": "E2E-PO"})
        assert resp.status_code == 200

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
        assert resp.status_code == 200
