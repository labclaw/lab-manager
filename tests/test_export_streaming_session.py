"""Tests for export endpoints: verify CSV export works after session closes.

The get_db() middleware closes the session after the route handler returns.
Lazy streaming via yield_per() would fail with a closed-session error because
the generator is consumed during StreamingResponse iteration — after the
session is already closed.  The fix eagerly materializes all rows inside the
handler so the returned response is self-contained.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor


@pytest.fixture
def export_engine():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def export_db(export_engine):
    with Session(export_engine) as session:
        yield session


@pytest.fixture
def export_client(export_db, monkeypatch):
    import os

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db
    from lab_manager.config import get_settings

    os.environ["AUTH_ENABLED"] = "false"
    os.environ["ADMIN_SECRET_KEY"] = "test-key"
    get_settings.cache_clear()

    app = create_app()

    def override_get_db():
        yield export_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()


def _seed_products(export_db, count=5):
    for i in range(1, count + 1):
        p = Product(
            catalog_number=f"CAT-{i:03d}",
            name=f"Product {i}",
            vendor_id=1,
            category="reagent",
        )
        export_db.add(p)
    export_db.flush()


def _seed_vendors(export_db, count=3):
    for i in range(1, count + 1):
        v = Vendor(name=f"Vendor {i}", email=f"v{i}@example.com")
        export_db.add(v)
    export_db.flush()


def test_export_products_returns_csv(export_client, export_db):
    """GET /api/v1/export/products.csv returns valid CSV with product data."""
    _seed_products(export_db, 3)
    resp = export_client.get("/api/v1/export/products.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    body = resp.text
    lines = body.strip().split("\n")
    # header + 3 data rows
    assert len(lines) == 4
    assert "catalog_number" in lines[0]
    assert "CAT-001" in lines[1]


def test_export_products_empty(export_client, export_db):
    """GET /api/v1/export/products.csv returns empty body when no products."""
    resp = export_client.get("/api/v1/export/products.csv")
    assert resp.status_code == 200
    assert resp.text == ""


def test_export_vendors_returns_csv(export_client, export_db):
    """GET /api/v1/export/vendors.csv returns valid CSV with vendor data."""
    _seed_vendors(export_db, 2)
    resp = export_client.get("/api/v1/export/vendors.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    body = resp.text
    lines = body.strip().split("\n")
    # header + 2 data rows
    assert len(lines) == 3
    assert "name" in lines[0]
    assert "Vendor 1" in lines[1]


def test_export_vendors_empty(export_client, export_db):
    """GET /api/v1/export/vendors.csv returns empty body when no vendors."""
    resp = export_client.get("/api/v1/export/vendors.csv")
    assert resp.status_code == 200
    assert resp.text == ""


def test_export_products_alias_route(export_client, export_db):
    """GET /api/v1/export/products (no .csv) also works."""
    _seed_products(export_db, 1)
    resp = export_client.get("/api/v1/export/products")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "CAT-001" in resp.text


def test_export_vendors_alias_route(export_client, export_db):
    """GET /api/v1/export/vendors (no .csv) also works."""
    _seed_vendors(export_db, 1)
    resp = export_client.get("/api/v1/export/vendors")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "Vendor 1" in resp.text
