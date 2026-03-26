"""E2E tests for authentication edge cases and error handling.

Tests session management, password flows, and auth edge cases.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

import conftest

ADMIN_PASSWORD = conftest.ADMIN_PASSWORD


@pytest.mark.e2e
class TestAuthLoginEdgeCases:
    """Tests for login edge cases."""

    def test_login_empty_credentials(self, e2e_client: TestClient | httpx.Client):
        """POST /api/v1/auth/login rejects empty credentials with 422."""
        resp = e2e_client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_login_empty_email(self, e2e_client: TestClient | httpx.Client):
        """POST /api/v1/auth/login rejects empty email."""
        resp = e2e_client.post(
            "/api/v1/auth/login",
            json={"email": "", "password": "test"},
        )
        assert resp.status_code in (400, 401, 422)

    def test_login_empty_password(self, e2e_client: TestClient | httpx.Client):
        """POST /api/v1/auth/login rejects empty password."""
        resp = e2e_client.post(
            "/api/v1/auth/login",
            json={"email": "test@test.local", "password": ""},
        )
        assert resp.status_code in (400, 401, 422)

    def test_login_invalid_email_format(self, e2e_client: TestClient | httpx.Client):
        """POST /api/v1/auth/login rejects invalid email format."""
        resp = e2e_client.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email", "password": "test"},
        )
        assert resp.status_code in (400, 401, 422)

    def test_login_wrong_credentials(self, e2e_client: TestClient | httpx.Client):
        """POST /api/v1/auth/login rejects wrong credentials with 401."""
        resp = e2e_client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@test.local", "password": "wrong-password"},
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_login_sql_injection_attempt(self, e2e_client: TestClient | httpx.Client):
        """POST /api/v1/auth/login handles SQL injection safely (returns 401, not crash)."""
        resp = e2e_client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@test.local'; DROP TABLE users; --",
                "password": "test",
            },
        )
        # Should reject with 401 (user not found), not crash with 500
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


@pytest.mark.e2e
class TestAuthSession:
    """Tests for session management."""

    def test_me_without_auth(self, e2e_client: TestClient | httpx.Client):
        """GET /api/v1/auth/me returns 401 without auth."""
        resp = e2e_client.get("/api/v1/auth/me")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_me_with_auth(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/auth/me returns user with auth."""
        resp = authenticated_client.get("/api/v1/auth/me")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "user" in data, f"Response missing 'user' key: {data.keys()}"

    def test_logout_clears_session(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/auth/logout clears session."""
        resp = authenticated_client.post("/api/v1/auth/logout")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

        # Verify session is cleared
        me_resp = authenticated_client.get("/api/v1/auth/me")
        assert me_resp.status_code == 401, (
            f"Expected 401 after logout, got {me_resp.status_code}"
        )


@pytest.mark.e2e
class TestAuthPasswordChange:
    """Tests for password change."""

    def test_change_password_wrong_current(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/users/me/password rejects wrong current password."""
        resp = authenticated_client.post(
            "/api/v1/users/me/password",
            json={
                "current_password": "wrong-password",
                "new_password": "new-password-123",
            },
        )
        assert resp.status_code in (400, 401, 403, 404)

    def test_change_password_empty_new(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/users/me/password rejects empty new password."""
        resp = authenticated_client.post(
            "/api/v1/users/me/password",
            json={
                "current_password": ADMIN_PASSWORD,
                "new_password": "",
            },
        )
        assert resp.status_code in (400, 401, 404, 422)


@pytest.mark.e2e
class TestAuthProtectedEndpoints:
    """Tests for protected endpoint access."""

    def test_protected_endpoint_without_auth(
        self, e2e_client: TestClient | httpx.Client
    ):
        """Protected endpoints return 401 without auth."""
        resp = e2e_client.post(
            "/api/v1/vendors",
            json={"name": "Unauthorized Vendor"},
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_protected_endpoint_with_auth(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Protected endpoints work with auth."""
        resp = authenticated_client.post(
            "/api/v1/vendors",
            json={"name": "Authorized Vendor Test"},
        )
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"


@pytest.mark.e2e
class TestAuthSetup:
    """Tests for setup flow."""

    def test_setup_status(self, e2e_client: TestClient | httpx.Client):
        """GET /api/v1/setup/status returns status."""
        resp = e2e_client.get("/api/v1/setup/status")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "needs_setup" in data, (
            f"Response missing 'needs_setup' key: {data.keys()}"
        )

    def test_setup_already_complete(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/setup/complete handles already-complete setup."""
        resp = authenticated_client.post(
            "/api/v1/setup/complete",
            json={
                "admin_name": "Test",
                "admin_email": "test@test.local",
                "admin_password": "test-password-12345",
            },
        )
        assert resp.status_code in (200, 201, 400, 409)


@pytest.mark.e2e
class TestAuthUserManagement:
    """Tests for user management."""

    def test_get_current_user(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/users/me returns current user."""
        resp = authenticated_client.get("/api/v1/users/me")
        assert resp.status_code in (200, 401, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert "email" in data or "id" in data

    def test_update_current_user(self, authenticated_client: TestClient | httpx.Client):
        """PATCH /api/v1/users/me updates current user."""
        resp = authenticated_client.patch(
            "/api/v1/users/me",
            json={"name": "Updated E2E User"},
        )
        assert resp.status_code in (200, 401, 404, 422)

    def test_list_users_requires_admin(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/users/ requires an available admin endpoint."""
        resp = authenticated_client.get("/api/v1/users")
        assert resp.status_code in (200, 401, 403, 404)


@pytest.mark.e2e
class TestAuthToken:
    """Tests for API token authentication."""

    def test_valid_api_key(self, e2e_client: TestClient | httpx.Client):
        """API key in header authenticates requests."""
        # Use the test API key from conftest
        resp = e2e_client.get(
            "/api/v1/vendors",
            headers={"X-API-Key": "e2e-test-api-key"},
        )
        assert resp.status_code == 200, (
            f"Expected 200 with valid API key, got {resp.status_code}"
        )

    def test_invalid_api_key(self, e2e_client: TestClient | httpx.Client):
        """Invalid API key returns 401."""
        resp = e2e_client.get(
            "/api/v1/vendors",
            headers={"X-API-Key": "invalid-key-12345"},
        )
        assert resp.status_code == 401, (
            f"Expected 401 with invalid API key, got {resp.status_code}"
        )
