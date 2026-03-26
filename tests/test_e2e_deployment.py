"""End-to-end deployment smoke tests.

Run against local TestClient (default) or live deployment:
    APP_BASE_URL=https://demo.labclaw.org uv run pytest tests/test_e2e_deployment.py -v
"""

from __future__ import annotations

import os
from typing import ClassVar

import httpx
import pytest
from fastapi.testclient import TestClient

from lab_manager.config import get_settings


_ENV_KEYS = (
    "AUTH_ENABLED",
    "ADMIN_SECRET_KEY",
    "ADMIN_PASSWORD",
    "API_KEY",
    "SECURE_COOKIES",
)


@pytest.fixture(scope="module")
def e2e_client():
    """Module-scoped HTTP client.

    Uses httpx against APP_BASE_URL if set, otherwise creates a local
    TestClient with auth enabled + SQLite.
    """
    base_url = os.environ.get("APP_BASE_URL")
    if base_url:
        client = httpx.Client(base_url=base_url, timeout=30, follow_redirects=True)
        yield client
        client.close()
        return

    # Save originals for restoration.
    orig_env = {k: os.environ.get(k) for k in _ENV_KEYS}

    os.environ["AUTH_ENABLED"] = "true"
    os.environ["ADMIN_SECRET_KEY"] = "e2e-test-secret-key-12345"
    os.environ["ADMIN_PASSWORD"] = "e2e-test-admin-password"
    os.environ["API_KEY"] = "e2e-test-api-key"
    os.environ["SECURE_COOKIES"] = "false"
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


# ---- Admin credentials used across tests ----
_ADMIN_NAME = "E2E Admin"
_ADMIN_EMAIL = "e2e-admin@example.com"
_ADMIN_PASSWORD = "e2e-test-password-12345"


@pytest.mark.e2e
class TestE2EDeployment:
    """End-to-end smoke tests exercising the full deployment lifecycle."""

    # Shared state: vendor_id is reused across product and order creation.
    _vendor_id: ClassVar[int | None] = None

    # ------------------------------------------------------------------
    # 1. Health
    # ------------------------------------------------------------------

    def test_health(self, e2e_client):
        """GET /api/health returns 200 with postgresql key."""
        resp = e2e_client.get("/api/health")
        # 200 (ok) or 503 (degraded) are both valid — just not 401.
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "services" in data
        assert "postgresql" in data["services"]

    # ------------------------------------------------------------------
    # 2. Setup status
    # ------------------------------------------------------------------

    def test_setup_status(self, e2e_client):
        """GET /api/v1/setup/status returns needs_setup boolean."""
        resp = e2e_client.get("/api/v1/setup/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "needs_setup" in data
        assert isinstance(data["needs_setup"], bool)

    # ------------------------------------------------------------------
    # 3. Config
    # ------------------------------------------------------------------

    def test_config(self, e2e_client):
        """GET /api/v1/config returns lab_name."""
        resp = e2e_client.get("/api/v1/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "lab_name" in data

    # ------------------------------------------------------------------
    # 4. Root accessible
    # ------------------------------------------------------------------

    def test_root_accessible(self, e2e_client):
        """GET / returns 200 with HTML content."""
        resp = e2e_client.get("/")
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "text/html" in content_type

    # ------------------------------------------------------------------
    # 5. Public endpoints no auth
    # ------------------------------------------------------------------

    def test_public_endpoints_no_auth(self, e2e_client):
        """All public paths return non-401 status codes.

        Note: /api/v1/auth/me is allowlisted from middleware auth but the
        endpoint itself returns 401 when no session exists, so we exclude it.
        """
        public_paths = [
            "/api/health",
            "/api/v1/setup/status",
            "/api/v1/config",
            "/",
        ]
        for path in public_paths:
            resp = e2e_client.get(path)
            assert resp.status_code != 401, f"{path} returned 401"

    # ------------------------------------------------------------------
    # 6. Protected endpoints require auth
    # ------------------------------------------------------------------

    def test_protected_endpoints_require_auth(self, e2e_client):
        """/api/v1/vendors/ returns 401 without session cookie."""
        # Use a clean request without cookies to ensure no auth leaks.
        base_url = os.environ.get("APP_BASE_URL")
        if base_url:
            # Fresh httpx client with no cookies.
            with httpx.Client(base_url=base_url, timeout=30) as fresh:
                resp = fresh.get("/api/v1/vendors")
        else:
            # For local TestClient: temporarily clear cookies.
            saved = dict(e2e_client.cookies)
            e2e_client.cookies.clear()
            resp = e2e_client.get("/api/v1/vendors")
            # Restore cookies.
            for k, v in saved.items():
                e2e_client.cookies.set(k, v)
        assert resp.status_code == 401

    # ------------------------------------------------------------------
    # 7. Complete setup
    # ------------------------------------------------------------------

    def test_complete_setup(self, e2e_client):
        """POST /api/v1/setup/complete creates admin user (skip if already setup)."""
        status_resp = e2e_client.get("/api/v1/setup/status")
        needs_setup = status_resp.json().get("needs_setup", False)

        if not needs_setup:
            pytest.skip("Setup already completed")

        resp = e2e_client.post(
            "/api/v1/setup/complete",
            json={
                "admin_name": _ADMIN_NAME,
                "admin_email": _ADMIN_EMAIL,
                "admin_password": _ADMIN_PASSWORD,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    # ------------------------------------------------------------------
    # 8. Login
    # ------------------------------------------------------------------

    def test_login(self, e2e_client):
        """POST /api/v1/auth/login returns session cookie."""
        resp = e2e_client.post(
            "/api/v1/auth/login",
            json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "user" in data

    # ------------------------------------------------------------------
    # 9. Auth me
    # ------------------------------------------------------------------

    def test_auth_me(self, e2e_client):
        """GET /api/v1/auth/me returns user info with session."""
        resp = e2e_client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert "user" in data
        assert "name" in data["user"]

    # ------------------------------------------------------------------
    # 10. Create vendor
    # ------------------------------------------------------------------

    def test_create_vendor(self, e2e_client):
        """POST /api/v1/vendors/ creates a vendor."""
        resp = e2e_client.post(
            "/api/v1/vendors",
            json={
                "name": "E2E Test Vendor",
                "email": "vendor@e2e-test.com",
                "website": "https://e2e-test.com",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["name"] == "E2E Test Vendor"
        TestE2EDeployment._vendor_id = data["id"]

    # ------------------------------------------------------------------
    # 11. List vendors
    # ------------------------------------------------------------------

    def test_list_vendors(self, e2e_client):
        """GET /api/v1/vendors/ returns total >= 1."""
        resp = e2e_client.get("/api/v1/vendors")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert data["total"] >= 1
        assert "items" in data

    # ------------------------------------------------------------------
    # 12. Create product
    # ------------------------------------------------------------------

    def test_create_product(self, e2e_client):
        """POST /api/v1/products/ creates a product."""
        resp = e2e_client.post(
            "/api/v1/products",
            json={
                "catalog_number": "E2E-001",
                "name": "E2E Test Product",
                "vendor_id": TestE2EDeployment._vendor_id,
                "category": "Reagents",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["catalog_number"] == "E2E-001"

    # ------------------------------------------------------------------
    # 13. Create order
    # ------------------------------------------------------------------

    def test_create_order(self, e2e_client):
        """POST /api/v1/orders/ creates an order."""
        resp = e2e_client.post(
            "/api/v1/orders",
            json={
                "po_number": "E2E-PO-001",
                "vendor_id": TestE2EDeployment._vendor_id,
                "status": "pending",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        # Response may be the order directly or wrapped with _duplicate_warning.
        order = data.get("order", data)
        assert "id" in order

    # ------------------------------------------------------------------
    # 14. List orders
    # ------------------------------------------------------------------

    def test_list_orders(self, e2e_client):
        """GET /api/v1/orders/ returns total >= 1."""
        resp = e2e_client.get("/api/v1/orders")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert data["total"] >= 1
        assert "items" in data

    # ------------------------------------------------------------------
    # 15. Analytics dashboard
    # ------------------------------------------------------------------

    def test_analytics_dashboard(self, e2e_client):
        """GET /api/v1/analytics/dashboard returns totals."""
        resp = e2e_client.get("/api/v1/analytics/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        # Dashboard summary returns total_* keys.
        assert "total_products" in data
        assert "total_vendors" in data
        assert "total_orders" in data

    # ------------------------------------------------------------------
    # 16. Search
    # ------------------------------------------------------------------

    def test_search(self, e2e_client):
        """GET /api/v1/search?q=test returns results dict or hits array."""
        resp = e2e_client.get("/api/v1/search", params={"q": "test"})
        # Meilisearch may not be available — accept 200 (with results) or 500.
        if resp.status_code == 200:
            data = resp.json()
            # When searching all indexes: {"query", "results", "total"}.
            assert "query" in data
            assert "results" in data or "hits" in data

    # ------------------------------------------------------------------
    # 17. Alerts
    # ------------------------------------------------------------------

    def test_alerts(self, e2e_client):
        """GET /api/v1/alerts/ returns items array."""
        resp = e2e_client.get("/api/v1/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    # ------------------------------------------------------------------
    # 18. Audit
    # ------------------------------------------------------------------

    def test_audit(self, e2e_client):
        """GET /api/v1/audit/ returns items with total."""
        resp = e2e_client.get("/api/v1/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    # ------------------------------------------------------------------
    # 19. Export CSV
    # ------------------------------------------------------------------

    def test_export_csv(self, e2e_client):
        """GET /api/v1/export/vendors returns 200 with CSV content."""
        resp = e2e_client.get("/api/v1/export/vendors")
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "text/csv" in content_type
        # Should contain at least a header row.
        body = resp.text
        assert "name" in body.lower()

    # ------------------------------------------------------------------
    # 20. Logout
    # ------------------------------------------------------------------

    def test_logout(self, e2e_client):
        """POST /api/v1/auth/logout clears session."""
        resp = e2e_client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

        # After logout, protected endpoint should reject (if we clear cookies).
        base_url = os.environ.get("APP_BASE_URL")
        if base_url:
            with httpx.Client(base_url=base_url, timeout=30) as fresh:
                check = fresh.get("/api/v1/vendors")
        else:
            e2e_client.cookies.clear()
            check = e2e_client.get("/api/v1/vendors")
        assert check.status_code == 401
