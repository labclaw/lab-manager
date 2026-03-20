"""Release-gate smoke tests for the default shipped product surface."""

from __future__ import annotations

import os
import re
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from lab_manager.config import get_settings


_ENV_KEYS = (
    "DATABASE_URL",
    "MEILISEARCH_URL",
    "AUTH_ENABLED",
    "ADMIN_SECRET_KEY",
    "ADMIN_PASSWORD",
    "API_KEY",
    "SECURE_COOKIES",
    "UPLOAD_DIR",
)


def _asset_refs(html: str) -> list[str]:
    # Release gate should validate whichever shipped frontend mode is active:
    # SPA build assets (/assets/*) or legacy static assets (/static/*).
    return re.findall(
        r'(?:src|href)=["\']((?:/assets/|/static/)[^"\']+)["\']',
        html,
    )


@pytest.fixture(scope="module")
def release_client(tmp_path_factory):
    """Boot the app against an isolated DB and exercise the shipped HTTP surface."""
    upload_dir = tmp_path_factory.mktemp("release-gate") / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    orig_env = {key: os.environ.get(key) for key in _ENV_KEYS}
    original_db_url = os.environ.get("DATABASE_URL", "sqlite://")

    os.environ["AUTH_ENABLED"] = "true"
    os.environ["ADMIN_SECRET_KEY"] = "release-gate-secret-key"
    os.environ["ADMIN_PASSWORD"] = "release-gate-admin-password"
    os.environ["API_KEY"] = "release-gate-api-key"
    os.environ["SECURE_COOKIES"] = "false"
    os.environ["UPLOAD_DIR"] = str(upload_dir)
    get_settings.cache_clear()

    admin_engine = None
    test_engine = None
    test_db_name = None

    if original_db_url.startswith("postgresql"):
        url = make_url(original_db_url)
        test_db_name = f"{url.database}_release_gate_{uuid.uuid4().hex[:8]}"
        admin_url = url.set(database="postgres")
        admin_engine = create_engine(
            admin_url.render_as_string(hide_password=False),
            isolation_level="AUTOCOMMIT",
        )
        quoted_db_name = test_db_name.replace('"', '""')
        with admin_engine.connect() as conn:
            conn.execute(
                text(f'DROP DATABASE IF EXISTS "{quoted_db_name}" WITH (FORCE)')
            )
            conn.execute(text(f'CREATE DATABASE "{quoted_db_name}"'))
        os.environ["DATABASE_URL"] = url.set(database=test_db_name).render_as_string(
            hide_password=False
        )
        test_engine = create_engine(os.environ["DATABASE_URL"])
    else:
        os.environ["DATABASE_URL"] = "sqlite://"
        test_engine = create_engine(
            "sqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )

    import lab_manager.models  # noqa: F401
    import lab_manager.database as db_module
    from lab_manager.api.app import create_app

    SQLModel.metadata.create_all(test_engine)

    original_engine = db_module._engine
    original_factory = db_module._session_factory
    db_module._engine = test_engine
    db_module._session_factory = None

    try:
        with TestClient(create_app()) as client:
            yield client
    finally:
        test_engine.dispose()
        db_module._engine = original_engine
        db_module._session_factory = original_factory

        if admin_engine is not None and test_db_name is not None:
            quoted_db_name = test_db_name.replace('"', '""')
            with admin_engine.connect() as conn:
                conn.execute(
                    text(f'DROP DATABASE IF EXISTS "{quoted_db_name}" WITH (FORCE)')
                )
            admin_engine.dispose()

        for key, value in orig_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_root_serves_existing_assets(release_client: TestClient):
    resp = release_client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")

    assets = _asset_refs(resp.text)
    assert assets, "root page should reference shipped frontend assets"
    for asset in assets:
        asset_resp = release_client.get(asset)
        assert asset_resp.status_code == 200, asset


def test_health_and_first_run_setup(release_client: TestClient):
    health = release_client.get("/api/health")
    assert health.status_code in (200, 503)
    assert "postgresql" in health.json()["services"]

    setup_status = release_client.get("/api/v1/setup/status")
    assert setup_status.status_code == 200
    assert setup_status.json()["needs_setup"] is True

    setup = release_client.post(
        "/api/v1/setup/complete",
        json={
            "admin_name": "Release Admin",
            "admin_email": "release-admin@example.com",
            "admin_password": "ReleasePass123",
        },
    )
    assert setup.status_code == 200

    login = release_client.post(
        "/api/v1/auth/login",
        json={"email": "release-admin@example.com", "password": "ReleasePass123"},
    )
    assert login.status_code == 200

    me = release_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["name"] == "Release Admin"


def test_authenticated_release_flow(release_client: TestClient):
    dashboard = release_client.get("/api/v1/analytics/dashboard")
    assert dashboard.status_code == 200

    vendor = release_client.post(
        "/api/v1/vendors/",
        json={"name": "Release Vendor", "website": "https://example.com"},
    )
    assert vendor.status_code == 201
    vendor_id = vendor.json()["id"]

    product = release_client.post(
        "/api/v1/products/",
        json={
            "catalog_number": "REL-001",
            "name": "Release Product",
            "vendor_id": vendor_id,
        },
    )
    assert product.status_code == 201

    order = release_client.post(
        "/api/v1/orders/",
        json={"vendor_id": vendor_id, "po_number": "REL-PO-001"},
    )
    assert order.status_code == 201

    export = release_client.get("/api/v1/export/vendors.csv")
    assert export.status_code == 200
    assert "text/csv" in export.headers.get("content-type", "")
    assert "Release Vendor" in export.text
