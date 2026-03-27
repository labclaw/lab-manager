"""Tests for inventory FK validation on create.

Verifies that POST /api/v1/inventory/ returns proper 404/422 errors
when referencing non-existent product_id, location_id, or order_item_id,
instead of a raw 500 IntegrityError from the database.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.models.product import Product


@pytest.fixture
def inv_engine():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def inv_db(inv_engine):
    with Session(inv_engine) as session:
        yield session


@pytest.fixture
def inv_client(inv_db, monkeypatch):
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
        yield inv_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        with patch("lab_manager.api.routes.inventory.index_inventory_record"):
            yield c

    get_settings.cache_clear()


def _make_product(inv_db, **kwargs):
    defaults = dict(
        catalog_number="CAT-001",
        name="Test Product",
        vendor_id=1,
        category="reagent",
    )
    defaults.update(kwargs)
    p = Product(**defaults)
    inv_db.add(p)
    inv_db.flush()
    inv_db.refresh(p)
    return p


def test_create_inventory_missing_product_returns_404(inv_client, inv_db):
    """POST with non-existent product_id returns 404, not 500."""
    resp = inv_client.post(
        "/api/v1/inventory/",
        json={"product_id": 99999, "quantity_on_hand": "5", "unit": "mL"},
    )
    assert resp.status_code == 404
    assert "Product" in resp.json()["detail"]


def test_create_inventory_missing_location_returns_404(inv_client, inv_db):
    """POST with non-existent location_id returns 404, not 500."""
    product = _make_product(inv_db)
    resp = inv_client.post(
        "/api/v1/inventory/",
        json={
            "product_id": product.id,
            "location_id": 99999,
            "quantity_on_hand": "5",
            "unit": "mL",
        },
    )
    assert resp.status_code == 404
    assert "Location" in resp.json()["detail"]


def test_create_inventory_missing_order_item_returns_404(inv_client, inv_db):
    """POST with non-existent order_item_id returns 404, not 500."""
    product = _make_product(inv_db)
    resp = inv_client.post(
        "/api/v1/inventory/",
        json={
            "product_id": product.id,
            "order_item_id": 99999,
            "quantity_on_hand": "5",
            "unit": "mL",
        },
    )
    assert resp.status_code == 404
    assert "Order item" in resp.json()["detail"]


def test_create_inventory_valid_product_succeeds(inv_client, inv_db):
    """POST with valid product_id creates item successfully."""
    product = _make_product(inv_db)
    resp = inv_client.post(
        "/api/v1/inventory/",
        json={
            "product_id": product.id,
            "quantity_on_hand": "10",
            "unit": "mL",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["product_id"] == product.id
    # SQLite stores Decimal as string '10.0000'; compare loosely
    assert float(data["quantity_on_hand"]) == 10.0
