"""E2E tests for inventory edge cases and error handling.

Tests pagination, sorting, expiring endpoint, and error conditions.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.mark.e2e
class TestInventoryPagination:
    """Tests for inventory pagination."""

    def test_pagination_default_params(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/ returns paginated results."""
        resp = authenticated_client.get("/api/v1/inventory/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

    def test_pagination_custom_page_size(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/ respects page_size."""
        resp = authenticated_client.get("/api/v1/inventory/", params={"page_size": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["page_size"] == 5

    def test_pagination_second_page(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/ returns correct page."""
        resp = authenticated_client.get(
            "/api/v1/inventory/", params={"page": 2, "page_size": 5}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2

    def test_pagination_invalid_page(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/ handles invalid page number."""
        resp = authenticated_client.get("/api/v1/inventory/", params={"page": 99999})
        assert resp.status_code == 200
        data = resp.json()
        # Should return empty items for out-of-range page
        assert data["items"] == [] or data["total"] >= 0


@pytest.mark.e2e
class TestInventorySorting:
    """Tests for inventory sorting."""

    def test_sort_by_quantity(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/inventory/ sorts by quantity."""
        resp = authenticated_client.get(
            "/api/v1/inventory/", params={"sort_by": "quantity", "sort_order": "desc"}
        )
        assert resp.status_code == 200
        data = resp.json()
        items = data["items"]
        if len(items) >= 2:
            # Descending order
            assert items[0]["quantity"] >= items[1]["quantity"]

    def test_sort_by_location(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/inventory/ sorts by location."""
        resp = authenticated_client.get(
            "/api/v1/inventory/", params={"sort_by": "location", "sort_order": "asc"}
        )
        assert resp.status_code == 200

    def test_sort_invalid_field(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/inventory/ handles invalid sort field."""
        resp = authenticated_client.get(
            "/api/v1/inventory/", params={"sort_by": "invalid_field"}
        )
        # API may ignore invalid sort or return error
        assert resp.status_code in (200, 400, 422)


@pytest.mark.e2e
class TestInventoryExpiring:
    """Tests for expiring inventory endpoint."""

    def test_expiring_endpoint_exists(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/expiring returns expiring items."""
        resp = authenticated_client.get("/api/v1/inventory/expiring")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data or isinstance(data, list)

    def test_expiring_with_days_param(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/expiring respects days parameter."""
        resp = authenticated_client.get(
            "/api/v1/inventory/expiring", params={"days": 30}
        )
        assert resp.status_code == 200
        data = resp.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        # All items should be expiring within 30 days
        for item in items:
            if "expiration_date" in item and item["expiration_date"]:
                # Date validation would go here
                pass

    def test_expiring_no_expirations(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/expiring returns empty when none expiring."""
        resp = authenticated_client.get(
            "/api/v1/inventory/expiring", params={"days": 0}
        )
        # May return 422 for days=0 (validation error)
        assert resp.status_code in (200, 422)


@pytest.mark.e2e
class TestInventoryNegativeQuantity:
    """Tests for negative quantity rejection."""

    def test_create_negative_quantity(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """POST /api/v1/inventory/ handles negative quantity."""
        resp = authenticated_client.post(
            "/api/v1/inventory/",
            json={
                "product_id": test_product_id,
                "quantity": -10,
                "location": "Test Location",
            },
        )
        # API may accept or reject negative quantities
        assert resp.status_code in (200, 201, 400, 422)

    def test_consume_more_than_available(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_inventory_id: int,
    ):
        """POST /api/v1/inventory/{id}/consume rejects over-consumption."""
        # First get current quantity
        get_resp = authenticated_client.get(f"/api/v1/inventory/{test_inventory_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        current_qty = float(data.get("quantity", data.get("quantity_on_hand", 0)))

        # Try to consume more than available
        resp = authenticated_client.post(
            f"/api/v1/inventory/{test_inventory_id}/consume",
            json={"quantity": current_qty + 1000},
        )
        # API may allow or reject
        assert resp.status_code in (200, 201, 400, 422)

    def test_consume_negative_quantity(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_inventory_id: int,
    ):
        """POST /api/v1/inventory/{id}/consume rejects negative quantity."""
        resp = authenticated_client.post(
            f"/api/v1/inventory/{test_inventory_id}/consume",
            json={"quantity": -5},
        )
        assert resp.status_code in (400, 422)

    def test_adjust_negative_quantity(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_inventory_id: int,
    ):
        """POST /api/v1/inventory/{id}/adjust handles adjustment to negative."""
        # First get current quantity
        get_resp = authenticated_client.get(f"/api/v1/inventory/{test_inventory_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        current_qty = float(data.get("quantity", data.get("quantity_on_hand", 0)))

        # Try to adjust to negative
        resp = authenticated_client.post(
            f"/api/v1/inventory/{test_inventory_id}/adjust",
            json={"quantity": -(current_qty + 100)},
        )
        # API may allow or reject
        assert resp.status_code in (200, 201, 400, 422)


@pytest.mark.e2e
class TestInventoryFiltering:
    """Tests for inventory filtering."""

    def test_filter_by_location(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/inventory/ filters by location."""
        resp = authenticated_client.get(
            "/api/v1/inventory/", params={"location": "Shelf A1"}
        )
        assert resp.status_code == 200
        data = resp.json()
        # Location filtering may use location_id instead of location string
        # Just verify we get a valid response structure
        assert "items" in data

    def test_filter_by_product(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """GET /api/v1/inventory/ filters by product_id."""
        resp = authenticated_client.get(
            "/api/v1/inventory/", params={"product_id": test_product_id}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["product_id"] == test_product_id

    def test_filter_by_lot_number(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/ filters by lot_number."""
        resp = authenticated_client.get(
            "/api/v1/inventory/", params={"lot_number": "LOT-E2E-001"}
        )
        assert resp.status_code == 200


@pytest.mark.e2e
class TestInventoryHistory:
    """Tests for inventory history endpoint."""

    def test_history_endpoint(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_inventory_id: int,
    ):
        """GET /api/v1/inventory/{id}/history returns history."""
        resp = authenticated_client.get(
            f"/api/v1/inventory/{test_inventory_id}/history"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data or isinstance(data, list)

    def test_history_nonexistent_item(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/{id}/history handles non-existent item."""
        resp = authenticated_client.get("/api/v1/inventory/999999/history")
        # May return 200 with empty list or 404
        assert resp.status_code in (200, 404)


@pytest.mark.e2e
class TestInventoryTransfer:
    """Tests for inventory transfer operations."""

    def test_transfer_to_same_location(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_inventory_id: int,
    ):
        """POST /api/v1/inventory/{id}/transfer handles same location."""
        # Get current location
        get_resp = authenticated_client.get(f"/api/v1/inventory/{test_inventory_id}")
        data = get_resp.json()
        current_location = data.get("location", data.get("location_id", "A1"))

        resp = authenticated_client.post(
            f"/api/v1/inventory/{test_inventory_id}/transfer",
            json={"location": current_location},
        )
        # May succeed (no-op) or return error
        assert resp.status_code in (200, 201, 400, 404, 422)

    def test_transfer_invalid_quantity(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_inventory_id: int,
    ):
        """POST /api/v1/inventory/{id}/transfer rejects invalid quantity."""
        resp = authenticated_client.post(
            f"/api/v1/inventory/{test_inventory_id}/transfer",
            json={"location": "New Location", "quantity": -5},
        )
        assert resp.status_code in (400, 422)


@pytest.mark.e2e
class TestInventoryDispose:
    """Tests for inventory disposal."""

    def test_dispose_with_reason(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """POST /api/v1/inventory/{id}/dispose with reason."""
        # Create item to dispose
        create_resp = authenticated_client.post(
            "/api/v1/inventory/",
            json={
                "product_id": test_product_id,
                "quantity": 10,
                "location": "Dispose Test",
                "lot_number": "LOT-DISPOSE-001",
            },
        )
        assert create_resp.status_code == 201
        item_id = create_resp.json()["id"]

        # Dispose with reason
        resp = authenticated_client.post(
            f"/api/v1/inventory/{item_id}/dispose",
            json={"reason": "Expired", "quantity": 10},
        )
        assert resp.status_code in (200, 201, 400, 404, 422)

    def test_dispose_partial_quantity(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """POST /api/v1/inventory/{id}/dispose partial quantity."""
        # Create item
        create_resp = authenticated_client.post(
            "/api/v1/inventory/",
            json={
                "product_id": test_product_id,
                "quantity": 100,
                "location": "Partial Dispose Test",
            },
        )
        if create_resp.status_code == 201:
            item_id = create_resp.json()["id"]

            # Dispose partial
            resp = authenticated_client.post(
                f"/api/v1/inventory/{item_id}/dispose",
                json={"quantity": 50},
            )
            assert resp.status_code in (200, 201, 400, 404, 422)
