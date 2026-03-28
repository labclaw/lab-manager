"""Tests for inventory route coverage — targeting _format_quantity, _flatten_item,
list filters, CRUD, status guards, history, and reorder URL."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from lab_manager.api.routes.inventory import _flatten_item, _format_quantity
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.location import StorageLocation
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(db_session):
    import os

    os.environ["AUTH_ENABLED"] = "false"
    from lab_manager.config import get_settings

    get_settings.cache_clear()
    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _no_search_index(monkeypatch):
    """Suppress Meilisearch calls in all tests."""
    monkeypatch.setattr(
        "lab_manager.api.routes.inventory.index_inventory_record", lambda _: None
    )


@pytest.fixture()
def vendor(db_session: Session) -> Vendor:
    v = Vendor(name="Sigma-Aldrich")
    db_session.add(v)
    db_session.flush()
    return v


@pytest.fixture()
def product(db_session: Session, vendor: Vendor) -> Product:
    p = Product(
        name="DMEM Media",
        catalog_number="D6429",
        vendor_id=vendor.id,
        category="cell culture",
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture()
def product_no_vendor(db_session: Session) -> Product:
    p = Product(name="Generic Reagent", catalog_number="GR-001")
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture()
def location(db_session: Session) -> StorageLocation:
    loc = StorageLocation(name="Cold Room A", room="B210")
    db_session.add(loc)
    db_session.flush()
    return loc


def _make_item(
    db_session: Session,
    product: Product,
    *,
    location_id: int | None = None,
    quantity: str = "10.0000",
    lot_number: str | None = "LOT-001",
    expiry: date | None = None,
    notes: str | None = None,
    status: str = "available",
) -> InventoryItem:
    item = InventoryItem(
        product_id=product.id,
        location_id=location_id,
        quantity_on_hand=Decimal(quantity),
        lot_number=lot_number,
        expiry_date=expiry,
        notes=notes,
        status=status,
    )
    db_session.add(item)
    db_session.flush()
    return item


# ---------------------------------------------------------------------------
# _format_quantity unit tests
# ---------------------------------------------------------------------------


class TestFormatQuantity:
    def test_none_returns_zero(self):
        assert _format_quantity(None) == "0"

    def test_decimal_trailing_zeros(self):
        assert _format_quantity(Decimal("1.0000")) == "1"

    def test_decimal_fraction_trailing_zeros(self):
        assert _format_quantity(Decimal("2.5000")) == "2.5"

    def test_plain_integer_decimal(self):
        assert _format_quantity(Decimal("7")) == "7"

    def test_plain_int_no_normalize(self):
        """int has no normalize attr, falls through to str()."""
        assert _format_quantity(42) == "42"

    def test_zero_value(self):
        assert _format_quantity(Decimal("0.0000")) == "0"

    def test_small_fraction(self):
        assert _format_quantity(Decimal("0.1250")) == "0.125"

    def test_already_clean(self):
        assert _format_quantity(Decimal("3.14")) == "3.14"


# ---------------------------------------------------------------------------
# _flatten_item unit tests
# ---------------------------------------------------------------------------


class TestFlattenItem:
    def test_with_product_vendor_location(self, db_session, vendor, product, location):
        item = _make_item(
            db_session,
            product,
            location_id=location.id,
            quantity="5.0000",
            lot_number="LOT-X",
            expiry=date(2026, 12, 31),
            notes="test note",
        )
        # Force eager-load of relationships for the test session
        db_session.refresh(item)

        flat = _flatten_item(item)
        assert flat["id"] == item.id
        assert flat["product_id"] == product.id
        assert flat["product_name"] == "DMEM Media"
        assert flat["catalog_number"] == "D6429"
        assert flat["category"] == "cell culture"
        assert flat["vendor_name"] == "Sigma-Aldrich"
        assert flat["location_id"] == location.id
        assert flat["location_name"] == "Cold Room A"
        assert flat["lot_number"] == "LOT-X"
        assert flat["quantity_on_hand"] == 5.0
        assert flat["quantity_display"] == "5"
        assert flat["status"] == "available"
        assert flat["notes"] == "test note"
        assert flat["expiry_date"] == "2026-12-31"
        assert flat["opened_date"] is None

    def test_without_product(self, db_session, product):
        item = _make_item(db_session, product)
        # Remove product relationship
        item.product = None
        flat = _flatten_item(item)
        assert flat["product_name"] is None
        assert flat["catalog_number"] is None
        assert flat["category"] is None
        assert flat["vendor_name"] is None

    def test_without_vendor(self, db_session, product_no_vendor):
        item = _make_item(db_session, product_no_vendor)
        db_session.refresh(item)
        flat = _flatten_item(item)
        assert flat["vendor_name"] is None

    def test_without_location(self, db_session, product):
        item = _make_item(db_session, product, location_id=None)
        db_session.refresh(item)
        flat = _flatten_item(item)
        assert flat["location_id"] is None
        assert flat["location_name"] is None

    def test_none_quantity_on_hand(self, db_session, product):
        item = _make_item(db_session, product, quantity="0")
        item.quantity_on_hand = None
        flat = _flatten_item(item)
        assert flat["quantity_on_hand"] == 0
        assert flat["quantity_display"] == "0"

    def test_opened_date_set(self, db_session, product):
        item = _make_item(db_session, product)
        item.opened_date = date(2026, 6, 15)
        db_session.flush()
        flat = _flatten_item(item)
        assert flat["opened_date"] == "2026-06-15"

    def test_order_item_id(self, db_session, product):
        item = _make_item(db_session, product)
        item.order_item_id = 42
        db_session.flush()
        flat = _flatten_item(item)
        assert flat["order_item_id"] == 42


# ---------------------------------------------------------------------------
# list_inventory — filters
# ---------------------------------------------------------------------------


class TestListInventory:
    def test_list_empty(self, client):
        resp = client.get("/api/v1/inventory/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_with_items(self, client, db_session, product):
        _make_item(db_session, product, quantity="10")
        resp = client.get("/api/v1/inventory/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_filter_by_product_id(self, client, db_session, product, product_no_vendor):
        _make_item(db_session, product, lot_number="A")
        _make_item(db_session, product_no_vendor, lot_number="B")
        resp = client.get("/api/v1/inventory/", params={"product_id": product.id})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i["product_id"] == product.id for i in items)

    def test_filter_by_location_id(self, client, db_session, product, location):
        _make_item(db_session, product, location_id=location.id)
        _make_item(db_session, product, location_id=None)
        resp = client.get("/api/v1/inventory/", params={"location_id": location.id})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i["location_id"] == location.id for i in items)

    def test_filter_by_status(self, client, db_session, product):
        _make_item(db_session, product, status="available", lot_number="S-A")
        _make_item(db_session, product, status="opened", lot_number="S-O")
        resp = client.get("/api/v1/inventory/", params={"status": "opened"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i["status"] == "opened" for i in items)

    def test_filter_by_expiring_before(self, client, db_session, product):
        _make_item(
            db_session,
            product,
            expiry=date(2026, 6, 1),
            lot_number="EXP-EARLY",
        )
        _make_item(
            db_session,
            product,
            expiry=date(2026, 12, 31),
            lot_number="EXP-LATE",
        )
        resp = client.get(
            "/api/v1/inventory/",
            params={"expiring_before": "2026-07-01"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        for i in items:
            assert i["expiry_date"] is not None
            assert i["expiry_date"] <= "2026-07-01"

    def test_search_filter(self, client, db_session, product):
        _make_item(db_session, product, lot_number="UNIQUE-LOT-XYZ")
        _make_item(db_session, product, notes="searchable note ABC")
        resp = client.get("/api/v1/inventory/", params={"search": "UNIQUE-LOT-XYZ"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1
        assert any("UNIQUE-LOT-XYZ" == i["lot_number"] for i in items)

    def test_sort_by_quantity_desc(self, client, db_session, product):
        _make_item(db_session, product, quantity="5", lot_number="Q5")
        _make_item(db_session, product, quantity="50", lot_number="Q50")
        resp = client.get(
            "/api/v1/inventory/",
            params={"sort_by": "quantity_on_hand", "sort_dir": "desc"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        qtys = [i["quantity_on_hand"] for i in items]
        assert qtys == sorted(qtys, reverse=True)


# ---------------------------------------------------------------------------
# create_inventory_item
# ---------------------------------------------------------------------------


class TestCreateInventoryItem:
    def test_create_basic(self, client, product):
        resp = client.post(
            "/api/v1/inventory/",
            json={
                "product_id": product.id,
                "quantity_on_hand": "25.5",
                "lot_number": "LOT-NEW",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["product_id"] == product.id
        assert data["lot_number"] == "LOT-NEW"

    def test_create_with_all_fields(self, client, product, location):
        resp = client.post(
            "/api/v1/inventory/",
            json={
                "product_id": product.id,
                "location_id": location.id,
                "quantity_on_hand": "100",
                "unit": "mL",
                "lot_number": "FULL-LOT",
                "expiry_date": "2027-01-01",
                "opened_date": "2026-06-01",
                "status": "opened",
                "notes": "full creation test",
                "received_by": "Dr. Test",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["location_id"] == location.id
        assert data["unit"] == "mL"
        assert data["status"] == "opened"
        assert data["notes"] == "full creation test"
        assert data["received_by"] == "Dr. Test"

    def test_create_invalid_status(self, client, product):
        resp = client.post(
            "/api/v1/inventory/",
            json={
                "product_id": product.id,
                "status": "invalid_status",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# get_inventory_item — including 404
# ---------------------------------------------------------------------------


class TestGetInventoryItem:
    def test_get_existing(self, client, db_session, product):
        item = _make_item(db_session, product)
        resp = client.get(f"/api/v1/inventory/{item.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == item.id

    def test_get_404(self, client):
        resp = client.get("/api/v1/inventory/99999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# update_inventory_item — including status guard
# ---------------------------------------------------------------------------


class TestUpdateInventoryItem:
    def test_update_notes(self, client, db_session, product):
        item = _make_item(db_session, product, notes="old note")
        resp = client.patch(
            f"/api/v1/inventory/{item.id}",
            json={"notes": "updated note"},
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "updated note"

    def test_update_status_guard_deleted(self, client, db_session, product):
        item = _make_item(db_session, product, status="deleted")
        resp = client.patch(
            f"/api/v1/inventory/{item.id}",
            json={"notes": "should fail"},
        )
        assert resp.status_code == 422

    def test_update_status_guard_disposed(self, client, db_session, product):
        item = _make_item(db_session, product, status="disposed")
        resp = client.patch(
            f"/api/v1/inventory/{item.id}",
            json={"notes": "should fail"},
        )
        assert resp.status_code == 422

    def test_update_status_guard_depleted(self, client, db_session, product):
        item = _make_item(db_session, product, status="depleted")
        resp = client.patch(
            f"/api/v1/inventory/{item.id}",
            json={"notes": "should fail"},
        )
        assert resp.status_code == 422

    def test_update_available_succeeds(self, client, db_session, product):
        item = _make_item(db_session, product, status="available")
        resp = client.patch(
            f"/api/v1/inventory/{item.id}",
            json={"status": "opened"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "opened"

    def test_update_404(self, client):
        resp = client.patch(
            "/api/v1/inventory/99999",
            json={"notes": "nope"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# delete_inventory_item — soft delete
# ---------------------------------------------------------------------------


class TestDeleteInventoryItem:
    def test_soft_delete(self, client, db_session, product):
        item = _make_item(db_session, product)
        resp = client.delete(f"/api/v1/inventory/{item.id}")
        assert resp.status_code == 204
        # Verify status changed to deleted
        resp2 = client.get(f"/api/v1/inventory/{item.id}")
        assert resp2.json()["status"] == "deleted"

    def test_delete_404(self, client):
        resp = client.delete("/api/v1/inventory/99999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# item_history
# ---------------------------------------------------------------------------


class TestItemHistory:
    def test_history_empty(self, client, db_session, product):
        item = _make_item(db_session, product)
        resp = client.get(f"/api/v1/inventory/{item.id}/history")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_history_404(self, client):
        """The history endpoint delegates to inv_svc which may or may not 404.
        We just verify it returns something (not a server error)."""
        resp = client.get("/api/v1/inventory/99999/history")
        # The service does not guard against missing items for history,
        # but get_or_404 is not called there — it just queries logs.
        # Expect 200 with empty list since no consumption logs exist.
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# get_reorder_url_endpoint
# ---------------------------------------------------------------------------


class TestReorderUrlEndpoint:
    def test_reorder_known_vendor(self, client, db_session, vendor, product):
        item = _make_item(db_session, product)
        db_session.refresh(item)
        resp = client.get(f"/api/v1/inventory/{item.id}/reorder-url")
        assert resp.status_code == 200
        data = resp.json()
        assert data["vendor"] == "Sigma-Aldrich"
        assert data["catalog_number"] == "D6429"
        assert "sigmaaldrich.com" in data["url"]

    def test_reorder_no_vendor(self, client, db_session, product_no_vendor):
        item = _make_item(db_session, product_no_vendor)
        db_session.refresh(item)
        resp = client.get(f"/api/v1/inventory/{item.id}/reorder-url")
        assert resp.status_code == 200
        data = resp.json()
        assert data["vendor"] is None
        assert data["url"] is None

    def test_reorder_404(self, client):
        resp = client.get("/api/v1/inventory/99999/reorder-url")
        assert resp.status_code == 404
