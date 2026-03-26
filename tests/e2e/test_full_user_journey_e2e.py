"""E2E test: Complete user journey from first-time setup to daily operations.

This is the "golden path" test that proves the system works end-to-end.
A single ordered test class runs sequentially, simulating a real user's
first-time experience through daily lab management tasks.

Tests are numbered to enforce execution order. Each test builds on state
created by previous tests, stored as class variables.
"""

from __future__ import annotations

import os
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

# Admin credentials — same as conftest but defined locally so we control
# the full setup flow ourselves.
_ADMIN_NAME = "Journey Test Admin"
_ADMIN_EMAIL = "journey-admin@test.local"
_ADMIN_PASSWORD = "journey-test-password-secure-12345"

# Unique suffix for this test run to avoid collisions.
_SUFFIX = uuid4().hex[:8]

# Environment keys that affect test setup.
_ENV_KEYS = (
    "AUTH_ENABLED",
    "ADMIN_SECRET_KEY",
    "ADMIN_PASSWORD",
    "API_KEY",
    "SECURE_COOKIES",
)


@pytest.fixture(scope="class")
def journey_client() -> TestClient | httpx.Client:
    """Class-scoped HTTP client that shares a single DB across all journey tests.

    Unlike the function-scoped e2e_client, this fixture persists throughout
    the entire TestFullUserJourney class so that sequential tests can build
    on each other's state.
    """
    base_url = os.environ.get("APP_BASE_URL")
    if base_url:
        client = httpx.Client(base_url=base_url, timeout=30, follow_redirects=True)
        yield client
        client.close()
        return

    # Save originals for restoration.
    orig_env = {k: os.environ.get(k) for k in _ENV_KEYS}

    # Configure test environment with auth enabled.
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["ADMIN_SECRET_KEY"] = "journey-test-secret-key-12345"
    os.environ["ADMIN_PASSWORD"] = _ADMIN_PASSWORD
    os.environ["API_KEY"] = "journey-test-api-key"
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

    # Import models to register them with SQLModel metadata.
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)

    # Override database engine for the app.
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


@pytest.mark.e2e
class TestFullUserJourney:
    """Complete user journey: setup -> login -> CRUD -> lifecycle -> analytics -> logout.

    Tests are numbered to enforce sequential execution. Each test stores
    IDs and state as class variables for cross-test reference.
    """

    # Shared state across tests.
    vendor_id: int | None = None
    product_ids: list[int] = []
    order_id: int | None = None
    order_item_ids: list[int] = []
    inventory_item_id: int | None = None

    # -----------------------------------------------------------------------
    # 1. First-run setup
    # -----------------------------------------------------------------------

    def test_01_setup_status_needs_setup(self, journey_client):
        """GET /api/v1/setup/status should indicate setup is needed on fresh DB."""
        resp = journey_client.get("/api/v1/setup/status")
        assert resp.status_code == 200, f"Setup status failed: {resp.text}"
        data = resp.json()
        assert "needs_setup" in data, f"Missing needs_setup key: {data}"
        assert data["needs_setup"] is True, f"Expected needs_setup=True: {data}"

    def test_02_setup_complete(self, journey_client):
        """POST /api/v1/setup/complete creates admin account on first run."""
        resp = journey_client.post(
            "/api/v1/setup/complete",
            json={
                "admin_name": _ADMIN_NAME,
                "admin_email": _ADMIN_EMAIL,
                "admin_password": _ADMIN_PASSWORD,
            },
        )
        assert resp.status_code == 200, f"Setup complete failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "ok", f"Setup status not ok: {data}"

    def test_03_setup_already_completed(self, journey_client):
        """POST /api/v1/setup/complete returns 409 when admin already exists."""
        resp = journey_client.post(
            "/api/v1/setup/complete",
            json={
                "admin_name": "Another Admin",
                "admin_email": "other@test.local",
                "admin_password": "another-password-12345",
            },
        )
        assert resp.status_code == 409, f"Expected 409 Conflict: {resp.text}"

    def test_04_setup_status_no_longer_needed(self, journey_client):
        """GET /api/v1/setup/status should indicate setup is complete."""
        resp = journey_client.get("/api/v1/setup/status")
        assert resp.status_code == 200, f"Setup status failed: {resp.text}"
        data = resp.json()
        assert data["needs_setup"] is False, f"Expected needs_setup=False: {data}"

    # -----------------------------------------------------------------------
    # 2. Authentication
    # -----------------------------------------------------------------------

    def test_05_login_wrong_password(self, journey_client):
        """POST /api/v1/auth/login with wrong password returns 401."""
        resp = journey_client.post(
            "/api/v1/auth/login",
            json={"email": _ADMIN_EMAIL, "password": "wrong-password"},
        )
        assert resp.status_code == 401, f"Expected 401: {resp.text}"

    def test_06_login_nonexistent_user(self, journey_client):
        """POST /api/v1/auth/login with unknown email returns 401."""
        resp = journey_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.local", "password": _ADMIN_PASSWORD},
        )
        assert resp.status_code == 401, f"Expected 401: {resp.text}"

    def test_07_login_success(self, journey_client):
        """POST /api/v1/auth/login with correct credentials sets session cookie."""
        resp = journey_client.post(
            "/api/v1/auth/login",
            json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
        )
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "ok", f"Login status not ok: {data}"
        assert "user" in data, f"Missing user in login response: {data}"
        assert data["user"]["name"] == _ADMIN_NAME

    def test_08_auth_me(self, journey_client):
        """GET /api/v1/auth/me returns current user info from session cookie."""
        resp = journey_client.get("/api/v1/auth/me")
        assert resp.status_code == 200, f"Auth me failed: {resp.text}"
        data = resp.json()
        assert "user" in data, f"Missing user in auth/me response: {data}"
        user = data["user"]
        assert user["name"] == _ADMIN_NAME
        assert user["email"] == _ADMIN_EMAIL
        assert user["role"] == "pi"

    # -----------------------------------------------------------------------
    # 3. Config & Health
    # -----------------------------------------------------------------------

    def test_09_config(self, journey_client):
        """GET /api/v1/config returns lab configuration."""
        resp = journey_client.get("/api/v1/config")
        assert resp.status_code == 200, f"Config failed: {resp.text}"
        data = resp.json()
        assert "lab_name" in data, f"Missing lab_name: {data}"
        assert "version" in data, f"Missing version: {data}"
        assert isinstance(data["version"], str)

    def test_10_health(self, journey_client):
        """GET /api/health returns service status."""
        resp = journey_client.get("/api/health")
        # Accept 200 (all ok) or 503 (degraded, e.g. meilisearch not running).
        assert resp.status_code in (200, 503), f"Health check failed: {resp.text}"
        data = resp.json()
        assert "status" in data, f"Missing status: {data}"
        assert data["status"] in ("ok", "degraded")
        assert "services" in data, f"Missing services: {data}"
        # PostgreSQL (or SQLite in tests) should always be ok.
        assert data["services"]["postgresql"] == "ok"

    # -----------------------------------------------------------------------
    # 4. Vendor CRUD
    # -----------------------------------------------------------------------

    def test_11_create_vendor(self, journey_client):
        """POST /api/v1/vendors/ creates a new vendor."""
        resp = journey_client.post(
            "/api/v1/vendors/",
            json={
                "name": f"Sigma-Aldrich {_SUFFIX}",
                "email": f"orders-{_SUFFIX}@sigma.com",
                "website": "https://www.sigmaaldrich.com",
                "phone": "+1-800-325-3010",
                "notes": "Primary chemical supplier",
            },
        )
        assert resp.status_code == 201, f"Create vendor failed: {resp.text}"
        data = resp.json()
        assert "id" in data
        assert data["name"] == f"Sigma-Aldrich {_SUFFIX}"
        assert data["email"] == f"orders-{_SUFFIX}@sigma.com"
        assert data["website"] == "https://www.sigmaaldrich.com"
        TestFullUserJourney.vendor_id = data["id"]

    def test_12_get_vendor(self, journey_client):
        """GET /api/v1/vendors/{id} retrieves vendor details."""
        vid = TestFullUserJourney.vendor_id
        assert vid is not None, "Vendor not created"

        resp = journey_client.get(f"/api/v1/vendors/{vid}")
        assert resp.status_code == 200, f"Get vendor failed: {resp.text}"
        data = resp.json()
        assert data["id"] == vid
        assert data["name"] == f"Sigma-Aldrich {_SUFFIX}"

    def test_13_list_vendors(self, journey_client):
        """GET /api/v1/vendors/ returns paginated vendor list."""
        resp = journey_client.get("/api/v1/vendors/")
        assert resp.status_code == 200, f"List vendors failed: {resp.text}"
        data = resp.json()
        assert "items" in data, f"Missing items in paginated response: {data}"
        assert "total" in data
        assert data["total"] >= 1
        vendor_ids = [v["id"] for v in data["items"]]
        assert TestFullUserJourney.vendor_id in vendor_ids

    def test_14_vendor_not_found(self, journey_client):
        """GET /api/v1/vendors/99999 returns 404."""
        resp = journey_client.get("/api/v1/vendors/99999")
        assert resp.status_code == 404, f"Expected 404: {resp.text}"

    # -----------------------------------------------------------------------
    # 5. Product CRUD
    # -----------------------------------------------------------------------

    def test_15_create_product_a(self, journey_client):
        """POST /api/v1/products/ creates first product."""
        vid = TestFullUserJourney.vendor_id
        assert vid is not None, "Vendor not created"

        resp = journey_client.post(
            "/api/v1/products/",
            json={
                "catalog_number": f"A1234-{_SUFFIX}",
                "name": f"Acetonitrile HPLC Grade {_SUFFIX}",
                "vendor_id": vid,
                "category": "Solvents",
                "unit": "L",
                "storage_temp": "RT",
                "cas_number": "75-05-8",
            },
        )
        assert resp.status_code == 201, f"Create product A failed: {resp.text}"
        data = resp.json()
        assert data["catalog_number"] == f"A1234-{_SUFFIX}"
        assert data["vendor_id"] == vid
        assert data["cas_number"] == "75-05-8"
        TestFullUserJourney.product_ids.append(data["id"])

    def test_16_create_product_b(self, journey_client):
        """POST /api/v1/products/ creates second product."""
        vid = TestFullUserJourney.vendor_id
        resp = journey_client.post(
            "/api/v1/products/",
            json={
                "catalog_number": f"T2345-{_SUFFIX}",
                "name": f"TRIzol Reagent {_SUFFIX}",
                "vendor_id": vid,
                "category": "Reagents",
                "unit": "mL",
                "storage_temp": "4C",
                "hazard_info": "Corrosive, toxic",
            },
        )
        assert resp.status_code == 201, f"Create product B failed: {resp.text}"
        data = resp.json()
        assert data["catalog_number"] == f"T2345-{_SUFFIX}"
        assert data["hazard_info"] == "Corrosive, toxic"
        TestFullUserJourney.product_ids.append(data["id"])

    def test_17_create_product_c(self, journey_client):
        """POST /api/v1/products/ creates third product."""
        vid = TestFullUserJourney.vendor_id
        resp = journey_client.post(
            "/api/v1/products/",
            json={
                "catalog_number": f"P3456-{_SUFFIX}",
                "name": f"PBS Buffer 10X {_SUFFIX}",
                "vendor_id": vid,
                "category": "Buffers",
                "unit": "mL",
            },
        )
        assert resp.status_code == 201, f"Create product C failed: {resp.text}"
        TestFullUserJourney.product_ids.append(resp.json()["id"])

    def test_18_duplicate_catalog_number_rejected(self, journey_client):
        """POST /api/v1/products/ with duplicate catalog_number+vendor returns 409."""
        vid = TestFullUserJourney.vendor_id
        resp = journey_client.post(
            "/api/v1/products/",
            json={
                "catalog_number": f"A1234-{_SUFFIX}",
                "name": "Duplicate Product",
                "vendor_id": vid,
            },
        )
        assert resp.status_code == 409, (
            f"Expected 409 Conflict for duplicate: {resp.text}"
        )

    def test_19_list_products_by_vendor(self, journey_client):
        """GET /api/v1/products/?vendor_id=... filters by vendor."""
        vid = TestFullUserJourney.vendor_id
        resp = journey_client.get("/api/v1/products/", params={"vendor_id": vid})
        assert resp.status_code == 200, f"List products failed: {resp.text}"
        data = resp.json()
        assert data["total"] >= 3, f"Expected at least 3 products: {data}"
        for item in data["items"]:
            assert item["vendor_id"] == vid

    def test_20_get_product(self, journey_client):
        """GET /api/v1/products/{id} retrieves product details."""
        pid = TestFullUserJourney.product_ids[0]
        resp = journey_client.get(f"/api/v1/products/{pid}")
        assert resp.status_code == 200, f"Get product failed: {resp.text}"
        data = resp.json()
        assert data["id"] == pid
        assert data["catalog_number"] == f"A1234-{_SUFFIX}"

    # -----------------------------------------------------------------------
    # 6. Order creation with items
    # -----------------------------------------------------------------------

    def test_21_create_order(self, journey_client):
        """POST /api/v1/orders/ creates a new order."""
        vid = TestFullUserJourney.vendor_id
        resp = journey_client.post(
            "/api/v1/orders/",
            json={
                "po_number": f"PO-{_SUFFIX}",
                "vendor_id": vid,
                "status": "pending",
            },
        )
        assert resp.status_code == 201, f"Create order failed: {resp.text}"
        data = resp.json()
        # Handle duplicate warning wrapper.
        order = data.get("order", data)
        assert "id" in order, f"Missing id in order: {order}"
        assert order["po_number"] == f"PO-{_SUFFIX}"
        assert order["status"] == "pending"
        TestFullUserJourney.order_id = order["id"]

    def test_22_add_order_item_1(self, journey_client):
        """POST /api/v1/orders/{id}/items adds first item."""
        oid = TestFullUserJourney.order_id
        pid = TestFullUserJourney.product_ids[0]
        assert oid is not None and pid is not None

        resp = journey_client.post(
            f"/api/v1/orders/{oid}/items",
            json={
                "product_id": pid,
                "catalog_number": f"A1234-{_SUFFIX}",
                "quantity": 5,
                "unit_price": 120.50,
                "unit": "L",
            },
        )
        assert resp.status_code == 201, f"Add order item 1 failed: {resp.text}"
        data = resp.json()
        assert data["order_id"] == oid
        assert data["product_id"] == pid
        TestFullUserJourney.order_item_ids.append(data["id"])

    def test_23_add_order_item_2(self, journey_client):
        """POST /api/v1/orders/{id}/items adds second item."""
        oid = TestFullUserJourney.order_id
        pid = TestFullUserJourney.product_ids[1]

        resp = journey_client.post(
            f"/api/v1/orders/{oid}/items",
            json={
                "product_id": pid,
                "catalog_number": f"T2345-{_SUFFIX}",
                "quantity": 10,
                "unit_price": 85.00,
                "unit": "mL",
                "lot_number": f"LOT-{_SUFFIX}",
            },
        )
        assert resp.status_code == 201, f"Add order item 2 failed: {resp.text}"
        TestFullUserJourney.order_item_ids.append(resp.json()["id"])

    def test_24_list_order_items(self, journey_client):
        """GET /api/v1/orders/{id}/items lists all items on the order."""
        oid = TestFullUserJourney.order_id
        resp = journey_client.get(f"/api/v1/orders/{oid}/items")
        assert resp.status_code == 200, f"List order items failed: {resp.text}"
        data = resp.json()
        assert "items" in data, f"Missing items key: {data}"
        assert data["total"] == 2, f"Expected 2 items: {data}"

    def test_25_get_order_detail(self, journey_client):
        """GET /api/v1/orders/{id} returns order with correct fields."""
        oid = TestFullUserJourney.order_id
        resp = journey_client.get(f"/api/v1/orders/{oid}")
        assert resp.status_code == 200, f"Get order failed: {resp.text}"
        data = resp.json()
        assert data["id"] == oid
        assert data["po_number"] == f"PO-{_SUFFIX}"
        assert data["vendor_id"] == TestFullUserJourney.vendor_id
        assert data["status"] == "pending"

    # -----------------------------------------------------------------------
    # 7. Receive order -> auto-create inventory
    # -----------------------------------------------------------------------

    def test_26_receive_order(self, journey_client):
        """POST /api/v1/orders/{id}/receive creates inventory items."""
        oid = TestFullUserJourney.order_id

        resp = journey_client.post(
            f"/api/v1/orders/{oid}/receive",
            json={
                "items": [
                    {
                        "order_item_id": TestFullUserJourney.order_item_ids[0],
                        "quantity": 5,
                        "lot_number": f"RECV-LOT-A-{_SUFFIX}",
                    },
                    {
                        "order_item_id": TestFullUserJourney.order_item_ids[1],
                        "quantity": 10,
                        "lot_number": f"RECV-LOT-B-{_SUFFIX}",
                    },
                ],
                "received_by": _ADMIN_NAME,
            },
        )
        assert resp.status_code == 201, f"Receive order failed: {resp.text}"
        data = resp.json()
        # receive_items returns a list of InventoryItem objects.
        assert isinstance(data, list), f"Expected list of inventory items: {data}"
        assert len(data) == 2, f"Expected 2 inventory items: {data}"

        # Save the first inventory item ID for lifecycle tests.
        TestFullUserJourney.inventory_item_id = data[0]["id"]

        for inv in data:
            assert inv["status"] == "available"
            assert inv["received_by"] == _ADMIN_NAME

    def test_27_order_status_is_received(self, journey_client):
        """After receiving, order status should be 'received'."""
        oid = TestFullUserJourney.order_id
        resp = journey_client.get(f"/api/v1/orders/{oid}")
        assert resp.status_code == 200, f"Get order failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "received", f"Expected status=received: {data}"
        assert data["received_by"] == _ADMIN_NAME

    # -----------------------------------------------------------------------
    # 8. Inventory lifecycle operations
    # -----------------------------------------------------------------------

    def test_28_inventory_item_available(self, journey_client):
        """GET /api/v1/inventory/{id} shows item is available with correct qty."""
        iid = TestFullUserJourney.inventory_item_id
        assert iid is not None, "No inventory item created"

        resp = journey_client.get(f"/api/v1/inventory/{iid}")
        assert resp.status_code == 200, f"Get inventory item failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "available"
        assert float(data["quantity_on_hand"]) == 5.0

    def test_29_consume_partial(self, journey_client):
        """POST /api/v1/inventory/{id}/consume reduces quantity."""
        iid = TestFullUserJourney.inventory_item_id
        resp = journey_client.post(
            f"/api/v1/inventory/{iid}/consume",
            json={
                "quantity": 2,
                "consumed_by": _ADMIN_NAME,
                "purpose": "PCR experiment",
            },
        )
        assert resp.status_code == 200, f"Consume failed: {resp.text}"
        data = resp.json()
        assert float(data["quantity_on_hand"]) == 3.0
        assert data["status"] == "available"

    def test_30_consume_overconsume_rejected(self, journey_client):
        """POST /api/v1/inventory/{id}/consume rejects over-consumption."""
        iid = TestFullUserJourney.inventory_item_id
        resp = journey_client.post(
            f"/api/v1/inventory/{iid}/consume",
            json={
                "quantity": 999,
                "consumed_by": _ADMIN_NAME,
                "purpose": "Should fail",
            },
        )
        # Expect 400 or 422 for validation error.
        assert resp.status_code in (400, 422), f"Expected rejection: {resp.text}"

    def test_31_check_history_after_consume(self, journey_client):
        """GET /api/v1/inventory/{id}/history shows receive + consume entries."""
        iid = TestFullUserJourney.inventory_item_id
        resp = journey_client.get(f"/api/v1/inventory/{iid}/history")
        assert resp.status_code == 200, f"History failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), f"Expected list: {data}"
        # At least 2 entries: receive + consume.
        assert len(data) >= 2, f"Expected at least 2 history entries: {data}"
        actions = [entry.get("action") for entry in data]
        assert "receive" in actions, f"Missing receive action: {actions}"
        assert "consume" in actions, f"Missing consume action: {actions}"

    def test_32_adjust_quantity(self, journey_client):
        """POST /api/v1/inventory/{id}/adjust corrects quantity via cycle count."""
        iid = TestFullUserJourney.inventory_item_id
        resp = journey_client.post(
            f"/api/v1/inventory/{iid}/adjust",
            json={
                "new_quantity": 4,
                "reason": "Cycle count correction",
                "adjusted_by": _ADMIN_NAME,
            },
        )
        assert resp.status_code == 200, f"Adjust failed: {resp.text}"
        data = resp.json()
        assert float(data["quantity_on_hand"]) == 4.0

    def test_33_open_item(self, journey_client):
        """POST /api/v1/inventory/{id}/open marks item as opened."""
        iid = TestFullUserJourney.inventory_item_id
        resp = journey_client.post(
            f"/api/v1/inventory/{iid}/open",
            json={"opened_by": _ADMIN_NAME},
        )
        assert resp.status_code == 200, f"Open failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "opened"
        assert data["opened_date"] is not None

    def test_34_open_already_opened_rejected(self, journey_client):
        """POST /api/v1/inventory/{id}/open on already-opened item fails."""
        iid = TestFullUserJourney.inventory_item_id
        resp = journey_client.post(
            f"/api/v1/inventory/{iid}/open",
            json={"opened_by": _ADMIN_NAME},
        )
        # Should reject with validation error.
        assert resp.status_code in (400, 422), f"Expected rejection: {resp.text}"

    def test_35_transfer_item(self, journey_client):
        """POST /api/v1/inventory/{id}/transfer changes location."""
        iid = TestFullUserJourney.inventory_item_id
        # Use a raw location_id (int) since there's no location API.
        resp = journey_client.post(
            f"/api/v1/inventory/{iid}/transfer",
            json={
                "location_id": 42,
                "transferred_by": _ADMIN_NAME,
            },
        )
        assert resp.status_code == 200, f"Transfer failed: {resp.text}"
        data = resp.json()
        assert data["location_id"] == 42

    def test_36_verify_full_history(self, journey_client):
        """GET /api/v1/inventory/{id}/history shows all lifecycle events."""
        iid = TestFullUserJourney.inventory_item_id
        resp = journey_client.get(f"/api/v1/inventory/{iid}/history")
        assert resp.status_code == 200, f"History failed: {resp.text}"
        data = resp.json()
        actions = [entry.get("action") for entry in data]
        # Should have: receive, consume, adjust, open, transfer.
        for expected in ("receive", "consume", "adjust", "open", "transfer"):
            assert expected in actions, f"Missing {expected} in history: {actions}"

    def test_37_list_inventory(self, journey_client):
        """GET /api/v1/inventory/ returns paginated inventory list."""
        resp = journey_client.get("/api/v1/inventory/")
        assert resp.status_code == 200, f"List inventory failed: {resp.text}"
        data = resp.json()
        assert "items" in data
        assert "total" in data
        # At least 2 items from the receive step.
        assert data["total"] >= 2, f"Expected at least 2 inventory items: {data}"

    def test_38_inventory_filter_by_status(self, journey_client):
        """GET /api/v1/inventory/?status=opened filters correctly."""
        resp = journey_client.get("/api/v1/inventory/", params={"status": "opened"})
        assert resp.status_code == 200, f"Filter inventory failed: {resp.text}"
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "opened"

    # -----------------------------------------------------------------------
    # 9. Search (Meilisearch — may not be available in test)
    # -----------------------------------------------------------------------

    def test_39_search(self, journey_client):
        """GET /api/v1/search/?q=... searches across indexes.

        Meilisearch is typically not running in unit test environments, so
        we accept connection errors gracefully.
        """
        resp = journey_client.get("/api/v1/search/", params={"q": f"Sigma {_SUFFIX}"})
        if resp.status_code == 200:
            data = resp.json()
            assert "query" in data
        else:
            # Accept 500/503 when Meilisearch is not available.
            assert resp.status_code in (
                500,
                502,
                503,
            ), f"Unexpected search error: {resp.text}"

    # -----------------------------------------------------------------------
    # 10. Analytics
    # -----------------------------------------------------------------------

    def test_40_analytics_dashboard(self, journey_client):
        """GET /api/v1/analytics/dashboard returns KPIs reflecting our data."""
        resp = journey_client.get("/api/v1/analytics/dashboard")
        assert resp.status_code == 200, f"Dashboard failed: {resp.text}"
        data = resp.json()
        # Dashboard should report counts matching what we created.
        assert "total_vendors" in data, f"Missing total_vendors: {data}"
        assert "total_products" in data, f"Missing total_products: {data}"
        assert "total_orders" in data, f"Missing total_orders: {data}"
        assert "total_inventory_items" in data, f"Missing total_inventory_items: {data}"
        assert data["total_vendors"] >= 1
        assert data["total_products"] >= 3
        assert data["total_orders"] >= 1
        assert data["total_inventory_items"] >= 2

    def test_41_analytics_spending_by_vendor(self, journey_client):
        """GET /api/v1/analytics/spending/by-vendor returns vendor spending."""
        resp = journey_client.get("/api/v1/analytics/spending/by-vendor")
        assert resp.status_code == 200, f"Spending by vendor failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), f"Expected list: {data}"

    def test_42_analytics_inventory_value(self, journey_client):
        """GET /api/v1/analytics/inventory/value returns inventory valuation."""
        resp = journey_client.get("/api/v1/analytics/inventory/value")
        assert resp.status_code == 200, f"Inventory value failed: {resp.text}"

    def test_43_analytics_vendor_summary(self, journey_client):
        """GET /api/v1/analytics/vendors/{id}/summary returns per-vendor stats."""
        vid = TestFullUserJourney.vendor_id
        resp = journey_client.get(f"/api/v1/analytics/vendors/{vid}/summary")
        assert resp.status_code == 200, f"Vendor summary failed: {resp.text}"

    def test_44_analytics_top_products(self, journey_client):
        """GET /api/v1/analytics/products/top returns top products."""
        resp = journey_client.get("/api/v1/analytics/products/top")
        assert resp.status_code == 200, f"Top products failed: {resp.text}"

    # -----------------------------------------------------------------------
    # 11. Export
    # -----------------------------------------------------------------------

    def test_45_export_inventory_csv(self, journey_client):
        """GET /api/v1/export/inventory returns CSV content."""
        resp = journey_client.get("/api/v1/export/inventory")
        assert resp.status_code == 200, f"Export inventory failed: {resp.text}"
        content_type = resp.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected CSV content-type: {content_type}"
        disposition = resp.headers.get("content-disposition", "")
        assert "inventory.csv" in disposition, f"Expected filename: {disposition}"

    def test_46_export_orders_csv(self, journey_client):
        """GET /api/v1/export/orders returns CSV content."""
        resp = journey_client.get("/api/v1/export/orders")
        assert resp.status_code == 200, f"Export orders failed: {resp.text}"
        content_type = resp.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected CSV content-type: {content_type}"

    def test_47_export_products_csv(self, journey_client):
        """GET /api/v1/export/products returns CSV with our products."""
        resp = journey_client.get("/api/v1/export/products")
        assert resp.status_code == 200, f"Export products failed: {resp.text}"
        content_type = resp.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected CSV content-type: {content_type}"
        # CSV body should contain our catalog numbers.
        body = resp.text
        assert f"A1234-{_SUFFIX}" in body, "Missing product A in CSV export"

    def test_48_export_vendors_csv(self, journey_client):
        """GET /api/v1/export/vendors returns CSV with our vendor."""
        resp = journey_client.get("/api/v1/export/vendors")
        assert resp.status_code == 200, f"Export vendors failed: {resp.text}"
        body = resp.text
        assert f"Sigma-Aldrich {_SUFFIX}" in body, "Missing vendor in CSV export"

    # -----------------------------------------------------------------------
    # 12. Audit trail
    # -----------------------------------------------------------------------

    def test_49_audit_log_has_entries(self, journey_client):
        """GET /api/v1/audit/ returns audit log entries for our operations."""
        resp = journey_client.get("/api/v1/audit/")
        assert resp.status_code == 200, f"Audit log failed: {resp.text}"
        data = resp.json()
        assert "items" in data, f"Missing items in audit response: {data}"
        # We performed many create/update operations, should have entries.
        assert data["total"] >= 1, f"Expected audit entries: {data}"

    def test_50_audit_record_history(self, journey_client):
        """GET /api/v1/audit/{table}/{record_id} returns history for a specific record."""
        iid = TestFullUserJourney.inventory_item_id
        resp = journey_client.get(f"/api/v1/audit/inventory_items/{iid}")
        assert resp.status_code == 200, f"Audit record history failed: {resp.text}"
        data = resp.json()
        assert "items" in data

    # -----------------------------------------------------------------------
    # 13. Vendor sub-resources
    # -----------------------------------------------------------------------

    def test_51_vendor_products(self, journey_client):
        """GET /api/v1/vendors/{id}/products lists vendor's products."""
        vid = TestFullUserJourney.vendor_id
        resp = journey_client.get(f"/api/v1/vendors/{vid}/products")
        assert resp.status_code == 200, f"Vendor products failed: {resp.text}"
        data = resp.json()
        assert data["total"] >= 3

    def test_52_vendor_orders(self, journey_client):
        """GET /api/v1/vendors/{id}/orders lists vendor's orders."""
        vid = TestFullUserJourney.vendor_id
        resp = journey_client.get(f"/api/v1/vendors/{vid}/orders")
        assert resp.status_code == 200, f"Vendor orders failed: {resp.text}"
        data = resp.json()
        assert data["total"] >= 1

    # -----------------------------------------------------------------------
    # 14. Product sub-resources
    # -----------------------------------------------------------------------

    def test_53_product_inventory(self, journey_client):
        """GET /api/v1/products/{id}/inventory lists product's inventory items."""
        pid = TestFullUserJourney.product_ids[0]
        resp = journey_client.get(f"/api/v1/products/{pid}/inventory")
        assert resp.status_code == 200, f"Product inventory failed: {resp.text}"
        data = resp.json()
        assert data["total"] >= 1

    def test_54_product_orders(self, journey_client):
        """GET /api/v1/products/{id}/orders lists product's order items."""
        pid = TestFullUserJourney.product_ids[0]
        resp = journey_client.get(f"/api/v1/products/{pid}/orders")
        assert resp.status_code == 200, f"Product orders failed: {resp.text}"
        data = resp.json()
        assert data["total"] >= 1

    # -----------------------------------------------------------------------
    # 15. Low stock & expiring alerts
    # -----------------------------------------------------------------------

    def test_55_low_stock_endpoint(self, journey_client):
        """GET /api/v1/inventory/low-stock returns low-stock products."""
        resp = journey_client.get("/api/v1/inventory/low-stock")
        assert resp.status_code == 200, f"Low stock failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, list)

    def test_56_expiring_endpoint(self, journey_client):
        """GET /api/v1/inventory/expiring returns items expiring within N days."""
        resp = journey_client.get("/api/v1/inventory/expiring", params={"days": 90})
        assert resp.status_code == 200, f"Expiring failed: {resp.text}"

    # -----------------------------------------------------------------------
    # 16. Update operations
    # -----------------------------------------------------------------------

    def test_57_update_vendor(self, journey_client):
        """PATCH /api/v1/vendors/{id} updates vendor details."""
        vid = TestFullUserJourney.vendor_id
        resp = journey_client.patch(
            f"/api/v1/vendors/{vid}",
            json={"notes": f"Updated via journey test {_SUFFIX}"},
        )
        assert resp.status_code == 200, f"Update vendor failed: {resp.text}"
        data = resp.json()
        assert data["notes"] == f"Updated via journey test {_SUFFIX}"

    def test_58_update_product(self, journey_client):
        """PATCH /api/v1/products/{id} updates product details."""
        pid = TestFullUserJourney.product_ids[0]
        resp = journey_client.patch(
            f"/api/v1/products/{pid}",
            json={"storage_temp": "-20C"},
        )
        assert resp.status_code == 200, f"Update product failed: {resp.text}"
        data = resp.json()
        assert data["storage_temp"] == "-20C"

    def test_59_update_order_item(self, journey_client):
        """PATCH /api/v1/orders/{id}/items/{item_id} updates an order item."""
        oid = TestFullUserJourney.order_id
        item_id = TestFullUserJourney.order_item_ids[0]
        resp = journey_client.patch(
            f"/api/v1/orders/{oid}/items/{item_id}",
            json={"quantity": 8},
        )
        assert resp.status_code == 200, f"Update order item failed: {resp.text}"

    # -----------------------------------------------------------------------
    # 17. Inventory reorder URL
    # -----------------------------------------------------------------------

    def test_60_reorder_url(self, journey_client):
        """GET /api/v1/inventory/{id}/reorder-url generates vendor URL."""
        iid = TestFullUserJourney.inventory_item_id
        resp = journey_client.get(f"/api/v1/inventory/{iid}/reorder-url")
        assert resp.status_code == 200, f"Reorder URL failed: {resp.text}"
        data = resp.json()
        assert "url" in data
        assert "catalog_number" in data

    # -----------------------------------------------------------------------
    # 18. Order filtering
    # -----------------------------------------------------------------------

    def test_61_filter_orders_by_status(self, journey_client):
        """GET /api/v1/orders/?status=received filters correctly."""
        resp = journey_client.get("/api/v1/orders/", params={"status": "received"})
        assert resp.status_code == 200, f"Filter orders failed: {resp.text}"
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "received"

    def test_62_filter_orders_by_vendor(self, journey_client):
        """GET /api/v1/orders/?vendor_id=... filters by vendor."""
        vid = TestFullUserJourney.vendor_id
        resp = journey_client.get("/api/v1/orders/", params={"vendor_id": vid})
        assert resp.status_code == 200, f"Filter orders by vendor failed: {resp.text}"
        data = resp.json()
        assert data["total"] >= 1

    def test_63_filter_orders_by_po_number(self, journey_client):
        """GET /api/v1/orders/?po_number=... searches by PO number."""
        resp = journey_client.get(
            "/api/v1/orders/", params={"po_number": f"PO-{_SUFFIX}"}
        )
        assert resp.status_code == 200, f"Filter by PO number failed: {resp.text}"
        data = resp.json()
        assert data["total"] >= 1

    # -----------------------------------------------------------------------
    # 19. Dispose inventory item
    # -----------------------------------------------------------------------

    def test_64_dispose_item(self, journey_client):
        """POST /api/v1/inventory/{id}/dispose marks item as disposed."""
        iid = TestFullUserJourney.inventory_item_id
        resp = journey_client.post(
            f"/api/v1/inventory/{iid}/dispose",
            json={
                "reason": "Expired, no longer usable",
                "disposed_by": _ADMIN_NAME,
            },
        )
        assert resp.status_code == 200, f"Dispose failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "disposed"
        assert float(data["quantity_on_hand"]) == 0.0

    def test_65_consume_disposed_rejected(self, journey_client):
        """POST /api/v1/inventory/{id}/consume on disposed item fails."""
        iid = TestFullUserJourney.inventory_item_id
        resp = journey_client.post(
            f"/api/v1/inventory/{iid}/consume",
            json={
                "quantity": 1,
                "consumed_by": _ADMIN_NAME,
                "purpose": "Should fail",
            },
        )
        assert resp.status_code in (400, 422), f"Expected rejection: {resp.text}"

    def test_66_final_history_check(self, journey_client):
        """Full lifecycle history should contain all operations."""
        iid = TestFullUserJourney.inventory_item_id
        resp = journey_client.get(f"/api/v1/inventory/{iid}/history")
        assert resp.status_code == 200, f"Final history failed: {resp.text}"
        data = resp.json()
        actions = [entry.get("action") for entry in data]
        for expected in ("receive", "consume", "adjust", "open", "transfer", "dispose"):
            assert expected in actions, (
                f"Missing {expected} in final history: {actions}"
            )

    # -----------------------------------------------------------------------
    # 20. Direct inventory creation (not via order receive)
    # -----------------------------------------------------------------------

    def test_67_create_inventory_directly(self, journey_client):
        """POST /api/v1/inventory/ creates inventory item without an order."""
        pid = TestFullUserJourney.product_ids[2]
        resp = journey_client.post(
            "/api/v1/inventory/",
            json={
                "product_id": pid,
                "quantity_on_hand": 50,
                "lot_number": f"DIRECT-LOT-{_SUFFIX}",
                "unit": "mL",
                "notes": "Added manually without order",
            },
        )
        assert resp.status_code == 201, f"Create inventory directly failed: {resp.text}"
        data = resp.json()
        assert data["product_id"] == pid
        assert float(data["quantity_on_hand"]) == 50.0
        assert data["status"] == "available"

    # -----------------------------------------------------------------------
    # 21. Pagination
    # -----------------------------------------------------------------------

    def test_68_pagination_works(self, journey_client):
        """Paginated endpoints return correct structure."""
        resp = journey_client.get(
            "/api/v1/products/", params={"page": 1, "page_size": 2}
        )
        assert resp.status_code == 200, f"Pagination failed: {resp.text}"
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert "pages" in data
        assert len(data["items"]) <= 2

    # -----------------------------------------------------------------------
    # 22. Sorting
    # -----------------------------------------------------------------------

    def test_69_sorting_works(self, journey_client):
        """Products can be sorted by name descending."""
        resp = journey_client.get(
            "/api/v1/products/",
            params={"sort_by": "name", "sort_dir": "desc"},
        )
        assert resp.status_code == 200, f"Sorting failed: {resp.text}"
        data = resp.json()
        names = [p["name"] for p in data["items"]]
        assert names == sorted(names, reverse=True), f"Not sorted desc: {names}"

    # -----------------------------------------------------------------------
    # 23. Unauthenticated access blocked
    # -----------------------------------------------------------------------

    def test_70_unauthenticated_access_blocked(self, journey_client):
        """Protected endpoints require authentication.

        We log out first, verify we get 401, then log back in.
        """
        # Logout.
        resp = journey_client.post("/api/v1/auth/logout")
        assert resp.status_code == 200, f"Logout failed: {resp.text}"

        # Attempt to access protected endpoint.
        resp = journey_client.get("/api/v1/vendors/")
        assert resp.status_code == 401, f"Expected 401 without auth: {resp.text}"

        # But public endpoints still work.
        resp = journey_client.get("/api/v1/setup/status")
        assert resp.status_code == 200, f"Public endpoint blocked: {resp.text}"

        resp = journey_client.get("/api/v1/config")
        assert resp.status_code == 200, f"Config endpoint blocked: {resp.text}"

        # Log back in for remaining tests.
        resp = journey_client.post(
            "/api/v1/auth/login",
            json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
        )
        assert resp.status_code == 200, f"Re-login failed: {resp.text}"

    # -----------------------------------------------------------------------
    # 24. API key authentication
    # -----------------------------------------------------------------------

    def test_71_api_key_auth(self, journey_client):
        """X-Api-Key header grants access when session cookie is absent."""
        # Logout to clear session.
        journey_client.post("/api/v1/auth/logout")

        # Access with API key header.
        resp = journey_client.get(
            "/api/v1/vendors/",
            headers={"X-Api-Key": "journey-test-api-key"},
        )
        assert resp.status_code == 200, f"API key auth failed: {resp.text}"

        # Wrong API key should fail.
        resp = journey_client.get(
            "/api/v1/vendors/",
            headers={"X-Api-Key": "wrong-key"},
        )
        assert resp.status_code == 401, f"Expected 401 with wrong API key: {resp.text}"

        # Log back in for remaining tests.
        resp = journey_client.post(
            "/api/v1/auth/login",
            json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
        )
        assert resp.status_code == 200, f"Re-login failed: {resp.text}"

    # -----------------------------------------------------------------------
    # 25. Final logout
    # -----------------------------------------------------------------------

    def test_72_logout(self, journey_client):
        """POST /api/v1/auth/logout clears session."""
        resp = journey_client.post("/api/v1/auth/logout")
        assert resp.status_code == 200, f"Logout failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "ok"

    def test_73_session_cleared_after_logout(self, journey_client):
        """After logout, protected endpoints return 401."""
        resp = journey_client.get("/api/v1/vendors/")
        assert resp.status_code == 401, f"Expected 401 after logout: {resp.text}"

        # Auth/me should also indicate not authenticated.
        resp = journey_client.get("/api/v1/auth/me")
        assert resp.status_code == 401, f"Expected 401 for auth/me: {resp.text}"
