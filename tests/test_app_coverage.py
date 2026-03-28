"""Tests for api/app.py — middleware, auth, setup, health, config, SPA checks, static serving."""

import os

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(db_session):
    os.environ["AUTH_ENABLED"] = "false"
    os.environ["UPLOAD_DIR"] = "/tmp/test-uploads"
    from lab_manager.config import get_settings

    get_settings.cache_clear()
    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# SPA asset readiness check (unit tests)
# ---------------------------------------------------------------------------


class TestSpaAssetsReady:
    def test_missing_dist_dir(self, tmp_path):
        from lab_manager.api.app import _spa_assets_ready

        assert _spa_assets_ready(tmp_path) is False

    def test_missing_index_html(self, tmp_path):
        from lab_manager.api.app import _spa_assets_ready

        dist = tmp_path / "dist"
        dist.mkdir()
        assert _spa_assets_ready(tmp_path) is False

    def test_missing_assets_dir(self, tmp_path):
        from lab_manager.api.app import _spa_assets_ready

        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html></html>")
        assert _spa_assets_ready(tmp_path) is False

    def test_no_asset_refs_in_html(self, tmp_path):
        from lab_manager.api.app import _spa_assets_ready

        dist = tmp_path / "dist"
        dist.mkdir()
        assets = dist / "assets"
        assets.mkdir()
        (dist / "index.html").write_text("<html><body>Hello</body></html>")
        assert _spa_assets_ready(tmp_path) is False

    def test_no_js_refs(self, tmp_path):
        from lab_manager.api.app import _spa_assets_ready

        dist = tmp_path / "dist"
        dist.mkdir()
        assets = dist / "assets"
        assets.mkdir()
        (dist / "index.html").write_text(
            '<html><link href="/assets/style.css" rel="stylesheet"></html>'
        )
        assert _spa_assets_ready(tmp_path) is False

    def test_missing_asset_file(self, tmp_path):
        from lab_manager.api.app import _spa_assets_ready

        dist = tmp_path / "dist"
        dist.mkdir()
        assets = dist / "assets"
        assets.mkdir()
        (dist / "index.html").write_text(
            '<html><script src="/assets/app.js"></script></html>'
        )
        # app.js doesn't exist
        assert _spa_assets_ready(tmp_path) is False

    def test_all_assets_present(self, tmp_path):
        from lab_manager.api.app import _spa_assets_ready

        dist = tmp_path / "dist"
        dist.mkdir()
        assets = dist / "assets"
        assets.mkdir()
        (assets / "app.js").write_text("console.log('hi')")
        (assets / "style.css").write_text("body{}")
        (dist / "index.html").write_text(
            '<html><script src="/assets/app.js"></script>'
            '<link href="/assets/style.css" rel="stylesheet"></html>'
        )
        assert _spa_assets_ready(tmp_path) is True


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "services" in data


# ---------------------------------------------------------------------------
# Config endpoint
# ---------------------------------------------------------------------------


class TestConfigEndpoint:
    def test_config(self, client):
        resp = client.get("/api/v1/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "lab_name" in data
        assert "version" in data


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------


class TestAuthMe:
    def test_auth_me_dev_mode(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["role"] == "pi"


class TestLogout:
    def test_logout(self, client):
        resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Login endpoint
# ---------------------------------------------------------------------------


class TestLogin:
    def test_login_invalid_credentials(self, client, db_session):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Setup endpoints
# ---------------------------------------------------------------------------


class TestSetupStatus:
    def test_needs_setup_when_no_admin(self, client, db_session):
        resp = client.get("/api/v1/setup/status")
        assert resp.status_code == 200
        assert resp.json()["needs_setup"] is True


class TestSetupComplete:
    def test_setup_validation_empty_name(self, client, db_session):
        resp = client.post(
            "/api/v1/setup/complete",
            json={
                "admin_name": "",
                "admin_email": "admin@test.com",
                "admin_password": "password123",
            },
        )
        assert resp.status_code == 422

    def test_setup_validation_invalid_email(self, client, db_session):
        resp = client.post(
            "/api/v1/setup/complete",
            json={
                "admin_name": "Admin",
                "admin_email": "not-an-email",
                "admin_password": "password123",
            },
        )
        assert resp.status_code == 422

    def test_setup_validation_short_password(self, client, db_session):
        resp = client.post(
            "/api/v1/setup/complete",
            json={
                "admin_name": "Admin",
                "admin_email": "admin@test.com",
                "admin_password": "short",
            },
        )
        assert resp.status_code == 422

    def test_setup_success(self, client, db_session):
        resp = client.post(
            "/api/v1/setup/complete",
            json={
                "admin_name": "Admin User",
                "admin_email": "admin@test.com",
                "admin_password": "securepassword123",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_setup_already_completed(self, client, db_session):
        # First setup
        client.post(
            "/api/v1/setup/complete",
            json={
                "admin_name": "Admin User",
                "admin_email": "admin@test.com",
                "admin_password": "securepassword123",
            },
        )
        # Second setup should fail
        resp = client.post(
            "/api/v1/setup/complete",
            json={
                "admin_name": "Another Admin",
                "admin_email": "admin2@test.com",
                "admin_password": "securepassword456",
            },
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Rate limit handler
# ---------------------------------------------------------------------------


class TestRateLimitHandler:
    def test_rate_limit_response(self):
        """Verify rate limit handler is registered."""
        os.environ["AUTH_ENABLED"] = "false"
        from lab_manager.config import get_settings

        get_settings.cache_clear()
        from lab_manager.api.app import create_app

        app = create_app()
        from slowapi.errors import RateLimitExceeded

        assert RateLimitExceeded in app.exception_handlers
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Upload file serving
# ---------------------------------------------------------------------------


class TestUploadServing:
    def test_serve_existing_file(self, db_session, tmp_path):
        os.environ["AUTH_ENABLED"] = "false"
        os.environ["UPLOAD_DIR"] = str(tmp_path)
        from lab_manager.config import get_settings

        get_settings.cache_clear()
        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db

        (tmp_path / "test.txt").write_text("hello world")

        app = create_app()

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/uploads/test.txt")
            assert resp.status_code == 200
            assert resp.text == "hello world"
        get_settings.cache_clear()

    def test_serve_nonexistent_file(self, db_session, tmp_path):
        os.environ["AUTH_ENABLED"] = "false"
        os.environ["UPLOAD_DIR"] = str(tmp_path)
        from lab_manager.config import get_settings

        get_settings.cache_clear()
        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db

        app = create_app()

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/uploads/nonexistent.txt")
            assert resp.status_code == 404
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------


class TestCORSMiddleware:
    def test_dev_mode_cors_wildcard(self, client):
        resp = client.options(
            "/api/v1/vendors/",
            headers={
                "origin": "http://localhost:3000",
                "access-control-request-method": "GET",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "*"


# ---------------------------------------------------------------------------
# Root endpoint (serves index.html)
# ---------------------------------------------------------------------------


class TestRootEndpoint:
    def test_root_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# Auth middleware — X-User header in dev mode
# ---------------------------------------------------------------------------


class TestAuthMiddlewareDevMode:
    def test_x_user_header_strips_control_chars(self, client):
        resp = client.get("/api/v1/vendors/", headers={"X-User": "test\x00user\r\n"})
        assert resp.status_code == 200

    def test_x_user_header_truncated(self, client):
        long_user = "a" * 200
        resp = client.get("/api/v1/vendors/", headers={"X-User": long_user})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Auth middleware — production mode
# ---------------------------------------------------------------------------


class TestAuthMiddlewareProdMode:
    def test_unauthenticated_returns_401(self, db_session):
        os.environ["AUTH_ENABLED"] = "true"
        os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-testing-minimum-16-chars"
        from lab_manager.config import get_settings

        get_settings.cache_clear()
        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db

        app = create_app()

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/v1/vendors/")
            assert resp.status_code == 401
        get_settings.cache_clear()

    def test_api_key_auth(self, db_session):
        os.environ["AUTH_ENABLED"] = "true"
        os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-testing-minimum-16-chars"
        os.environ["API_KEY"] = "test-api-key-12345"
        from lab_manager.config import get_settings

        get_settings.cache_clear()
        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db

        app = create_app()

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get(
                "/api/v1/vendors/", headers={"X-Api-Key": "test-api-key-12345"}
            )
            assert resp.status_code == 200
        get_settings.cache_clear()

    def test_wrong_api_key_returns_401(self, db_session):
        os.environ["AUTH_ENABLED"] = "true"
        os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-testing-minimum-16-chars"
        os.environ["API_KEY"] = "test-api-key-12345"
        from lab_manager.config import get_settings

        get_settings.cache_clear()
        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db

        app = create_app()

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/v1/vendors/", headers={"X-Api-Key": "wrong-key"})
            assert resp.status_code == 401
        get_settings.cache_clear()

    def test_allowlisted_paths_no_auth(self, db_session):
        os.environ["AUTH_ENABLED"] = "true"
        os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-testing-minimum-16-chars"
        from lab_manager.config import get_settings

        get_settings.cache_clear()
        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db

        app = create_app()

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/v1/config")
            assert resp.status_code == 200
        get_settings.cache_clear()
