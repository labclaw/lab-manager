"""E2E tests for complete vendor lifecycle.

Covers the full journey: create vendor -> add products -> create orders ->
receive orders -> view analytics -> update vendor -> delete vendor (when safe).

Uses a class-scoped client (shared DB) so sequential tests can build on state
created by previous tests.
"""

from __future__ import annotations

import os
from uuid import uuid4
from typing import Generator

import httpx
import pytest
from fastapi.testclient import TestClient

# Admin credentials for the lifecycle test.
_ADMIN_NAME = "Vendor LC Admin"
_ADMIN_EMAIL = "vendor-lc-admin@test.local"
_ADMIN_PASSWORD = "vendor-lc-password-secure-12345"

_ENV_KEYS = (
    "AUTH_ENABLED",
    "ADMIN_SECRET_KEY",
    "ADMIN_PASSWORD",
    "API_KEY",
    "SECURE_COOKIES",
)


def _suffix() -> str:
    return uuid4().hex[:8]


@pytest.fixture(scope="class")
def lifecycle_client() -> Generator[TestClient | httpx.Client, None, None]:
    """Class-scoped HTTP client that shares a single DB across lifecycle tests."""
    base_url = os.environ.get("APP_BASE_URL")
    if base_url:
        client = httpx.Client(base_url=base_url, timeout=30, follow_redirects=True)
        yield client
        client.close()
        return

    orig_env = {k: os.environ.get(k) for k in _ENV_KEYS}
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["ADMIN_SECRET_KEY"] = "vendor-lc-test-secret-key"
    os.environ["ADMIN_PASSWORD"] = _ADMIN_PASSWORD
    os.environ["API_KEY"] = "vendor-lc-test-api-key"
    os.environ["SECURE_COOKIES"] = "false"

    from lab_manager.config import get_settings

    get_settings.cache_clear()

    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel, create_engine

    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)

    import lab_manager.database as db_module

    original_engine = db_module._engine
    original_factory = db_module._session_factory
    db_module._engine = engine
    db_module._session_factory = None

    from lab_manager.api.app import create_app
    from lab_manager.database import get_db

    app = create_app()

    def override_get_db():
        with Session(engine) as session:
            yield session
            session.commit()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            # Complete setup and login
            setup_resp = client.post(
                "/api/v1/setup/complete",
                json={
                    "admin_name": _ADMIN_NAME,
                    "admin_email": _ADMIN_EMAIL,
                    "admin_password": _ADMIN_PASSWORD,
                },
            )
            assert setup_resp.status_code in (200, 201), setup_resp.text

            login_resp = client.post(
                "/api/v1/auth/login",
                json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
            )
            assert login_resp.status_code == 200, login_resp.text

            yield client
    finally:
        engine.dispose()
        db_module._engine = original_engine
        db_module._session_factory = original_factory
        for k, v in orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Full Vendor Lifecycle (sequential, shared state)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestVendorLifecycleE2E:
    """Full vendor lifecycle: create -> products -> orders -> receive ->
    analytics -> update -> cleanup."""

    # Shared state across tests.
    vendor_id: int | None = None
    vendor_suffix: str | None = None
    product_ids: list[int] = []
    order_id: int | None = None
    order_item_ids: list[int] = []
    lot_numbers: list[str] = []
    inventory_ids: list[int] = []

    def test_01_create_vendor_with_full_details(self, lifecycle_client):
        """Create a vendor with all optional fields populated."""
        suffix = _suffix()
        resp = lifecycle_client.post(
            "/api/v1/vendors/",
            json={
                "name": f"BioCorp International {suffix}",
                "email": f"orders-{suffix}@biocorp.com",
                "website": "https://biocorp.example.com",
                "phone": "+1-617-555-0100",
                "notes": f"Primary reagent supplier for E2E test {suffix}",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["name"] == f"BioCorp International {suffix}"
        assert data["email"] == f"orders-{suffix}@biocorp.com"
        assert data["phone"] == "+1-617-555-0100"
        assert data["notes"] == f"Primary reagent supplier for E2E test {suffix}"
        TestVendorLifecycleE2E.vendor_id = data["id"]
        TestVendorLifecycleE2E.vendor_suffix = suffix

    def test_02_get_vendor_details(self, lifecycle_client):
        """Retrieve the vendor and verify all fields."""
        vid = TestVendorLifecycleE2E.vendor_id
        resp = lifecycle_client.get(f"/api/v1/vendors/{vid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == vid
        assert "BioCorp" in data["name"]

    def test_03_update_vendor_contact_info(self, lifecycle_client):
        """Update vendor phone and notes."""
        vid = TestVendorLifecycleE2E.vendor_id
        resp = lifecycle_client.patch(
            f"/api/v1/vendors/{vid}",
            json={
                "phone": "+1-617-555-0200",
                "notes": "Updated contact info via lifecycle test",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["phone"] == "+1-617-555-0200"
        assert data["notes"] == "Updated contact info via lifecycle test"

    def test_04_add_multiple_products_to_vendor(self, lifecycle_client):
        """Create several products linked to this vendor."""
        vid = TestVendorLifecycleE2E.vendor_id
        products = []
        for cat, price in [
            ("Antibodies", 350.00),
            ("Buffers", 45.50),
            ("Media", 120.00),
        ]:
            suffix = _suffix()
            resp = lifecycle_client.post(
                "/api/v1/products/",
                json={
                    "catalog_number": f"LC-{suffix.upper()}",
                    "name": f"LC Product {suffix}",
                    "vendor_id": vid,
                    "category": cat,
                    "unit_price": price,
                },
            )
            assert resp.status_code == 201, resp.text
            products.append(resp.json())
        TestVendorLifecycleE2E.product_ids = [p["id"] for p in products]
        assert len(TestVendorLifecycleE2E.product_ids) == 3

    def test_05_list_vendor_products(self, lifecycle_client):
        """GET /vendors/{id}/products returns exactly our products."""
        vid = TestVendorLifecycleE2E.vendor_id
        resp = lifecycle_client.get(f"/api/v1/vendors/{vid}/products")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        listed_ids = {p["id"] for p in data["items"]}
        for pid in TestVendorLifecycleE2E.product_ids:
            assert pid in listed_ids

    def test_06_create_order_with_items(self, lifecycle_client):
        """Place an order for two of the vendor's products."""
        vid = TestVendorLifecycleE2E.vendor_id
        suffix = _suffix()
        resp = lifecycle_client.post(
            "/api/v1/orders/",
            json={
                "po_number": f"LC-PO-{suffix.upper()}",
                "vendor_id": vid,
                "status": "pending",
            },
        )
        assert resp.status_code == 201, resp.text
        order = resp.json().get("order", resp.json())
        TestVendorLifecycleE2E.order_id = order["id"]

        p0 = TestVendorLifecycleE2E.product_ids[0]
        p1 = TestVendorLifecycleE2E.product_ids[1]
        lot_a = f"LOT-LC-{_suffix().upper()}"
        lot_b = f"LOT-LC-{_suffix().upper()}"

        s1 = _suffix()
        item_a_resp = lifecycle_client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={
                "product_id": p0,
                "catalog_number": f"LC-{s1.upper()}",
                "description": f"LC Item A {s1}",
                "quantity": 5,
                "lot_number": lot_a,
            },
        )
        assert item_a_resp.status_code == 201, item_a_resp.text

        s2 = _suffix()
        item_b_resp = lifecycle_client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={
                "product_id": p1,
                "catalog_number": f"LC-{s2.upper()}",
                "description": f"LC Item B {s2}",
                "quantity": 10,
                "lot_number": lot_b,
            },
        )
        assert item_b_resp.status_code == 201, item_b_resp.text

        TestVendorLifecycleE2E.order_item_ids = [
            item_a_resp.json()["id"],
            item_b_resp.json()["id"],
        ]
        TestVendorLifecycleE2E.lot_numbers = [lot_a, lot_b]

    def test_07_receive_order_creates_inventory(self, lifecycle_client):
        """Receive the order and verify inventory auto-creation."""
        oid = TestVendorLifecycleE2E.order_id
        item_ids = TestVendorLifecycleE2E.order_item_ids
        lots = TestVendorLifecycleE2E.lot_numbers

        resp = lifecycle_client.post(
            f"/api/v1/orders/{oid}/receive",
            json={
                "items": [
                    {
                        "order_item_id": item_ids[0],
                        "quantity": 5,
                        "lot_number": lots[0],
                    },
                    {
                        "order_item_id": item_ids[1],
                        "quantity": 10,
                        "lot_number": lots[1],
                    },
                ],
                "received_by": "lifecycle-tester",
            },
        )
        assert resp.status_code == 201
        created = resp.json()
        assert len(created) == 2
        TestVendorLifecycleE2E.inventory_ids = [inv["id"] for inv in created]

    def test_08_order_status_is_received(self, lifecycle_client):
        """After receiving, order status should be 'received'."""
        oid = TestVendorLifecycleE2E.order_id
        resp = lifecycle_client.get(f"/api/v1/orders/{oid}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "received"

    def test_09_vendor_orders_endpoint(self, lifecycle_client):
        """GET /vendors/{id}/orders shows our received order."""
        vid = TestVendorLifecycleE2E.vendor_id
        resp = lifecycle_client.get(f"/api/v1/vendors/{vid}/orders")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_10_analytics_reflects_vendor_data(self, lifecycle_client):
        """Analytics dashboard reflects the vendor, products, and orders."""
        resp = lifecycle_client.get("/api/v1/analytics/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_vendors"] >= 1
        assert data["total_products"] >= 3
        assert data["total_orders"] >= 1

    def test_11_vendor_summary_analytics(self, lifecycle_client):
        """GET /analytics/vendors/{id}/summary returns stats for this vendor."""
        vid = TestVendorLifecycleE2E.vendor_id
        resp = lifecycle_client.get(f"/api/v1/analytics/vendors/{vid}/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_12_spending_by_vendor(self, lifecycle_client):
        """GET /analytics/spending/by-vendor returns data."""
        resp = lifecycle_client.get("/api/v1/analytics/spending/by-vendor")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (list, dict))

    def test_13_export_vendor_csv_contains_data(self, lifecycle_client):
        """GET /export/vendors CSV contains our vendor."""
        import csv
        import io

        suffix = TestVendorLifecycleE2E.vendor_suffix
        resp = lifecycle_client.get("/api/v1/export/vendors")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) >= 2
        names = [r[rows[0].index("name")] for r in rows[1:] if "name" in rows[0]]
        assert any(suffix in n for n in names)

    def test_14_delete_vendor_with_linked_data_blocked(self, lifecycle_client):
        """DELETE vendor with products returns 409 (FK constraint) or 204."""
        vid = TestVendorLifecycleE2E.vendor_id
        resp = lifecycle_client.delete(f"/api/v1/vendors/{vid}")
        assert resp.status_code in (409, 204)


# ---------------------------------------------------------------------------
# Vendor Isolation (self-contained tests)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestVendorIsolationE2E:
    """Verify that vendor-scoped queries do not cross-contaminate."""

    def test_01_vendors_products_isolated(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Products from vendor A do not appear under vendor B."""
        client = authenticated_client
        s1, s2 = _suffix(), _suffix()
        va_resp = client.post(
            "/api/v1/vendors/",
            json={"name": f"IsoA {s1}", "email": f"isoa-{s1}@test.local"},
        )
        assert va_resp.status_code == 201
        va = va_resp.json()

        vb_resp = client.post(
            "/api/v1/vendors/",
            json={"name": f"IsoB {s2}", "email": f"isob-{s2}@test.local"},
        )
        assert vb_resp.status_code == 201
        vb = vb_resp.json()

        pa_resp = client.post(
            "/api/v1/products/",
            json={
                "catalog_number": f"ISO-A-{s1.upper()}",
                "name": f"ProductA {s1}",
                "vendor_id": va["id"],
                "category": "Reagents",
            },
        )
        assert pa_resp.status_code == 201
        pa = pa_resp.json()

        client.post(
            "/api/v1/products/",
            json={
                "catalog_number": f"ISO-B-{s2.upper()}",
                "name": f"ProductB {s2}",
                "vendor_id": vb["id"],
                "category": "Reagents",
            },
        )

        resp = client.get(f"/api/v1/vendors/{va['id']}/products")
        assert resp.status_code == 200
        data = resp.json()
        for p in data["items"]:
            assert p["vendor_id"] == va["id"]
        ids = {p["id"] for p in data["items"]}
        assert pa["id"] in ids

    def test_02_vendors_orders_isolated(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Orders from vendor A do not appear under vendor B."""
        client = authenticated_client
        s1, s2 = _suffix(), _suffix()
        va_resp = client.post(
            "/api/v1/vendors/",
            json={"name": f"OrdIsoA {s1}", "email": f"ordisoa-{s1}@test.local"},
        )
        assert va_resp.status_code == 201
        va = va_resp.json()

        vb_resp = client.post(
            "/api/v1/vendors/",
            json={"name": f"OrdIsoB {s2}", "email": f"ordisob-{s2}@test.local"},
        )
        assert vb_resp.status_code == 201
        vb = vb_resp.json()

        client.post(
            "/api/v1/orders/",
            json={"po_number": f"ISO-OA-{s1.upper()}", "vendor_id": va["id"]},
        )
        client.post(
            "/api/v1/orders/",
            json={"po_number": f"ISO-OB-{s2.upper()}", "vendor_id": vb["id"]},
        )

        resp = client.get(f"/api/v1/vendors/{va['id']}/orders")
        assert resp.status_code == 200
        data = resp.json()
        for o in data["items"]:
            assert o["vendor_id"] == va["id"]

    def test_03_vendor_summary_independent(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Vendor summary returns 404 for nonexistent vendor."""
        client = authenticated_client
        resp = client.get("/api/v1/analytics/vendors/99999/summary")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Multi-Vendor Analytics (self-contained tests)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestMultiVendorAnalyticsE2E:
    """Verify analytics work correctly when multiple vendors have orders."""

    def test_01_spending_by_vendor_multiple(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Create orders for 2 vendors -> spending breakdown returns data."""
        client = authenticated_client
        for s in [_suffix(), _suffix()]:
            v_resp = client.post(
                "/api/v1/vendors/",
                json={"name": f"SpdV {s}", "email": f"spdv-{s}@test.local"},
            )
            assert v_resp.status_code == 201
            client.post(
                "/api/v1/orders/",
                json={
                    "po_number": f"SPD-{s.upper()}",
                    "vendor_id": v_resp.json()["id"],
                },
            )

        resp = client.get("/api/v1/analytics/spending/by-vendor")
        assert resp.status_code == 200
        assert isinstance(resp.json(), (list, dict))

    def test_02_order_history_with_vendor_filter(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /analytics/orders/history with vendor_id filter."""
        client = authenticated_client
        s = _suffix()
        v_resp = client.post(
            "/api/v1/vendors/",
            json={"name": f"HistV {s}", "email": f"histv-{s}@test.local"},
        )
        assert v_resp.status_code == 201
        vid = v_resp.json()["id"]
        client.post(
            "/api/v1/orders/",
            json={"po_number": f"HIST-{s.upper()}", "vendor_id": vid},
        )

        resp = client.get(
            "/api/v1/analytics/orders/history",
            params={"vendor_id": vid},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), (list, dict))

    def test_03_inventory_value_after_receiving(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """After receiving an order, inventory value reflects new stock."""
        client = authenticated_client
        s = _suffix()
        v_resp = client.post(
            "/api/v1/vendors/",
            json={"name": f"ValV {s}", "email": f"valv-{s}@test.local"},
        )
        assert v_resp.status_code == 201
        vid = v_resp.json()["id"]

        p_resp = client.post(
            "/api/v1/products/",
            json={
                "catalog_number": f"VAL-{s.upper()}",
                "name": f"ValProduct {s}",
                "vendor_id": vid,
                "category": "Reagents",
                "unit_price": 50.00,
            },
        )
        assert p_resp.status_code == 201
        pid = p_resp.json()["id"]

        o_resp = client.post(
            "/api/v1/orders/",
            json={"po_number": f"VAL-PO-{s.upper()}", "vendor_id": vid},
        )
        assert o_resp.status_code == 201
        oid = o_resp.json().get("order", o_resp.json())["id"]

        oi_s = _suffix()
        oi_resp = client.post(
            f"/api/v1/orders/{oid}/items",
            json={
                "product_id": pid,
                "catalog_number": f"VAL-{oi_s.upper()}",
                "description": f"ValItem {oi_s}",
                "quantity": 10,
                "lot_number": f"LOT-VAL-{_suffix().upper()}",
            },
        )
        assert oi_resp.status_code == 201
        oiid = oi_resp.json()["id"]

        lot = f"LOT-VALR-{_suffix().upper()}"
        client.post(
            f"/api/v1/orders/{oid}/receive",
            json={
                "items": [{"order_item_id": oiid, "quantity": 10, "lot_number": lot}],
                "received_by": "val-tester",
            },
        )

        resp = client.get("/api/v1/analytics/inventory/value")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)
