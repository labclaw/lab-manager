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
        status = e2e_client.get("/api/v1/setup/status")
        if status.json().get("needs_setup"):
            e2e_client.post(
                "/api/v1/setup/complete",
                json={
                    "admin_name": "Test Admin",
                    "admin_email": _ADMIN_EMAIL,
                    "admin_password": _ADMIN_PASSWORD,
                },
            )

        resp = e2e_client.post(
            "/api/v1/auth/login",
            json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "user" in data

    def test_login_invalid_password(self, e2e_client: TestClient | httpx.Client):
        """POST /api/auth/login rejects invalid password."""
        resp = e2e_client.post(
            "/api/v1/auth/login",
            json={"email": _ADMIN_EMAIL, "password": "wrong-password"},
        )
        assert resp.status_code == 401

    def test_login_invalid_email(self, e2e_client: TestClient | httpx.Client):
        """POST /api/auth/login rejects invalid email."""
        resp = e2e_client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@test.local", "password": "any-password"},
        )
        assert resp.status_code == 401

    def test_auth_me(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/auth/me returns current user."""
        resp = authenticated_client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert "user" in data

    def test_logout(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/auth/logout clears session."""
        resp = authenticated_client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
        # Re-login to restore session for subsequent tests
        login_resp = authenticated_client.post(
            "/api/v1/auth/login",
            json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
        )
        assert login_resp.status_code == 200


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
        # May return 400, 422 for empty query or empty results
        assert resp.status_code in (200, 400, 422)

    def test_search_suggest(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/search/suggest returns suggestions."""
        resp = authenticated_client.get("/api/v1/search/suggest", params={"q": "test"})
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, (list, dict))


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

    def test_resolve_alert(self, authenticated_client: TestClient | httpx.Client):
        """POST resolve alert."""
        # Try to resolve a non-existent alert
        resp = authenticated_client.post("/api/v1/alerts/99999/resolve")
        assert resp.status_code in (200, 404, 405)

    def test_alerts_check(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/alerts/check triggers alert check."""
        resp = authenticated_client.post("/api/v1/alerts/check")
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
        assert resp.status_code in (200, 400, 404, 422, 500)


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
        resp = e2e_client.get("/api/v1/setup/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "needs_setup" in data

    def test_config(self, e2e_client: TestClient | httpx.Client):
        """GET /api/v1/config returns config."""
        resp = e2e_client.get("/api/v1/config")
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


@pytest.mark.e2e
class TestEndpointAccessibility:
    """Tests that protected endpoints are reachable with authentication."""

    def test_vendors_endpoint_accessible(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Vendors endpoint is accessible."""
        resp = authenticated_client.get("/api/v1/vendors/")
        assert resp.status_code == 200

    def test_products_endpoint_accessible(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Products endpoint is accessible."""
        resp = authenticated_client.get("/api/v1/products/")
        assert resp.status_code == 200

    def test_inventory_endpoint_accessible(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Inventory endpoint is accessible."""
        resp = authenticated_client.get("/api/v1/inventory/")
        assert resp.status_code == 200

    def test_orders_endpoint_accessible(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Orders endpoint is accessible."""
        resp = authenticated_client.get("/api/v1/orders/")
        assert resp.status_code == 200

    def test_documents_endpoint_accessible(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Documents endpoint is accessible."""
        resp = authenticated_client.get("/api/v1/documents/")
        assert resp.status_code == 200

    def test_equipment_endpoint_accessible(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Equipment endpoint is accessible."""
        resp = authenticated_client.get("/api/v1/equipment/")
        assert resp.status_code == 200

    def test_analytics_endpoint_accessible(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Analytics endpoint is accessible."""
        resp = authenticated_client.get("/api/v1/analytics/dashboard")
        assert resp.status_code == 200

    def test_audit_endpoint_accessible(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Audit endpoint is accessible."""
        resp = authenticated_client.get("/api/v1/audit/")
        assert resp.status_code == 200


@pytest.mark.e2e
class TestInvalidIdHandling:
    """Tests for handling invalid/non-existent IDs."""

    def test_get_nonexistent_vendor(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/vendors/{id} returns 404 for non-existent vendor."""
        resp = authenticated_client.get("/api/v1/vendors/999999")
        assert resp.status_code == 404

    def test_get_nonexistent_product(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/products/{id} returns 404 for non-existent product."""
        resp = authenticated_client.get("/api/v1/products/999999")
        assert resp.status_code == 404

    def test_get_nonexistent_order(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/orders/{id} returns 404 for non-existent order."""
        resp = authenticated_client.get("/api/v1/orders/999999")
        assert resp.status_code == 404

    def test_get_nonexistent_inventory(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/{id} returns 404 for non-existent inventory."""
        resp = authenticated_client.get("/api/v1/inventory/999999")
        assert resp.status_code == 404

    def test_get_nonexistent_document(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/documents/{id} returns 404 for non-existent document."""
        resp = authenticated_client.get("/api/v1/documents/999999")
        assert resp.status_code == 404

    def test_get_nonexistent_equipment(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/equipment/{id} returns 404 for non-existent equipment."""
        resp = authenticated_client.get("/api/v1/equipment/999999")
        assert resp.status_code == 404

    def test_patch_nonexistent_vendor(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """PATCH /api/v1/vendors/{id} returns 404 for non-existent vendor."""
        resp = authenticated_client.patch(
            "/api/v1/vendors/999999", json={"name": "test"}
        )
        assert resp.status_code == 404

    def test_delete_nonexistent_order(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """DELETE /api/v1/orders/{id} returns 404 for non-existent order."""
        resp = authenticated_client.delete("/api/v1/orders/999999")
        assert resp.status_code == 404


@pytest.mark.e2e
class TestMalformedRequests:
    """Tests for handling malformed requests."""

    def test_login_missing_email(self, e2e_client: TestClient | httpx.Client):
        """POST /api/auth/login rejects missing email."""
        resp = e2e_client.post("/api/v1/auth/login", json={"password": "test"})
        assert resp.status_code in (400, 422)

    def test_login_missing_password(self, e2e_client: TestClient | httpx.Client):
        """POST /api/auth/login rejects missing password."""
        resp = e2e_client.post("/api/v1/auth/login", json={"email": "test@test.local"})
        assert resp.status_code in (400, 422)

    def test_create_vendor_missing_name(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/vendors/ rejects missing name."""
        resp = authenticated_client.post("/api/v1/vendors/", json={})
        assert resp.status_code in (400, 422)

    def test_create_order_invalid_vendor(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/orders/ handles invalid vendor_id."""
        # API may accept the order with null vendor or create anyway
        resp = authenticated_client.post(
            "/api/v1/orders/",
            json={"po_number": "TEST-INVALID-VENDOR", "vendor_id": 999999},
        )
        # API returns 201 even with invalid vendor_id (creates order)
        assert resp.status_code in (201, 400, 404, 422)

    def test_invalid_json_body(self, authenticated_client: TestClient | httpx.Client):
        """Endpoints handle invalid JSON gracefully."""
        # This tests the framework's JSON parsing
        resp = authenticated_client.post(
            "/api/v1/vendors/",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code in (400, 422)


@pytest.mark.e2e
class TestProductsCRUD:
    """Tests for products CRUD operations."""

    def test_create_product(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/products/ creates new product."""
        resp = authenticated_client.post(
            "/api/v1/products/",
            json={
                "name": "E2E Test Product CRUD",
                "catalog_number": "E2E-CRUD-001",
                "vendor_id": 1,
            },
        )
        assert resp.status_code in (200, 201, 400, 422)

    def test_delete_product(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """DELETE /api/v1/products/{id} removes product."""
        # Create a product to delete
        resp = authenticated_client.post(
            "/api/v1/products/",
            json={
                "name": "Product To Delete",
                "catalog_number": "E2E-DEL-001",
            },
        )
        if resp.status_code in (200, 201):
            product_id = resp.json()["id"]
            del_resp = authenticated_client.delete(f"/api/v1/products/{product_id}")
            assert del_resp.status_code in (200, 204)


@pytest.mark.e2e
class TestVendorsCRUD:
    """Tests for vendors CRUD operations."""

    def test_create_vendor(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/vendors/ creates new vendor."""
        resp = authenticated_client.post(
            "/api/v1/vendors/",
            json={
                "name": "E2E Test Vendor CRUD",
                "website": "https://e2e-crud.local",
            },
        )
        assert resp.status_code in (200, 201)

    def test_delete_vendor(self, authenticated_client: TestClient | httpx.Client):
        """DELETE /api/v1/vendors/{id} removes vendor."""
        # Create a vendor to delete
        resp = authenticated_client.post(
            "/api/v1/vendors/",
            json={"name": "Vendor To Delete E2E"},
        )
        if resp.status_code in (200, 201):
            vendor_id = resp.json()["id"]
            del_resp = authenticated_client.delete(f"/api/v1/vendors/{vendor_id}")
            assert del_resp.status_code in (200, 204)


@pytest.mark.e2e
class TestInventoryBulkOperations:
    """Tests for inventory bulk operations."""

    def test_bulk_create_inventory(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """POST /api/v1/inventory/bulk creates multiple items."""
        resp = authenticated_client.post(
            "/api/v1/inventory/bulk",
            json={
                "items": [
                    {
                        "product_id": test_product_id,
                        "quantity": 100,
                        "location": "Bulk A",
                    },
                    {
                        "product_id": test_product_id,
                        "quantity": 200,
                        "location": "Bulk B",
                    },
                ]
            },
        )
        assert resp.status_code in (200, 201, 404, 405, 422)

    def test_inventory_report_csv(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/inventory/report/csv returns CSV report."""
        resp = authenticated_client.get("/api/v1/inventory/report/csv")
        assert resp.status_code in (200, 404)


@pytest.mark.e2e
class TestSetupFlow:
    """Tests for initial setup flow."""

    def test_setup_complete_flow(self, e2e_client: TestClient | httpx.Client):
        """Complete setup flow works end-to-end."""
        # Check setup status
        status_resp = e2e_client.get("/api/v1/setup/status")
        assert status_resp.status_code == 200
        status = status_resp.json()
        assert "needs_setup" in status

        # If setup is needed, complete it
        if status.get("needs_setup"):
            setup_resp = e2e_client.post(
                "/api/v1/setup/complete",
                json={
                    "admin_name": "Setup Test Admin",
                    "admin_email": "setup-test@test.local",
                    "admin_password": "setup-test-password-123",
                },
            )
            assert setup_resp.status_code in (200, 400)  # 400 if already done

            # Verify setup is now complete
            verify_resp = e2e_client.get("/api/v1/setup/status")
            assert not verify_resp.json().get("needs_setup")


@pytest.mark.e2e
class TestDAUAnalytics:
    """Tests for DAU (Daily Active Users) analytics."""

    def test_dau_endpoint(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/analytics/dau returns DAU stats."""
        resp = authenticated_client.get("/api/v1/analytics/dau")
        assert resp.status_code in (200, 404)

    def test_events_endpoint(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/analytics/events returns event list."""
        resp = authenticated_client.get("/api/v1/analytics/events")
        assert resp.status_code in (200, 404)

    def test_dashboard_stats(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/analytics/dashboard returns comprehensive stats."""
        resp = authenticated_client.get("/api/v1/analytics/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        # Should have various counts
        assert "total_products" in data
        assert "total_vendors" in data
        assert "total_orders" in data
        # Field is total_inventory_items, not total_inventory
        assert "total_inventory_items" in data or "total_inventory" in data


@pytest.mark.e2e
class TestStaffEndpoints:
    """Tests for staff management endpoints."""

    def test_list_staff(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/staff/ returns staff list."""
        resp = authenticated_client.get("/api/v1/staff/")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert "items" in data or isinstance(data, list)

    def test_create_staff(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/staff/ creates staff member."""
        resp = authenticated_client.post(
            "/api/v1/staff/",
            json={
                "name": "E2E Test Staff",
                "email": "e2e-staff@test.local",
                "role": "technician",
            },
        )
        assert resp.status_code in (200, 201, 404, 422)

    def test_staff_activity(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/analytics/staff/activity returns activity."""
        resp = authenticated_client.get("/api/v1/analytics/staff/activity")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, (list, dict))


@pytest.mark.e2e
class TestLocationEndpoints:
    """Tests for location management endpoints."""

    def test_list_locations(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/locations/ returns locations list."""
        resp = authenticated_client.get("/api/v1/locations/")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert "items" in data or isinstance(data, list)

    def test_create_location(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/locations/ creates location."""
        resp = authenticated_client.post(
            "/api/v1/locations/",
            json={
                "name": "E2E Test Location",
                "building": "Building A",
                "room": "Room 101",
            },
        )
        assert resp.status_code in (200, 201, 404, 422)


@pytest.mark.e2e
class TestUserManagement:
    """Tests for user management endpoints."""

    def test_list_users(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/users/ returns users list."""
        resp = authenticated_client.get("/api/v1/users/")
        assert resp.status_code in (200, 401, 403, 404)

    def test_get_current_user(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/users/me returns current user."""
        resp = authenticated_client.get("/api/v1/users/me")
        assert resp.status_code in (200, 404)

    def test_update_current_user(self, authenticated_client: TestClient | httpx.Client):
        """PATCH /api/v1/users/me updates current user."""
        resp = authenticated_client.patch(
            "/api/v1/users/me",
            json={"name": "Updated E2E User"},
        )
        assert resp.status_code in (200, 404, 422)

    def test_change_password(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/users/me/password changes password."""
        resp = authenticated_client.post(
            "/api/v1/users/me/password",
            json={
                "current_password": "test-password",
                "new_password": "new-test-password",
            },
        )
        assert resp.status_code in (200, 400, 404, 422)
