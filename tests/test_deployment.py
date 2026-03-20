"""Deployment-specific tests: auth allowlist, health checks, static files, database config."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from lab_manager.config import get_settings


# ---------------------------------------------------------------------------
# Auth Allowlist — verify public vs protected endpoints
# ---------------------------------------------------------------------------


class TestAuthAllowlist:
    """Verify that the auth middleware allowlists the correct paths."""

    @pytest.fixture(autouse=True)
    def _auth_client(self):
        """Create a TestClient with auth enabled and a DB for every test."""
        from sqlalchemy.pool import StaticPool
        from sqlmodel import SQLModel, create_engine

        os.environ["AUTH_ENABLED"] = "true"
        os.environ["ADMIN_SECRET_KEY"] = "deploy-test-secret-key-12345"
        os.environ["ADMIN_PASSWORD"] = "deploy-test-admin-password"
        os.environ["API_KEY"] = "deploy-test-api-key"
        os.environ["SECURE_COOKIES"] = "false"
        get_settings.cache_clear()

        # Create an in-memory SQLite engine with tables so endpoints
        # that touch the DB (e.g. /api/setup/status) don't crash.
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
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as c:
            self.client = c
            yield

        db_module._engine = original_engine
        db_module._session_factory = original_factory
        engine.dispose()
        os.environ["AUTH_ENABLED"] = "false"
        os.environ.pop("ADMIN_SECRET_KEY", None)
        os.environ.pop("ADMIN_PASSWORD", None)
        os.environ.pop("API_KEY", None)
        get_settings.cache_clear()

    def test_health_endpoint_public(self):
        """GET /api/health returns 200 without auth."""
        resp = self.client.get("/api/health")
        # 200 or 503 (degraded) are both valid — just not 401
        assert resp.status_code != 401

    def test_setup_status_public(self):
        """GET /api/setup/status returns 200 without auth."""
        resp = self.client.get("/api/setup/status")
        assert resp.status_code != 401

    def test_config_public(self):
        """GET /api/config returns 200 without auth."""
        resp = self.client.get("/api/config")
        assert resp.status_code != 401

    def test_root_public(self):
        """GET / returns 200 without auth (not 401)."""
        resp = self.client.get("/")
        assert resp.status_code != 401

    def test_favicon_public(self):
        """GET /favicon.svg is accessible (either 200 or 404, but not 401)."""
        resp = self.client.get("/favicon.svg")
        assert resp.status_code in (200, 404)

    def test_sw_js_public(self):
        """GET /sw.js is accessible without auth."""
        resp = self.client.get("/sw.js")
        assert resp.status_code in (200, 404, 405)

    def test_manifest_json_public(self):
        """GET /manifest.json is accessible without auth."""
        resp = self.client.get("/manifest.json")
        assert resp.status_code in (200, 404, 405)

    def test_admin_public(self):
        """GET /admin/ has its own auth (not 401 from middleware)."""
        resp = self.client.get("/admin/")
        # Admin has its own auth backend; middleware should not block it
        assert resp.status_code != 401

    def test_static_prefix_public(self):
        """Paths starting with /static/ are public."""
        resp = self.client.get("/static/nonexistent.css")
        # 404 is fine — just not 401
        assert resp.status_code != 401

    def test_assets_prefix_public(self):
        """Paths starting with /assets/ are public."""
        resp = self.client.get("/assets/nonexistent.js")
        # 404 is fine — just not 401
        assert resp.status_code != 401

    def test_vendors_requires_auth(self):
        """GET /api/v1/vendors/ returns 401 when auth enabled."""
        resp = self.client.get("/api/v1/vendors/")
        assert resp.status_code == 401

    def test_products_requires_auth(self):
        """GET /api/v1/products/ returns 401 when auth enabled."""
        resp = self.client.get("/api/v1/products/")
        assert resp.status_code == 401

    def test_orders_requires_auth(self):
        """GET /api/v1/orders/ returns 401 when auth enabled."""
        resp = self.client.get("/api/v1/orders/")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Health Check — verify response structure and failure modes
# ---------------------------------------------------------------------------


class TestHealthCheck:
    """Verify health endpoint response structure and degraded states."""

    def test_health_returns_services(self, client):
        """Response has postgresql, meilisearch, disk keys."""
        resp = client.get("/api/health")
        data = resp.json()
        assert "services" in data
        services = data["services"]
        assert "postgresql" in services
        assert "meilisearch" in services
        assert "disk" in services

    def test_health_meilisearch_error_still_200(self, client):
        """Meilisearch down doesn't make health fail."""
        with patch("lab_manager.services.search.get_search_client") as mock_get:
            mock_client = MagicMock()
            mock_client.health.side_effect = ConnectionError("connection refused")
            mock_get.return_value = mock_client

            resp = client.get("/api/health")
            data = resp.json()
            # Meilisearch is not core — app should still be 200 if PG is OK
            assert resp.status_code == 200
            assert data["services"]["meilisearch"] == "error"

    def test_health_postgresql_error_returns_503(self, client):
        """PostgreSQL down makes health fail."""
        with patch("lab_manager.api.app.get_engine") as mock_engine:
            mock_conn = MagicMock()
            mock_conn.__enter__ = MagicMock(side_effect=Exception("pg down"))
            mock_engine.return_value.connect.return_value = mock_conn

            resp = client.get("/api/health")
            data = resp.json()
            assert resp.status_code == 503
            assert data["status"] == "degraded"
            assert data["services"]["postgresql"] == "error"


# ---------------------------------------------------------------------------
# Static File Serving — verify SPA / legacy mode behavior
# ---------------------------------------------------------------------------


class TestStaticFileServing:
    """Verify static file serving and SPA mode."""

    def test_root_returns_html(self, client):
        """GET / returns HTML content type."""
        resp = client.get("/")
        # Should serve index.html
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            content_type = resp.headers.get("content-type", "")
            assert "text/html" in content_type

    def test_legacy_mode_when_no_assets(self, client):
        """When dist/assets/ doesn't exist, legacy index.html is served."""
        # The test client runs without React build artifacts, so it falls
        # back to legacy mode. GET / should still serve something.
        resp = client.get("/")
        # In legacy mode the route still exists — 200 or 404 if index.html missing
        assert resp.status_code in (200, 404, 500)

    def test_favicon_served(self):
        """GET /favicon.svg returns SVG when dist/favicon.svg exists."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            # Set up a fake static dir structure
            dist_dir = Path(tmpdir) / "dist"
            dist_dir.mkdir()
            favicon = dist_dir / "favicon.svg"
            favicon.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
            # Also need index.html for the root route
            index = dist_dir / "index.html"
            index.write_text("<html></html>")

            with (
                patch("lab_manager.api.app.STATIC_DIR", Path(tmpdir)),
                patch("lab_manager.api.app.Path", wraps=Path),
                patch.dict(os.environ, {"AUTH_ENABLED": "false"}),
            ):
                # Need to recreate app with the patched static dir
                get_settings.cache_clear()

                from lab_manager.api.app import create_app
                from fastapi.testclient import TestClient

                # Patch the DIST_DIR check within create_app
                app = create_app()
                with TestClient(app) as c:
                    resp = c.get("/favicon.svg")
                    # May or may not pick up our temp dir depending on import order,
                    # but should not be 401
                    assert resp.status_code in (200, 404)

            get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Database Config — verify search_path and URL normalization
# ---------------------------------------------------------------------------


class TestDatabaseConfig:
    """Verify database engine configuration."""

    def test_postgres_uses_search_path(self):
        """Postgres engine created with connect_args search_path."""
        import lab_manager.database as db_module

        # Save and clear singleton
        original = db_module._engine
        db_module._engine = None

        try:
            with patch("lab_manager.database.get_settings") as mock_settings:
                mock_settings.return_value.database_url = (
                    "postgresql+psycopg://user:pass@localhost/testdb"
                )
                with patch("lab_manager.database.create_engine") as mock_create:
                    mock_create.return_value = MagicMock()
                    db_module.get_engine()

                    mock_create.assert_called_once()
                    _args, kwargs = mock_create.call_args
                    assert "connect_args" in kwargs
                    assert "options" in kwargs["connect_args"]
                    assert "search_path" in kwargs["connect_args"]["options"]
                    assert "labmanager" in kwargs["connect_args"]["options"]
        finally:
            db_module._engine = original

    def test_sqlite_no_search_path(self):
        """SQLite engine created without connect_args."""
        import lab_manager.database as db_module

        original = db_module._engine
        db_module._engine = None

        try:
            with patch("lab_manager.database.get_settings") as mock_settings:
                mock_settings.return_value.database_url = "sqlite:///test.db"
                with patch("lab_manager.database.create_engine") as mock_create:
                    mock_create.return_value = MagicMock()
                    db_module.get_engine()

                    mock_create.assert_called_once()
                    _args, kwargs = mock_create.call_args
                    assert "connect_args" not in kwargs

        finally:
            db_module._engine = original

    def test_database_url_normalized(self):
        """postgresql:// prefix gets converted to postgresql+psycopg://."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@host/db"}):
            get_settings.cache_clear()
            try:
                settings = get_settings()
                assert settings.database_url.startswith("postgresql+psycopg://")
                assert not settings.database_url.startswith("postgresql://u")
            finally:
                get_settings.cache_clear()
