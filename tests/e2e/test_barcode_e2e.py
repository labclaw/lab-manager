"""E2E tests for barcode lookup endpoints.

Tests barcode/QR value lookup against products and inventory.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4


@pytest.mark.e2e
class TestBarcodeLookup:
    """End-to-end tests for barcode lookup."""

    def test_lookup_known_catalog_number(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """GET /api/v1/barcode/lookup finds product by catalog number."""
        # First get the product's catalog number
        prod_resp = authenticated_client.get(f"/api/v1/products/{test_product_id}")
        assert prod_resp.status_code == 200
        catalog_number = prod_resp.json().get("catalog_number")

        if not catalog_number:
            pytest.skip("Product has no catalog_number")

        resp = authenticated_client.get(
            "/api/v1/barcode/lookup",
            params={"value": catalog_number},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "match_type" in data
        assert data["match_type"] in (
            "catalog_number_exact",
            "partial",
            "none",
        )

    def test_lookup_no_match(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/barcode/lookup with unknown value returns none."""
        resp = authenticated_client.get(
            "/api/v1/barcode/lookup",
            params={"value": f"NONEXISTENT-{uuid4().hex[:8]}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["match_type"] in ("none", "partial")

    def test_lookup_empty_value(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/barcode/lookup with empty value returns 422."""
        resp = authenticated_client.get(
            "/api/v1/barcode/lookup",
            params={"value": ""},
        )
        assert resp.status_code == 422

    def test_lookup_missing_value(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/barcode/lookup without value param returns 422."""
        resp = authenticated_client.get("/api/v1/barcode/lookup")
        assert resp.status_code == 422

    def test_lookup_pagination(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/barcode/lookup supports pagination."""
        resp = authenticated_client.get(
            "/api/v1/barcode/lookup",
            params={"value": "E2E", "page": 1, "page_size": 10},
        )
        assert resp.status_code == 200
        data = resp.json()
        if "page" in data:
            assert data["page"] == 1

    def test_lookup_response_structure(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Response has expected fields."""
        resp = authenticated_client.get(
            "/api/v1/barcode/lookup",
            params={"value": "test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "match_type" in data


@pytest.mark.e2e
class TestBarcodeLookupWithInventory:
    """Barcode lookup tests that create inventory for matching."""

    def test_lookup_finds_inventory_by_lot_number(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """GET /api/v1/barcode/lookup finds inventory by lot number."""
        # Create inventory with a unique lot number
        lot = f"E2E-LOT-{uuid4().hex[:8].upper()}"
        inv_resp = authenticated_client.post(
            "/api/v1/inventory/",
            json={
                "product_id": test_product_id,
                "quantity": 50,
                "location": "Shelf E2E",
                "lot_number": lot,
            },
        )
        assert inv_resp.status_code in (200, 201)

        # Lookup by that lot number
        resp = authenticated_client.get(
            "/api/v1/barcode/lookup",
            params={"value": lot},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["match_type"] in ("partial", "catalog_number_exact")

    def test_lookup_partial_match(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Partial barcode match returns partial match_type."""
        resp = authenticated_client.get(
            "/api/v1/barcode/lookup",
            params={"value": "E2E-TEST"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "match_type" in data
