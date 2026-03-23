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
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "items" in data, f"Response missing 'items': {data.keys()}"
        assert "total" in data, f"Response missing 'total': {data.keys()}"
        assert "page" in data, f"Response missing 'page': {data.keys()}"
        assert "page_size" in data, f"Response missing 'page_size': {data.keys()}"

    def test_pagination_custom_page_size(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/ respects page_size."""
        resp = authenticated_client.get("/api/v1/inventory/", params={"page_size": 5})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["page_size"] == 5, f"Expected page_size=5, got {data['page_size']}"

    def test_pagination_second_page(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/ returns correct page."""
        resp = authenticated_client.get(
            "/api/v1/inventory/", params={"page": 2, "page_size": 5}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["page"] == 2, f"Expected page=2, got {data['page']}"

    def test_pagination_invalid_page(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/ returns empty items for out-of-range page."""
        resp = authenticated_client.get("/api/v1/inventory/", params={"page": 99999})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        # Out-of-range page should return empty items
        assert data["items"] == [], (
            f"Expected empty items, got {len(data['items'])} items"
        )


@pytest.mark.e2e
class TestInventorySorting:
    """Tests for inventory sorting."""

    def test_sort_by_quantity(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/inventory/ sorts by quantity descending."""
        resp = authenticated_client.get(
            "/api/v1/inventory/", params={"sort_by": "quantity", "sort_order": "desc"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        items = data["items"]
        if len(items) >= 2:
            assert items[0]["quantity"] >= items[1]["quantity"], (
                f"Items not sorted descending: {items[0]['quantity']} < {items[1]['quantity']}"
            )

    def test_sort_by_location(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/inventory/ sorts by location ascending."""
        resp = authenticated_client.get(
            "/api/v1/inventory/", params={"sort_by": "location", "sort_order": "asc"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_sort_invalid_field(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/inventory/ handles invalid sort field safely."""
        resp = authenticated_client.get(
            "/api/v1/inventory/", params={"sort_by": "invalid_field_xyz"}
        )
        assert resp.status_code in (200, 400, 422), (
            f"Expected 200/400/422, got {resp.status_code}"
        )


@pytest.mark.e2e
class TestInventoryExpiring:
    """Tests for expiring inventory endpoint."""

    def test_expiring_endpoint_exists(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/expiring returns expiring items."""
        resp = authenticated_client.get("/api/v1/inventory/expiring")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "items" in data or isinstance(data, list), (
            f"Response should have 'items' or be a list: {type(data)}"
        )

    def test_expiring_with_days_param(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/expiring respects days parameter."""
        resp = authenticated_client.get(
            "/api/v1/inventory/expiring", params={"days": 30}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        # Response should be valid JSON structure
        data = resp.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        assert isinstance(items, list), f"Expected list, got {type(items)}"


@pytest.mark.e2e
class TestInventoryNegativeQuantity:
    """Tests for negative quantity rejection."""

    def test_consume_negative_quantity(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_inventory_id: int,
    ):
        """POST /api/v1/inventory/{id}/consume rejects negative quantity with 422."""
        resp = authenticated_client.post(
            f"/api/v1/inventory/{test_inventory_id}/consume",
            json={"quantity": -5},
        )
        assert resp.status_code == 422, (
            f"Expected 422 for negative quantity, got {resp.status_code}"
        )

    def test_consume_zero_quantity(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_inventory_id: int,
    ):
        """POST /api/v1/inventory/{id}/consume rejects zero quantity with 422."""
        resp = authenticated_client.post(
            f"/api/v1/inventory/{test_inventory_id}/consume",
            json={"quantity": 0},
        )
        assert resp.status_code == 422, (
            f"Expected 422 for zero quantity, got {resp.status_code}"
        )


@pytest.mark.e2e
class TestInventoryFiltering:
    """Tests for inventory filtering."""

    def test_filter_by_location(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/inventory/ filters by location."""
        resp = authenticated_client.get(
            "/api/v1/inventory/", params={"location": "Shelf A1"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "items" in data, f"Response missing 'items': {data.keys()}"

    def test_filter_by_product(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """GET /api/v1/inventory/ filters by product_id."""
        resp = authenticated_client.get(
            "/api/v1/inventory/", params={"product_id": test_product_id}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        for item in data["items"]:
            assert item["product_id"] == test_product_id, (
                f"Expected product_id={test_product_id}, got {item['product_id']}"
            )

    def test_filter_by_lot_number(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/ filters by lot_number."""
        resp = authenticated_client.get(
            "/api/v1/inventory/", params={"lot_number": "LOT-E2E-001"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


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
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "items" in data or isinstance(data, list), (
            f"Response should have 'items' or be a list: {type(data)}"
        )

    def test_history_nonexistent_item(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/{id}/history handles missing items gracefully."""
        resp = authenticated_client.get("/api/v1/inventory/999999/history")
        assert resp.status_code in (200, 404), (
            f"Expected 200 or 404, got {resp.status_code}"
        )


@pytest.mark.e2e
class TestInventoryTransfer:
    """Tests for inventory transfer operations."""

    def test_transfer_invalid_quantity(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_inventory_id: int,
    ):
        """POST /api/v1/inventory/{id}/transfer rejects negative quantity with 422."""
        resp = authenticated_client.post(
            f"/api/v1/inventory/{test_inventory_id}/transfer",
            json={"location": "New Location", "quantity": -5},
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"


@pytest.mark.e2e
class TestInventoryDispose:
    """Tests for inventory disposal."""

    def test_dispose_with_reason(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """POST /api/v1/inventory/{id}/dispose validates the dispose payload."""
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
        assert create_resp.status_code == 201, (
            f"Expected 201, got {create_resp.status_code}"
        )
        item_id = create_resp.json()["id"]

        # Dispose with reason
        resp = authenticated_client.post(
            f"/api/v1/inventory/{item_id}/dispose",
            json={"reason": "Expired", "disposed_by": "e2e-tester"},
        )
        assert resp.status_code in (200, 201), (
            f"Expected 200 or 201, got {resp.status_code}"
        )

    def test_dispose_item(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """POST /api/v1/inventory/{id}/dispose disposes an item."""
        # Create item
        create_resp = authenticated_client.post(
            "/api/v1/inventory/",
            json={
                "product_id": test_product_id,
                "quantity": 100,
                "location": "Dispose Test",
            },
        )
        assert create_resp.status_code == 201, (
            f"Expected 201, got {create_resp.status_code}"
        )
        item_id = create_resp.json()["id"]

        # Dispose the item
        resp = authenticated_client.post(
            f"/api/v1/inventory/{item_id}/dispose",
            json={"reason": "Expired", "disposed_by": "e2e-tester"},
        )
        assert resp.status_code in (200, 201), (
            f"Expected 200 or 201, got {resp.status_code}"
        )
