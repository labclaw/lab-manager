"""Tests for RBAC permission guards on route endpoints (Phase C).

Verifies that protected endpoints enforce the correct permissions:
- visitor/undergrad (view-only) gets 403 on write endpoints
- PI (all permissions) gets 200/201/204 on all endpoints
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("MEILISEARCH_URL", "http://localhost:7700")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("ADMIN_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password-not-for-production")
os.environ.setdefault("UPLOAD_DIR", "/tmp/lab-manager-test-uploads")

from lab_manager.config import get_settings  # noqa: E402

get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _engine():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def _session(_engine):
    with Session(_engine) as session:
        yield session


def _make_client(session: Session, role: str, role_level: int) -> TestClient:
    """Build a TestClient whose staff has *role*.

    Patches get_current_staff so that require_permission() sees our
    chosen role instead of the default pi from auth middleware.
    """
    os.environ["AUTH_ENABLED"] = "false"
    get_settings.cache_clear()

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), {
        "id": 1,
        "name": f"Test {role}",
        "email": None,
        "role": role,
        "role_level": role_level,
    }


def _staff_dict(role: str, role_level: int) -> dict:
    return {
        "id": 1,
        "name": f"Test {role}",
        "email": None,
        "role": role,
        "role_level": role_level,
    }


PI = _staff_dict("pi", 0)
VISITOR = _staff_dict("visitor", 4)


@pytest.fixture
def _app(_session):
    """Create a single test app with DB override."""
    os.environ["AUTH_ENABLED"] = "false"
    get_settings.cache_clear()

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield _session

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture
def pi_client(_app):
    """Client where get_current_staff returns PI."""
    with patch("lab_manager.api.auth.get_current_staff", return_value=PI):
        with TestClient(_app) as c:
            yield c


@pytest.fixture
def visitor_client(_app):
    """Client where get_current_staff returns visitor."""
    with patch("lab_manager.api.auth.get_current_staff", return_value=VISITOR):
        with TestClient(_app) as c:
            yield c


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_vendor(session: Session) -> int:
    from lab_manager.models.vendor import Vendor

    v = Vendor(name="Test Vendor")
    session.add(v)
    session.flush()
    session.refresh(v)
    return v.id


def _seed_product(session: Session, vendor_id: int | None = None) -> int:
    from lab_manager.models.product import Product

    p = Product(
        catalog_number="TEST-001",
        name="Test Product",
        vendor_id=vendor_id,
        category="Reagent",
    )
    session.add(p)
    session.flush()
    session.refresh(p)
    return p.id


def _seed_order(session: Session) -> int:
    from lab_manager.models.order import Order

    o = Order(status="pending")
    session.add(o)
    session.flush()
    session.refresh(o)
    return o.id


def _seed_inventory(session: Session, product_id: int) -> int:
    from lab_manager.models.inventory import InventoryItem

    item = InventoryItem(
        product_id=product_id,
        quantity_on_hand=10,
        unit="ea",
        status="available",
    )
    session.add(item)
    session.flush()
    session.refresh(item)
    return item.id


def _seed_document(session: Session) -> int:
    from lab_manager.models.document import Document

    doc = Document(
        file_path="/tmp/test.pdf",
        file_name="test.pdf",
        status="needs_review",
    )
    session.add(doc)
    session.flush()
    session.refresh(doc)
    return doc.id


def _seed_equipment(session: Session) -> int:
    from lab_manager.models.equipment import Equipment

    eq = Equipment(name="Test Microscope", status="active")
    session.add(eq)
    session.flush()
    session.refresh(eq)
    return eq.id


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


class TestOrderGuards:
    def test_visitor_cannot_create_order(self, visitor_client):
        resp = visitor_client.post("/api/v1/orders/", json={"status": "pending"})
        assert resp.status_code == 403

    def test_pi_can_create_order(self, pi_client):
        resp = pi_client.post("/api/v1/orders/", json={"status": "pending"})
        assert resp.status_code == 201

    def test_visitor_cannot_update_order(self, visitor_client, _session):
        oid = _seed_order(_session)
        resp = visitor_client.patch(f"/api/v1/orders/{oid}", json={"status": "pending"})
        assert resp.status_code == 403

    def test_pi_can_update_order(self, pi_client, _session):
        oid = _seed_order(_session)
        resp = pi_client.patch(f"/api/v1/orders/{oid}", json={"status": "pending"})
        assert resp.status_code == 200

    def test_visitor_cannot_delete_order(self, visitor_client, _session):
        oid = _seed_order(_session)
        resp = visitor_client.delete(f"/api/v1/orders/{oid}")
        assert resp.status_code == 403

    def test_pi_can_delete_order(self, pi_client, _session):
        oid = _seed_order(_session)
        resp = pi_client.delete(f"/api/v1/orders/{oid}")
        assert resp.status_code == 204

    def test_visitor_can_list_orders(self, visitor_client):
        """GET /orders/ has no guard -- read is allowed for all authenticated users."""
        resp = visitor_client.get("/api/v1/orders/")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class TestDocumentGuards:
    def test_visitor_cannot_delete_document(self, visitor_client, _session):
        did = _seed_document(_session)
        resp = visitor_client.delete(f"/api/v1/documents/{did}")
        assert resp.status_code == 403

    def test_pi_can_delete_document(self, pi_client, _session):
        did = _seed_document(_session)
        resp = pi_client.delete(f"/api/v1/documents/{did}")
        assert resp.status_code == 204

    def test_visitor_cannot_review_document(self, visitor_client, _session):
        did = _seed_document(_session)
        resp = visitor_client.post(
            f"/api/v1/documents/{did}/review",
            json={"action": "approve", "reviewed_by": "test"},
        )
        assert resp.status_code == 403

    def test_visitor_can_list_documents(self, visitor_client):
        resp = visitor_client.get("/api/v1/documents/")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


class TestInventoryGuards:
    def test_visitor_cannot_create_inventory(self, visitor_client, _session):
        vid = _seed_vendor(_session)
        pid = _seed_product(_session, vid)
        resp = visitor_client.post(
            "/api/v1/inventory/",
            json={"product_id": pid, "quantity_on_hand": 5, "status": "available"},
        )
        assert resp.status_code == 403

    def test_pi_can_create_inventory(self, pi_client, _session):
        vid = _seed_vendor(_session)
        pid = _seed_product(_session, vid)
        resp = pi_client.post(
            "/api/v1/inventory/",
            json={"product_id": pid, "quantity_on_hand": 5, "status": "available"},
        )
        assert resp.status_code == 201

    def test_visitor_cannot_consume(self, visitor_client, _session):
        vid = _seed_vendor(_session)
        pid = _seed_product(_session, vid)
        iid = _seed_inventory(_session, pid)
        resp = visitor_client.post(
            f"/api/v1/inventory/{iid}/consume",
            json={"quantity": 1, "consumed_by": "test"},
        )
        assert resp.status_code == 403

    def test_visitor_cannot_delete_inventory(self, visitor_client, _session):
        vid = _seed_vendor(_session)
        pid = _seed_product(_session, vid)
        iid = _seed_inventory(_session, pid)
        resp = visitor_client.delete(f"/api/v1/inventory/{iid}")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class TestAnalyticsGuards:
    def test_visitor_cannot_view_analytics(self, visitor_client):
        resp = visitor_client.get("/api/v1/analytics/dashboard")
        assert resp.status_code == 403

    def test_pi_can_view_analytics(self, pi_client):
        resp = pi_client.get("/api/v1/analytics/dashboard")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


class TestAuditGuards:
    def test_visitor_cannot_view_audit(self, visitor_client):
        resp = visitor_client.get("/api/v1/audit/")
        assert resp.status_code == 403

    def test_pi_can_view_audit(self, pi_client):
        resp = pi_client.get("/api/v1/audit/")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class TestExportGuards:
    def test_visitor_cannot_export(self, visitor_client):
        resp = visitor_client.get("/api/v1/export/inventory")
        assert resp.status_code == 403

    def test_pi_can_export_inventory(self, pi_client):
        resp = pi_client.get("/api/v1/export/inventory")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------


class TestEquipmentGuards:
    def test_visitor_cannot_create_equipment(self, visitor_client):
        resp = visitor_client.post("/api/v1/equipment/", json={"name": "Microscope"})
        assert resp.status_code == 403

    def test_pi_can_create_equipment(self, pi_client):
        resp = pi_client.post("/api/v1/equipment/", json={"name": "Microscope"})
        assert resp.status_code == 201

    def test_visitor_cannot_delete_equipment(self, visitor_client, _session):
        eid = _seed_equipment(_session)
        resp = visitor_client.delete(f"/api/v1/equipment/{eid}")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Vendors
# ---------------------------------------------------------------------------


class TestVendorGuards:
    def test_visitor_cannot_create_vendor(self, visitor_client):
        resp = visitor_client.post("/api/v1/vendors/", json={"name": "NewVendor"})
        assert resp.status_code == 403

    def test_pi_can_create_vendor(self, pi_client):
        resp = pi_client.post("/api/v1/vendors/", json={"name": "NewVendor"})
        assert resp.status_code == 201

    def test_visitor_cannot_update_vendor(self, visitor_client, _session):
        vid = _seed_vendor(_session)
        resp = visitor_client.patch(f"/api/v1/vendors/{vid}", json={"name": "Updated"})
        assert resp.status_code == 403

    def test_visitor_cannot_delete_vendor(self, visitor_client, _session):
        vid = _seed_vendor(_session)
        resp = visitor_client.delete(f"/api/v1/vendors/{vid}")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


class TestProductGuards:
    def test_visitor_cannot_create_product(self, visitor_client):
        resp = visitor_client.post(
            "/api/v1/products/",
            json={"catalog_number": "X-1", "name": "Product X"},
        )
        assert resp.status_code == 403

    def test_pi_can_create_product(self, pi_client):
        resp = pi_client.post(
            "/api/v1/products/",
            json={"catalog_number": "X-1", "name": "Product X"},
        )
        assert resp.status_code == 201

    def test_visitor_cannot_update_product(self, visitor_client, _session):
        vid = _seed_vendor(_session)
        pid = _seed_product(_session, vid)
        resp = visitor_client.patch(f"/api/v1/products/{pid}", json={"name": "Updated"})
        assert resp.status_code == 403

    def test_visitor_cannot_delete_product(self, visitor_client, _session):
        vid = _seed_vendor(_session)
        pid = _seed_product(_session, vid)
        resp = visitor_client.delete(f"/api/v1/products/{pid}")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Ask (AI Q&A)
# ---------------------------------------------------------------------------


class TestAskGuards:
    def test_visitor_cannot_ask(self, visitor_client):
        resp = visitor_client.post(
            "/api/v1/ask", json={"question": "How many reagents?"}
        )
        assert resp.status_code == 403

    def test_visitor_cannot_ask_get(self, visitor_client):
        resp = visitor_client.get("/api/v1/ask?q=test")
        assert resp.status_code == 403
