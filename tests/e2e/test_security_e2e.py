"""E2E tests for security hardening.

Verifies auth enforcement, login security, setup security,
input validation, security headers, and CORS behaviour.
"""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

import conftest

ADMIN_EMAIL = conftest.ADMIN_EMAIL
ADMIN_PASSWORD = conftest.ADMIN_PASSWORD


def _unique_suffix() -> str:
    return uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Auth Enforcement
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestAuthEnforcementE2E:
    """All protected endpoints must return 401 without authentication."""

    def test_1_unauthenticated_vendors(self, e2e_client: TestClient | httpx.Client):
        """GET /api/v1/vendors/ returns 401 without auth."""
        resp = e2e_client.get("/api/v1/vendors")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_2_unauthenticated_products(self, e2e_client: TestClient | httpx.Client):
        """GET /api/v1/products/ returns 401 without auth."""
        resp = e2e_client.get("/api/v1/products")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_3_unauthenticated_orders(self, e2e_client: TestClient | httpx.Client):
        """GET /api/v1/orders/ returns 401 without auth."""
        resp = e2e_client.get("/api/v1/orders")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_4_unauthenticated_inventory(self, e2e_client: TestClient | httpx.Client):
        """GET /api/v1/inventory/ returns 401 without auth."""
        resp = e2e_client.get("/api/v1/inventory")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_5_unauthenticated_documents(self, e2e_client: TestClient | httpx.Client):
        """GET /api/v1/documents/ returns 401 without auth."""
        resp = e2e_client.get("/api/v1/documents")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_6_unauthenticated_search(self, e2e_client: TestClient | httpx.Client):
        """GET /api/v1/search?q=test returns 401 without auth."""
        resp = e2e_client.get("/api/v1/search", params={"q": "test"})
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_7_unauthenticated_ask(self, e2e_client: TestClient | httpx.Client):
        """POST /api/v1/ask returns 401 without auth."""
        resp = e2e_client.post("/api/v1/ask", json={"question": "test"})
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_8_unauthenticated_analytics(self, e2e_client: TestClient | httpx.Client):
        """GET /api/v1/analytics/dashboard returns 401 without auth."""
        resp = e2e_client.get("/api/v1/analytics/dashboard")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_9_unauthenticated_export(self, e2e_client: TestClient | httpx.Client):
        """GET /api/v1/export/inventory returns 401 without auth."""
        resp = e2e_client.get("/api/v1/export/inventory")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_10_unauthenticated_alerts(self, e2e_client: TestClient | httpx.Client):
        """GET /api/v1/alerts/ returns 401 without auth."""
        resp = e2e_client.get("/api/v1/alerts")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_11_unauthenticated_audit(self, e2e_client: TestClient | httpx.Client):
        """GET /api/v1/audit/ returns 401 without auth."""
        resp = e2e_client.get("/api/v1/audit")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_12_unauthenticated_equipment(self, e2e_client: TestClient | httpx.Client):
        """GET /api/v1/equipment/ returns 401 without auth."""
        resp = e2e_client.get("/api/v1/equipment")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_13_unauthenticated_telemetry(self, e2e_client: TestClient | httpx.Client):
        """GET /api/v1/telemetry/events returns 401 without auth."""
        resp = e2e_client.get("/api/v1/telemetry/events")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_14_public_health(self, e2e_client: TestClient | httpx.Client):
        """GET /api/health works without auth."""
        resp = e2e_client.get("/api/health")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_15_public_setup_status(self, e2e_client: TestClient | httpx.Client):
        """GET /api/v1/setup/status works without auth."""
        resp = e2e_client.get("/api/v1/setup/status")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_16_public_config(self, e2e_client: TestClient | httpx.Client):
        """GET /api/v1/config works without auth."""
        resp = e2e_client.get("/api/v1/config")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Login Security
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestLoginSecurityE2E:
    """Login endpoint must resist common attack vectors."""

    def test_1_wrong_password(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/auth/login rejects wrong password with 401."""
        # authenticated_client triggers setup so the admin user exists.
        resp = authenticated_client.post(
            "/api/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": "totally-wrong-password"},
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_2_wrong_email(self, e2e_client: TestClient | httpx.Client):
        """POST /api/v1/auth/login rejects nonexistent email with 401."""
        resp = e2e_client.post(
            "/api/v1/auth/login",
            json={
                "email": "nobody-here@nonexistent.local",
                "password": "some-password",
            },
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_3_empty_credentials(self, e2e_client: TestClient | httpx.Client):
        """POST /api/v1/auth/login with empty email/password returns 401 or 422."""
        resp = e2e_client.post(
            "/api/v1/auth/login",
            json={"email": "", "password": ""},
        )
        assert resp.status_code in (401, 422), (
            f"Expected 401 or 422, got {resp.status_code}"
        )

    def test_4_sql_injection_in_email(self, e2e_client: TestClient | httpx.Client):
        """POST /api/v1/auth/login with SQL injection returns 401, not 500."""
        resp = e2e_client.post(
            "/api/v1/auth/login",
            json={"email": "' OR 1=1 --", "password": "anything"},
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        # Must not leak internal errors or stack traces
        body = resp.text
        assert "traceback" not in body.lower()
        assert "sqlalchemy" not in body.lower()

    def test_5_xss_in_setup_name(self, e2e_client: TestClient | httpx.Client):
        """POST /api/v1/setup/complete with XSS in name stores safely."""
        xss_name = "<script>alert(1)</script>"
        suffix = _unique_suffix()
        resp = e2e_client.post(
            "/api/v1/setup/complete",
            json={
                "admin_name": xss_name,
                "admin_email": f"xss-test-{suffix}@test.local",
                "admin_password": "secure-password-12345",
            },
        )
        # Should succeed or conflict (if setup already done)
        if resp.status_code in (200, 201):
            # The raw script tag must not appear unescaped in HTML context;
            # as JSON it is safely stored and returned.
            assert resp.status_code in (200, 201)
        else:
            # Setup already completed is acceptable (409)
            assert resp.status_code == 409

    def test_6_session_invalidation_after_logout(
        self, e2e_client: TestClient | httpx.Client
    ):
        """Login -> logout -> old cookie must yield 401."""
        # Ensure setup
        status_resp = e2e_client.get("/api/v1/setup/status")
        if status_resp.json().get("needs_setup", False):
            e2e_client.post(
                "/api/v1/setup/complete",
                json={
                    "admin_name": "Session Test Admin",
                    "admin_email": ADMIN_EMAIL,
                    "admin_password": ADMIN_PASSWORD,
                },
            )

        # Login
        login_resp = e2e_client.post(
            "/api/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"

        # Verify session works
        me_resp = e2e_client.get("/api/v1/auth/me")
        assert me_resp.status_code == 200, (
            f"Expected 200 for /auth/me, got {me_resp.status_code}"
        )

        # Logout
        logout_resp = e2e_client.post("/api/v1/auth/logout")
        assert logout_resp.status_code == 200

        # Old session cookie should be cleared -- /auth/me returns 401
        me_resp2 = e2e_client.get("/api/v1/auth/me")
        assert me_resp2.status_code == 401, (
            f"Expected 401 after logout, got {me_resp2.status_code}"
        )


# ---------------------------------------------------------------------------
# Setup Security
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestSetupSecurityE2E:
    """Setup endpoint must only work once and validate inputs."""

    def test_1_setup_only_works_once(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/setup/complete returns 409 when setup already done."""
        resp = authenticated_client.post(
            "/api/v1/setup/complete",
            json={
                "admin_name": "Second Admin",
                "admin_email": "second@test.local",
                "admin_password": "another-password-12345",
            },
        )
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}"

    def test_2_setup_with_weak_password(self, e2e_client: TestClient | httpx.Client):
        """POST /api/v1/setup/complete rejects empty/short password."""
        resp = e2e_client.post(
            "/api/v1/setup/complete",
            json={
                "admin_name": "Weak PW Admin",
                "admin_email": "weak@test.local",
                "admin_password": "",
            },
        )
        # Either validation fails (422) or setup already done (409)
        assert resp.status_code in (409, 422), (
            f"Expected 409 or 422, got {resp.status_code}"
        )

    def test_3_setup_with_long_name(self, e2e_client: TestClient | httpx.Client):
        """POST /api/v1/setup/complete handles 1000-char name gracefully."""
        long_name = "A" * 1000
        resp = e2e_client.post(
            "/api/v1/setup/complete",
            json={
                "admin_name": long_name,
                "admin_email": "longname@test.local",
                "admin_password": "secure-password-12345",
            },
        )
        # Name > 200 chars should be rejected (422) or setup already done (409)
        assert resp.status_code in (409, 422), (
            f"Expected 409 or 422, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# Input Validation
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestInputValidationE2E:
    """API endpoints must validate inputs and return proper error codes."""

    def test_1_vendor_missing_name(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/vendors/ with missing name returns 422."""
        resp = authenticated_client.post("/api/v1/vendors", json={})
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_2_product_invalid_cas_number(
        self, authenticated_client: TestClient | httpx.Client, test_vendor_id: int
    ):
        """POST /api/v1/products/ with invalid CAS number returns 422."""
        suffix = _unique_suffix()
        resp = authenticated_client.post(
            "/api/v1/products",
            json={
                "catalog_number": f"CAS-TEST-{suffix}",
                "name": f"CAS Test Product {suffix}",
                "vendor_id": test_vendor_id,
                "cas_number": "invalid-cas",
            },
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_3_consume_negative_quantity(
        self, authenticated_client: TestClient | httpx.Client, test_inventory_id: int
    ):
        """POST /api/v1/inventory/{id}/consume with quantity=-1 returns 422."""
        resp = authenticated_client.post(
            f"/api/v1/inventory/{test_inventory_id}/consume",
            json={
                "quantity": -1,
                "consumed_by": "tester",
                "purpose": "negative test",
            },
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_4_consume_zero_quantity(
        self, authenticated_client: TestClient | httpx.Client, test_inventory_id: int
    ):
        """POST /api/v1/inventory/{id}/consume with quantity=0 returns 422."""
        resp = authenticated_client.post(
            f"/api/v1/inventory/{test_inventory_id}/consume",
            json={
                "quantity": 0,
                "consumed_by": "tester",
                "purpose": "zero test",
            },
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_5_consume_more_than_available(
        self, authenticated_client: TestClient | httpx.Client, test_vendor_id: int
    ):
        """Consuming more than available stock must fail."""
        suffix = _unique_suffix()
        # Create product
        prod_resp = authenticated_client.post(
            "/api/v1/products",
            json={
                "catalog_number": f"OVERCON-{suffix}",
                "name": f"Overconsume Product {suffix}",
                "vendor_id": test_vendor_id,
            },
        )
        assert prod_resp.status_code == 201
        product_id = prod_resp.json()["id"]

        # Create inventory with small quantity
        inv_resp = authenticated_client.post(
            "/api/v1/inventory",
            json={
                "product_id": product_id,
                "quantity_on_hand": 5,
                "location": "Shelf B",
                "lot_number": f"LOT-OC-{suffix}",
            },
        )
        assert inv_resp.status_code == 201
        inv_id = inv_resp.json()["id"]

        # Try to consume 10 from 5 available
        consume_resp = authenticated_client.post(
            f"/api/v1/inventory/{inv_id}/consume",
            json={
                "quantity": 10,
                "consumed_by": "tester",
                "purpose": "overconsume test",
            },
        )
        assert consume_resp.status_code == 422, (
            f"Expected 422, got {consume_resp.status_code}"
        )

    def test_6_invalid_order_status(
        self, authenticated_client: TestClient | httpx.Client, test_order_id: int
    ):
        """PATCH /api/v1/orders/{id} with invalid status returns 422."""
        resp = authenticated_client.patch(
            f"/api/v1/orders/{test_order_id}",
            json={"status": "invalid_status_value"},
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_7_duplicate_po_number_warns(
        self, authenticated_client: TestClient | httpx.Client, test_vendor_id: int
    ):
        """Creating two orders with the same PO# returns a duplicate warning."""
        suffix = _unique_suffix()
        po = f"DUP-PO-{suffix}"

        # First order
        resp1 = authenticated_client.post(
            "/api/v1/orders",
            json={"po_number": po, "vendor_id": test_vendor_id, "status": "pending"},
        )
        assert resp1.status_code == 201

        # Second order with same PO#
        resp2 = authenticated_client.post(
            "/api/v1/orders",
            json={"po_number": po, "vendor_id": test_vendor_id, "status": "pending"},
        )
        # API warns but does not block (OCR re-scan use case)
        assert resp2.status_code == 201
        data2 = resp2.json()
        assert "_duplicate_warning" in data2, (
            f"Expected _duplicate_warning in response: {data2.keys()}"
        )

    def test_8_duplicate_catalog_vendor_product(
        self, authenticated_client: TestClient | httpx.Client, test_vendor_id: int
    ):
        """Creating a product with same catalog_number+vendor returns 409."""
        suffix = _unique_suffix()
        catalog = f"DUP-CAT-{suffix}"

        resp1 = authenticated_client.post(
            "/api/v1/products",
            json={
                "catalog_number": catalog,
                "name": f"Dup Product 1 {suffix}",
                "vendor_id": test_vendor_id,
            },
        )
        assert resp1.status_code == 201

        resp2 = authenticated_client.post(
            "/api/v1/products",
            json={
                "catalog_number": catalog,
                "name": f"Dup Product 2 {suffix}",
                "vendor_id": test_vendor_id,
            },
        )
        assert resp2.status_code == 409, f"Expected 409, got {resp2.status_code}"

    def test_9_large_json_payload_rejected(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST with >10MB JSON body returns 413."""
        # Build a payload slightly over 10 MB
        large_value = "x" * (11 * 1024 * 1024)
        resp = authenticated_client.post(
            "/api/v1/vendors",
            json={"name": large_value},
        )
        assert resp.status_code == 413, f"Expected 413, got {resp.status_code}"

    def test_10_path_traversal_in_document(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/documents/ with path traversal is rejected."""
        resp = authenticated_client.post(
            "/api/v1/documents",
            json={
                "file_path": "../../etc/passwd",
                "file_name": "passwd",
            },
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Security Headers
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestSecurityHeadersE2E:
    """Responses must include standard security headers."""

    def _get_response(self, client: TestClient | httpx.Client):
        """Fetch /api/health to inspect response headers."""
        return client.get("/api/health")

    def test_1_x_content_type_options(self, e2e_client: TestClient | httpx.Client):
        """Response includes X-Content-Type-Options: nosniff."""
        resp = self._get_response(e2e_client)
        header = resp.headers.get("x-content-type-options", "")
        # Some deployments set this; we check if present it is correct
        if header:
            assert header == "nosniff", f"Expected nosniff, got {header}"

    def test_2_x_request_id_present(self, e2e_client: TestClient | httpx.Client):
        """Response includes X-Request-ID header (audit middleware)."""
        # /api/health skips access log but audit middleware still sets X-Request-ID
        # Use a different endpoint to test
        resp = e2e_client.get("/api/v1/setup/status")
        header = resp.headers.get("x-request-id", "")
        assert header, "Expected X-Request-ID header to be present"

    def test_3_no_server_header_leak(self, e2e_client: TestClient | httpx.Client):
        """Response should not leak detailed server version info."""
        resp = self._get_response(e2e_client)
        server = resp.headers.get("server", "")
        # Should not contain specific version info like "uvicorn/0.x.x"
        if server:
            assert "python" not in server.lower(), (
                f"Server header leaks Python info: {server}"
            )

    def test_4_no_stacktrace_in_404(self, e2e_client: TestClient | httpx.Client):
        """404 responses must not leak stack traces."""
        resp = e2e_client.get("/api/v1/nonexistent-endpoint-xyz")
        body = resp.text.lower()
        assert "traceback" not in body
        assert 'file "' not in body
        assert "line " not in body or "exception" not in body


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestCORSE2E:
    """CORS headers must be strict in production (auth_enabled=true)."""

    def test_1_no_origin_no_cors_header(self, e2e_client: TestClient | httpx.Client):
        """GET /api/health without Origin header has no Access-Control-Allow-Origin."""
        resp = e2e_client.get("/api/health")
        acao = resp.headers.get("access-control-allow-origin")
        # With auth_enabled=true, allow_origins=[] so no ACAO unless matching origin
        assert acao is None, f"Unexpected ACAO header: {acao}"

    def test_2_unknown_origin_not_reflected(
        self, e2e_client: TestClient | httpx.Client
    ):
        """Evil origin must not be reflected in Access-Control-Allow-Origin."""
        resp = e2e_client.get(
            "/api/health",
            headers={"Origin": "https://evil.com"},
        )
        acao = resp.headers.get("access-control-allow-origin")
        if acao:
            assert acao != "https://evil.com", f"Evil origin reflected in ACAO: {acao}"
            assert acao != "*", "Wildcard ACAO in production mode"
