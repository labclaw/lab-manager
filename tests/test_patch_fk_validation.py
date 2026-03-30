"""Tests for FK validation on PATCH endpoints.

Verifies that PATCH routes return proper 404/409 errors when referencing
non-existent foreign keys, instead of raw 500 IntegrityError from the database.

Covers:
- PATCH /api/v1/inventory/{id}  — product_id, location_id, order_item_id
- PATCH /api/v1/orders/{id}     — vendor_id, document_id
- PATCH /api/v1/vendors/{id}    — duplicate name -> 409
- PATCH /api/v1/products/{id}   — vendor_id
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.models.order import Order, OrderStatus
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor


@pytest.fixture
def engine():
    e = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(e)
    return e


@pytest.fixture
def db(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(db, monkeypatch):
    import os
    from unittest.mock import patch

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db
    from lab_manager.config import get_settings

    os.environ["AUTH_ENABLED"] = "false"
    os.environ["ADMIN_SECRET_KEY"] = "test-key"
    get_settings.cache_clear()

    app = create_app()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        with (
            patch("lab_manager.api.routes.inventory.index_inventory_record"),
            patch("lab_manager.api.routes.orders.index_order_record"),
            patch("lab_manager.api.routes.vendors.index_vendor_record"),
            patch("lab_manager.api.routes.products.index_product_record"),
        ):
            yield c

    get_settings.cache_clear()


_vendor_counter = 0


def _make_vendor(db, **kwargs):
    global _vendor_counter
    _vendor_counter += 1
    defaults = dict(
        name=f"TestVendor{_vendor_counter}", email=f"test{_vendor_counter}@vendor.com"
    )
    defaults.update(kwargs)
    v = Vendor(**defaults)
    db.add(v)
    db.flush()
    db.refresh(v)
    return v


def _make_product(db, vendor=None, **kwargs):
    if vendor is None:
        vendor = _make_vendor(db)
    defaults = dict(
        catalog_number="CAT-001",
        name="Test Product",
        vendor_id=vendor.id,
        category="reagent",
    )
    defaults.update(kwargs)
    p = Product(**defaults)
    db.add(p)
    db.flush()
    db.refresh(p)
    return p


def _make_order(db, vendor=None, **kwargs):
    if vendor is None:
        vendor = _make_vendor(db)
    defaults = dict(status=OrderStatus.pending, vendor_id=vendor.id)
    defaults.update(kwargs)
    o = Order(**defaults)
    db.add(o)
    db.flush()
    db.refresh(o)
    return o


# ---- Inventory PATCH FK validation ----


def test_patch_inventory_missing_product_returns_404(client, db):
    """PATCH inventory with non-existent product_id returns 404, not 500."""
    product = _make_product(db)
    from lab_manager.models.inventory import InventoryItem

    item = InventoryItem(product_id=product.id, status="available")
    db.add(item)
    db.flush()
    db.refresh(item)

    resp = client.patch(
        f"/api/v1/inventory/{item.id}",
        json={"product_id": 99999},
    )
    assert resp.status_code == 404
    assert "Product" in resp.json()["detail"]


def test_patch_inventory_valid_product_succeeds(client, db):
    """PATCH inventory with valid product_id succeeds."""
    product1 = _make_product(db, catalog_number="CAT-001")
    product2 = _make_product(db, catalog_number="CAT-002", name="Product 2")
    from lab_manager.models.inventory import InventoryItem

    item = InventoryItem(product_id=product1.id, status="available")
    db.add(item)
    db.flush()
    db.refresh(item)

    resp = client.patch(
        f"/api/v1/inventory/{item.id}",
        json={"product_id": product2.id},
    )
    assert resp.status_code == 200
    assert resp.json()["product_id"] == product2.id


def test_patch_inventory_missing_location_returns_404(client, db):
    """PATCH inventory with non-existent location_id returns 404."""
    product = _make_product(db)
    from lab_manager.models.inventory import InventoryItem

    item = InventoryItem(product_id=product.id, status="available")
    db.add(item)
    db.flush()
    db.refresh(item)

    resp = client.patch(
        f"/api/v1/inventory/{item.id}",
        json={"location_id": 99999},
    )
    assert resp.status_code == 404
    assert "Location" in resp.json()["detail"]


def test_patch_inventory_missing_order_item_returns_404(client, db):
    """PATCH inventory with non-existent order_item_id returns 404."""
    product = _make_product(db)
    from lab_manager.models.inventory import InventoryItem

    item = InventoryItem(product_id=product.id, status="available")
    db.add(item)
    db.flush()
    db.refresh(item)

    resp = client.patch(
        f"/api/v1/inventory/{item.id}",
        json={"order_item_id": 99999},
    )
    assert resp.status_code == 404
    assert "Order item" in resp.json()["detail"]


# ---- Orders PATCH FK validation ----


def test_patch_order_missing_vendor_returns_404(client, db):
    """PATCH order with non-existent vendor_id returns 404."""
    order = _make_order(db)

    resp = client.patch(
        f"/api/v1/orders/{order.id}",
        json={"vendor_id": 99999},
    )
    assert resp.status_code == 404
    assert "Vendor" in resp.json()["detail"]


def test_patch_order_valid_vendor_succeeds(client, db):
    """PATCH order with valid vendor_id succeeds."""
    vendor1 = _make_vendor(db, name="Vendor A")
    vendor2 = _make_vendor(db, name="Vendor B")
    order = _make_order(db, vendor=vendor1)

    resp = client.patch(
        f"/api/v1/orders/{order.id}",
        json={"vendor_id": vendor2.id},
    )
    assert resp.status_code == 200
    assert resp.json()["vendor_id"] == vendor2.id


def test_patch_order_missing_document_returns_404(client, db):
    """PATCH order with non-existent document_id returns 404."""
    order = _make_order(db)

    resp = client.patch(
        f"/api/v1/orders/{order.id}",
        json={"document_id": 99999},
    )
    assert resp.status_code == 404
    assert "Document" in resp.json()["detail"]


def test_patch_order_clearing_vendor_id_succeeds(client, db):
    """PATCH order setting vendor_id to None should succeed (clearing FK)."""
    vendor = _make_vendor(db)
    order = _make_order(db, vendor=vendor)

    resp = client.patch(
        f"/api/v1/orders/{order.id}",
        json={"vendor_id": None},
    )
    assert resp.status_code == 200


# ---- Vendors PATCH duplicate name ----


def test_patch_vendor_duplicate_name_returns_409(client, db):
    """PATCH vendor with name already taken by another vendor returns 409."""
    vendor1 = _make_vendor(db, name="Alpha")
    _make_vendor(db, name="Beta")

    resp = client.patch(
        f"/api/v1/vendors/{vendor1.id}",
        json={"name": "Beta"},
    )
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]


def test_patch_vendor_same_name_case_insensitive_returns_409(client, db):
    """PATCH vendor with same name but different case returns 409."""
    vendor1 = _make_vendor(db, name="Alpha")
    _make_vendor(db, name="Beta")

    resp = client.patch(
        f"/api/v1/vendors/{vendor1.id}",
        json={"name": "beta"},
    )
    assert resp.status_code == 409


def test_patch_vendor_keep_own_name_succeeds(client, db):
    """PATCH vendor keeping its own name (case-insensitive) succeeds."""
    vendor = _make_vendor(db, name="Alpha")

    resp = client.patch(
        f"/api/v1/vendors/{vendor.id}",
        json={"name": "alpha"},
    )
    assert resp.status_code == 200


def test_patch_vendor_rename_to_new_name_succeeds(client, db):
    """PATCH vendor with a new unique name succeeds."""
    vendor = _make_vendor(db, name="Alpha")

    resp = client.patch(
        f"/api/v1/vendors/{vendor.id}",
        json={"name": "Gamma"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Gamma"


# ---- Products PATCH FK validation ----


def test_patch_product_missing_vendor_returns_404(client, db):
    """PATCH product with non-existent vendor_id returns 404."""
    product = _make_product(db)

    resp = client.patch(
        f"/api/v1/products/{product.id}",
        json={"vendor_id": 99999},
    )
    assert resp.status_code == 404
    assert "Vendor" in resp.json()["detail"]


def test_patch_product_valid_vendor_succeeds(client, db):
    """PATCH product with valid vendor_id succeeds."""
    vendor1 = _make_vendor(db, name="Vendor A")
    vendor2 = _make_vendor(db, name="Vendor B")
    product = _make_product(db, vendor=vendor1)

    resp = client.patch(
        f"/api/v1/products/{product.id}",
        json={"vendor_id": vendor2.id},
    )
    assert resp.status_code == 200
    assert resp.json()["vendor_id"] == vendor2.id


def test_patch_product_clearing_vendor_id_succeeds(client, db):
    """PATCH product setting vendor_id to None should succeed (clearing FK)."""
    vendor = _make_vendor(db)
    product = _make_product(db, vendor=vendor)

    resp = client.patch(
        f"/api/v1/products/{product.id}",
        json={"vendor_id": None},
    )
    assert resp.status_code == 200
