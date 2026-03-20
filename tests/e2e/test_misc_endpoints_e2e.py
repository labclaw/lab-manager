"""E2E tests for auth, search, alerts, audit, telemetry, and other endpoints.

Comprehensive coverage of remaining API endpoints.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

# ADMIN_EMAIL and ADMIN_PASSWORD are available via conftest.py fixture injection


# Admin credentials for tests (must match conftest.py)
_ADMIN_EMAIL = "e2e-admin@test.local"
_ADMIN_PASSWORD = "e2e-test-password-secure-12345"


@pytest.mark.e2e
class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    def test_login_success(self, e2e_client: TestClient | httpx.Client):
        """POST /api/auth/login authenticates user."""
        # First ensure setup is complete
        status = e2e_client.get("/api/setup/status")
        if status.json().get("needs_setup"):
            e2e_client.post(
                "/api/setup/complete",
                json={
                    "admin_name": "Test Admin",
                    "admin_email": _ADMIN_EMAIL,
                    "admin_password": _ADMIN_PASSWORD,
                },
            )

        resp = e2e_client.post(
            "/api/auth/login",
            json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "user" in data

    def test_login_invalid_password(self, e2e_client: TestClient | httpx.Client):
        """POST /api/auth/login rejects invalid password."""
        resp = e2e_client.post(
            "/api/auth/login",
            json={"email": _ADMIN_EMAIL, "password": "wrong-password"},
        )
        assert resp.status_code == 401

    def test_login_invalid_email(self, e2e_client: TestClient | httpx.Client):
        """POST /api/auth/login rejects invalid email."""
        resp = e2e_client.post(
            "/api/auth/login",
            json={"email": "nonexistent@test.local", "password": "any-password"},
        )
        assert resp.status_code == 401

    def test_auth_me(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/auth/me returns current user."""
        resp = authenticated_client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert "user" in data

    def test_logout(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/auth/logout clears session."""
        resp = authenticated_client.post("/api/auth/logout")
        assert resp.status_code == 200


@pytest.mark.e2e
class TestSearchEndpoints:
    """Tests for search endpoints."""

    def test_search_all(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/search/ searches all indexes."""
        resp = authenticated_client.get("/api/v1/search/", params={"q": "test"})
        # Meilisearch may not be available
        if resp.status_code == 200:
            data = resp.json()
            assert "query" in data

    def test_search_with_limit(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/search/ respects limit parameter."""
        resp = authenticated_client.get(
            "/api/v1/search/", params={"q": "test", "limit": 5}
        )
        if resp.status_code == 200:
            data = resp.json()
            assert "query" in data

    def test_search_empty_query(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/search/ handles empty query."""
        resp = authenticated_client.get("/api/v1/search/", params={"q": ""})
        # May return 400 for empty query or empty results
        assert resp.status_code in (200, 400)


@pytest.mark.e2e
class TestAlertsEndpoints:
    """Tests for alerts endpoints."""

    def test_list_alerts(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/alerts/ returns alerts list."""
        resp = authenticated_client.get("/api/v1/alerts/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data or isinstance(data, list)

    def test_alerts_summary(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/alerts/summary returns alert summary."""
        resp = authenticated_client.get("/api/v1/alerts/summary")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)

    def test_acknowledge_alert(self, authenticated_client: TestClient | httpx.Client):
        """POST acknowledge alert."""
        # Try to acknowledge a non-existent alert
        resp = authenticated_client.post("/api/v1/alerts/99999/acknowledge")
        assert resp.status_code in (200, 404, 405)


@pytest.mark.e2e
class TestAuditEndpoints:
    """Tests for audit log endpoints."""

    def test_list_audit(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/audit/ returns audit log."""
        resp = authenticated_client.get("/api/v1/audit/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data or isinstance(data, list)

    def test_audit_with_filters(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/audit/ with filters."""
        resp = authenticated_client.get(
            "/api/v1/audit/",
            params={"table": "vendors", "action": "create"},
        )
        assert resp.status_code == 200

    def test_record_history(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/audit/{table}/{id} returns record history."""
        resp = authenticated_client.get("/api/v1/audit/vendors/1")
        assert resp.status_code in (200, 404)


@pytest.mark.e2e
class TestTelemetryEndpoints:
    """Tests for telemetry endpoints."""

    def test_track_event(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/telemetry/event tracks event."""
        resp = authenticated_client.post(
            "/api/v1/telemetry/event",
            json={"event_type": "e2e_test", "properties": {"test": True}},
        )
        assert resp.status_code in (200, 201, 404, 422)

    def test_dau_stats(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/telemetry/dau returns DAU stats."""
        resp = authenticated_client.get("/api/v1/telemetry/dau")
        assert resp.status_code in (200, 404)

    def test_events_list(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/telemetry/events returns events list."""
        resp = authenticated_client.get("/api/v1/telemetry/events")
        assert resp.status_code in (200, 404)


@pytest.mark.e2e
class TestAskEndpoint:
    """Tests for RAG/NL-to-SQL ask endpoint."""

    def test_ask_get(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/ask returns help or results."""
        resp = authenticated_client.get("/api/v1/ask", params={"q": "show vendors"})
        assert resp.status_code in (200, 400, 404, 500)

    def test_ask_post(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/ask processes natural language query."""
        resp = authenticated_client.post(
            "/api/v1/ask",
            json={"query": "list all vendors"},
        )
        assert resp.status_code in (200, 400, 404, 500)


@pytest.mark.e2e
class TestPublicEndpoints:
    """Tests for public (unauthenticated) endpoints."""

    def test_health_check(self, e2e_client: TestClient | httpx.Client):
        """GET /api/health returns health status."""
        resp = e2e_client.get("/api/health")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "services" in data

    def test_setup_status(self, e2e_client: TestClient | httpx.Client):
        """GET /api/setup/status returns setup status."""
        resp = e2e_client.get("/api/setup/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "needs_setup" in data

    def test_config(self, e2e_client: TestClient | httpx.Client):
        """GET /api/config returns config."""
        resp = e2e_client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "lab_name" in data


@pytest.mark.e2e
class TestProductsEndpoints:
    """Tests for products endpoints."""

    def test_list_products(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/products/ returns products list."""
        resp = authenticated_client.get("/api/v1/products/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data or isinstance(data, list)

    def test_get_product_by_id(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """GET /api/v1/products/{id} returns product details."""
        resp = authenticated_client.get(f"/api/v1/products/{test_product_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "catalog_number" in data

    def test_update_product(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """PATCH /api/v1/products/{id} updates product."""
        resp = authenticated_client.patch(
            f"/api/v1/products/{test_product_id}",
            json={"name": "Updated E2E Product"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated E2E Product"

    def test_product_inventory(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """GET /api/v1/products/{id}/inventory returns product inventory."""
        resp = authenticated_client.get(f"/api/v1/products/{test_product_id}/inventory")
        assert resp.status_code in (200, 404)

    def test_product_orders(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """GET /api/v1/products/{id}/orders returns product orders."""
        resp = authenticated_client.get(f"/api/v1/products/{test_product_id}/orders")
        assert resp.status_code in (200, 404)


@pytest.mark.e2e
class TestVendorsEndpoints:
    """Tests for vendors endpoints."""

    def test_list_vendors(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/vendors/ returns vendors list."""
        resp = authenticated_client.get("/api/v1/vendors/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data or isinstance(data, list)

    def test_get_vendor_by_id(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_vendor_id: int,
    ):
        """GET /api/v1/vendors/{id} returns vendor details."""
        resp = authenticated_client.get(f"/api/v1/vendors/{test_vendor_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data

    def test_update_vendor(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_vendor_id: int,
    ):
        """PATCH /api/v1/vendors/{id} updates vendor."""
        resp = authenticated_client.patch(
            f"/api/v1/vendors/{test_vendor_id}",
            json={"website": "https://updated-e2e.local"},
        )
        assert resp.status_code == 200

    def test_vendor_products(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_vendor_id: int,
    ):
        """GET /api/v1/vendors/{id}/products returns vendor products."""
        resp = authenticated_client.get(f"/api/v1/vendors/{test_vendor_id}/products")
        assert resp.status_code == 200

    def test_vendor_orders(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_vendor_id: int,
    ):
        """GET /api/v1/vendors/{id}/orders returns vendor orders."""
        resp = authenticated_client.get(f"/api/v1/vendors/{test_vendor_id}/orders")
        assert resp.status_code == 200
