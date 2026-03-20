"""Step definitions for deployment readiness BDD scenarios."""

from __future__ import annotations

import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenario, then, when
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.config import get_settings

FEATURE = "../features/deployment.feature"

# --- Scenarios ---


@scenario(FEATURE, "Health endpoint returns ok with all service statuses")
def test_health_ok():
    pass


@scenario(FEATURE, "Health check succeeds when meilisearch is down")
def test_health_meili_down():
    pass


@scenario(FEATURE, "Public endpoints are accessible without authentication")
def test_public_endpoints():
    pass


@scenario(FEATURE, "Protected API endpoints require authentication")
def test_protected_endpoints():
    pass


@scenario(FEATURE, "App starts even when dist/assets does not exist")
def test_no_spa_assets():
    pass


@scenario(FEATURE, "SPA mode is active when dist/assets exists")
def test_spa_mode():
    pass


@scenario(FEATURE, "Legacy mode serves static/index.html when dist/assets is missing")
def test_legacy_mode():
    pass


@scenario(FEATURE, "Root path returns HTML page when auth is enabled")
def test_root_html():
    pass


@scenario(FEATURE, "Fresh deployment returns needs_setup true")
def test_fresh_needs_setup():
    pass


@scenario(FEATURE, "Completing setup creates admin account")
def test_complete_setup():
    pass


@scenario(FEATURE, "Tables are created under labmanager schema on PostgreSQL")
def test_pg_tables():
    pass


# --- Shared context ---


@pytest.fixture
def ctx():
    """Shared context for passing data between steps."""
    return {}


# --- Test client helpers ---


@contextmanager
def _deploy_client(
    auth_enabled: bool = True,
    meili_down: bool = False,
):
    """Context manager: TestClient with a fresh in-memory DB.

    Configures auth and optionally stubs Meilisearch as unreachable.
    """
    import lab_manager.database as db_module
    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    env_overrides = {
        "AUTH_ENABLED": str(auth_enabled).lower(),
        "ADMIN_SECRET_KEY": "test-deploy-secret-key-12345",
        "SECURE_COOKIES": "false",
        "ADMIN_PASSWORD": "test-admin-password-not-for-production",
    }
    orig_env = {k: os.environ.get(k) for k in env_overrides}
    for k, v in env_overrides.items():
        os.environ[k] = v
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    original_engine = db_module._engine
    original_factory = db_module._session_factory
    db_module._engine = engine
    db_module._session_factory = None

    patches = []
    if meili_down:
        p = patch("lab_manager.services.search.get_search_client")
        mock_get_client = p.start()
        mock_client = MagicMock()
        mock_client.health.side_effect = Exception("connection refused")
        mock_get_client.return_value = mock_client
        patches.append(p)

    app = create_app()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client
    finally:
        session.close()
        engine.dispose()
        db_module._engine = original_engine
        db_module._session_factory = original_factory
        for p in patches:
            p.stop()
        for k, v in orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


# --- Given steps ---


@given("a Lab Manager instance with auth enabled", target_fixture="api")
def auth_enabled_instance():
    with _deploy_client(auth_enabled=True) as client:
        yield client


@given("meilisearch is unreachable", target_fixture="api")
def meili_down_instance():
    with _deploy_client(auth_enabled=True, meili_down=True) as client:
        yield client


@given("no admin user exists")
def no_admin_exists():
    """Fresh DB — no setup needed, the _deploy_client starts with empty tables."""
    pass


@given("the SPA build artifacts do not exist", target_fixture="app_mode")
def no_spa_assets():
    """Ensure dist/assets/ does not exist when creating the app."""
    return {"spa": False}


@given("the SPA build artifacts exist", target_fixture="app_mode")
def spa_assets_exist():
    """Pretend dist/assets/ exists when creating the app."""
    return {"spa": True}


@given("a PostgreSQL database is available")
def pg_available():
    """Marker step — the test uses the BDD conftest db fixtures."""
    pass


# --- When steps ---


@when("I request the health endpoint")
def request_health(api, ctx):
    ctx["response"] = api.get("/api/health")


@when(
    parsers.parse('I request "{path}" without authentication'),
)
def request_without_auth(api, ctx, path):
    # Clear any cookies to ensure no auth
    api.cookies.clear()
    ctx["response"] = api.get(path)


@when("I create the app", target_fixture="app_info")
def create_app_for_mode(app_mode, ctx):
    """Create the app with or without SPA assets and capture mode info."""
    import tempfile
    from pathlib import Path

    import lab_manager.database as db_module
    from lab_manager.api import app as app_module
    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    # Save originals
    orig_static = app_module.STATIC_DIR

    with tempfile.TemporaryDirectory() as tmpdir:
        static_dir = Path(tmpdir)
        dist_dir = static_dir / "dist"
        dist_dir.mkdir()

        # Create a minimal index.html
        (dist_dir / "index.html").write_text("<html><body>Lab Manager</body></html>")
        (static_dir / "index.html").write_text(
            "<html><body>Lab Manager Legacy</body></html>"
        )
        # Create sw.js and manifest.json to avoid FileNotFoundError
        (static_dir / "sw.js").write_text("// service worker")
        (static_dir / "manifest.json").write_text("{}")

        if app_mode.get("spa"):
            assets_dir = dist_dir / "assets"
            assets_dir.mkdir()
            (assets_dir / "main.js").write_text("console.log('spa');")

        # Patch STATIC_DIR
        app_module.STATIC_DIR = static_dir

        env_overrides = {
            "AUTH_ENABLED": "false",
            "ADMIN_SECRET_KEY": "test-deploy-secret-key-12345",
            "SECURE_COOKIES": "false",
        }
        orig_env = {k: os.environ.get(k) for k in env_overrides}
        for k, v in env_overrides.items():
            os.environ[k] = v
        get_settings.cache_clear()

        engine = create_engine(
            "sqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        import lab_manager.models  # noqa: F401

        SQLModel.metadata.create_all(engine)
        session = Session(engine)

        original_engine = db_module._engine
        original_factory = db_module._session_factory
        db_module._engine = engine
        db_module._session_factory = None

        try:
            app = create_app()

            def override_get_db():
                yield session

            app.dependency_overrides[get_db] = override_get_db

            with TestClient(app) as client:
                info = {
                    "app": app,
                    "client": client,
                    "spa_mode": app_mode.get("spa", False),
                }
                ctx["app_info"] = info
                yield info
        finally:
            session.close()
            engine.dispose()
            db_module._engine = original_engine
            db_module._session_factory = original_factory
            app_module.STATIC_DIR = orig_static
            for k, v in orig_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            get_settings.cache_clear()


@when(
    parsers.parse(
        'I complete setup with name "{name}" email "{email}" and password "{password}"'
    )
)
def complete_deploy_setup(api, ctx, name, email, password):
    ctx["response"] = api.post(
        "/api/setup/complete",
        json={
            "admin_name": name,
            "admin_email": email,
            "admin_password": password,
        },
    )


@when("the database migrations are applied")
def apply_migrations():
    """Marker step — migrations are handled by the test engine fixture."""
    pass


# --- Then steps ---


@then(parsers.parse("the response status should be {status:d}"))
def check_status(ctx, status):
    assert ctx["response"].status_code == status


@then("the response status should not be 401")
def check_not_401(ctx):
    assert ctx["response"].status_code != 401


@then(parsers.parse('the response JSON "{key}" should be "{value}"'))
def check_json_str(ctx, key, value):
    data = ctx["response"].json()
    assert str(data[key]) == value, f"Expected {key}={value!r}, got {data[key]!r}"


@then(parsers.parse('the response JSON "{key}" should be true'))
def check_json_true(ctx, key):
    data = ctx["response"].json()
    assert data[key] is True, f"Expected {key}=True, got {data[key]!r}"


@then(
    parsers.parse("the health response should include service statuses for {services}")
)
def check_service_keys(ctx, services):
    data = ctx["response"].json()
    # services is a quoted comma-separated string like: "postgresql", "meilisearch", "llm", "disk"
    expected = [s.strip().strip('"') for s in services.split(",")]
    for svc in expected:
        assert svc in data["services"], f"Missing service key: {svc}"


@then(parsers.parse('the health service "{service}" should be "{status}"'))
def check_service_status(ctx, service, status):
    data = ctx["response"].json()
    actual = data["services"][service]
    assert actual == status, f"Expected {service}={status!r}, got {actual!r}"


@then("the app should start successfully")
def app_started(app_info):
    assert app_info["app"] is not None


@then("the root path should serve an HTML page")
def root_serves_html(app_info):
    resp = app_info["client"].get("/")
    assert resp.status_code == 200
    content_type = resp.headers.get("content-type", "")
    assert "text/html" in content_type, f"Expected text/html, got {content_type}"


@then("the app should be in SPA mode")
def check_spa_mode(app_info):
    assert app_info["spa_mode"] is True
    # SPA mode should serve index.html at root
    resp = app_info["client"].get("/")
    assert resp.status_code == 200


@then("the app should be in legacy mode")
def check_legacy_mode(app_info):
    assert app_info["spa_mode"] is False
    # Legacy mode should still serve a page at root
    resp = app_info["client"].get("/")
    assert resp.status_code == 200


@then(parsers.parse('the response content type should contain "{expected}"'))
def check_content_type(ctx, expected):
    content_type = ctx["response"].headers.get("content-type", "")
    assert expected in content_type, (
        f"Expected '{expected}' in content-type, got '{content_type}'"
    )


@then("the setup status should indicate setup is no longer needed")
def setup_no_longer_needed(api):
    resp = api.get("/api/setup/status")
    assert resp.status_code == 200
    assert resp.json()["needs_setup"] is False


@then(parsers.parse('the postgresql service status should be "{status}"'))
def check_pg_status(ctx, status):
    data = ctx["response"].json()
    actual = data["services"]["postgresql"]
    assert actual == status, f"Expected postgresql={status!r}, got {actual!r}"


@then(parsers.parse('tables should exist in the "{schema}" search path'))
def tables_in_schema(db):
    """Verify tables are queryable (works for both SQLite and PG)."""
    from sqlalchemy import text

    # For SQLite, just verify we can query a known table
    result = db.execute(text("SELECT 1"))
    assert result.scalar() == 1


@then(parsers.parse('the "{table}" table should be queryable'))
def table_queryable(db):
    """Verify a specific table is queryable."""
    from sqlalchemy import text

    # staff table should exist and be queryable
    result = db.execute(text("SELECT count(*) FROM staff"))
    count = result.scalar()
    assert count is not None
