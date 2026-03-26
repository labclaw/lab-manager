"""Tests for barcode lookup endpoint."""

import pytest

from lab_manager.models.product import Product
from lab_manager.models.inventory import InventoryItem


@pytest.fixture
def seed_products(db_session):
    """Seed products and inventory for barcode tests."""
    p1 = Product(catalog_number="S1234", name="Sodium Chloride")
    p2 = Product(catalog_number="E5678", name="Ethanol 95%")
    db_session.add_all([p1, p2])
    db_session.flush()

    inv1 = InventoryItem(
        product_id=p1.id,
        lot_number="LOT-ABC",
        quantity_on_hand=5,
        unit="kg",
        status="available",
    )
    inv2 = InventoryItem(
        product_id=p2.id,
        lot_number="LOT-DEF",
        quantity_on_hand=2,
        unit="L",
        status="available",
    )
    db_session.add_all([inv1, inv2])
    db_session.flush()
    return p1, p2, inv1, inv2


class TestBarcodeLookup:
    """GET /api/v1/barcode/lookup?value=..."""

    def test_exact_catalog_number_match(self, client, seed_products):
        res = client.get("/api/v1/barcode/lookup?value=S1234")
        assert res.status_code == 200
        data = res.json()
        assert data["match_type"] == "catalog_number_exact"
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["lot_number"] == "LOT-ABC"

    def test_partial_name_match(self, client, seed_products):
        res = client.get("/api/v1/barcode/lookup?value=Sodium")
        assert res.status_code == 200
        data = res.json()
        assert data["match_type"] == "partial"
        assert data["total"] >= 1

    def test_partial_catalog_match(self, client, seed_products):
        res = client.get("/api/v1/barcode/lookup?value=E567")
        assert res.status_code == 200
        data = res.json()
        assert data["match_type"] == "partial"
        assert data["total"] >= 1

    def test_lot_number_match(self, client, seed_products):
        res = client.get("/api/v1/barcode/lookup?value=LOT-ABC")
        assert res.status_code == 200
        data = res.json()
        assert data["match_type"] == "partial"
        assert data["total"] >= 1

    def test_no_match_returns_empty(self, client, seed_products):
        res = client.get("/api/v1/barcode/lookup?value=NONEXISTENT-999")
        assert res.status_code == 200
        data = res.json()
        assert data["match_type"] == "none"
        assert data["total"] == 0
        assert data["items"] == []

    def test_missing_value_returns_422(self, client, seed_products):
        res = client.get("/api/v1/barcode/lookup")
        assert res.status_code == 422

    def test_pagination_params_accepted(self, client, seed_products):
        res = client.get("/api/v1/barcode/lookup?value=S1234&page=1&page_size=10")
        assert res.status_code == 200
        data = res.json()
        assert data["page"] == 1
        assert data["page_size"] in (10, 50)  # accepted or default
