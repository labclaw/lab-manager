"""Tests for first-run setup wizard endpoints."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.config import get_settings


@pytest.fixture
def setup_engine():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def setup_db_session(setup_engine):
    with Session(setup_engine) as session:
        yield session


@pytest.fixture
def setup_client(setup_engine, setup_db_session):
    """TestClient with auth_enabled=True and empty DB (no admin yet)."""
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-signing"
    os.environ["ADMIN_PASSWORD"] = "test-admin-password-12345"
    os.environ["SECURE_COOKIES"] = "false"
    os.environ["LAB_NAME"] = "Test Lab"
    os.environ["LAB_SUBTITLE"] = "Unit Testing"
    get_settings.cache_clear()

    import lab_manager.database as db_module

    original_engine = db_module._engine
    original_factory = db_module._session_factory
    db_module._engine = setup_engine
    db_module._session_factory = None

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield setup_db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c

    db_module._engine = original_engine
    db_module._session_factory = original_factory
    os.environ.pop("LAB_NAME", None)
    os.environ.pop("LAB_SUBTITLE", None)
    os.environ.pop("ADMIN_PASSWORD", None)
    os.environ["AUTH_ENABLED"] = "false"
    get_settings.cache_clear()


# --- Config endpoint ---


def test_config_returns_lab_identity(setup_client):
    """Config endpoint returns lab name and subtitle."""
    resp = setup_client.get("/api/v1/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["lab_name"] == "Test Lab"
    assert data["lab_subtitle"] == "Unit Testing"
    assert data["version"] == "0.1.9"


def test_config_no_auth_required(setup_client):
    """Config endpoint should be accessible without authentication."""
    resp = setup_client.get("/api/v1/config")
    assert resp.status_code != 401


# --- Setup status ---


def test_setup_status_needs_setup_when_empty(setup_client):
    """Empty DB should indicate setup is needed."""
    resp = setup_client.get("/api/v1/setup/status")
    assert resp.status_code == 200
    assert resp.json()["needs_setup"] is True


def test_setup_status_no_auth_required(setup_client):
    """Setup status should be accessible without authentication."""
    resp = setup_client.get("/api/v1/setup/status")
    assert resp.status_code != 401


# --- Setup complete ---


def test_setup_complete_creates_admin(setup_client):
    """First-run setup should create an admin user."""
    resp = setup_client.post(
        "/api/v1/setup/complete",
        json={
            "admin_name": "Dr. Smith",
            "admin_email": "smith@mit.edu",
            "admin_password": "securepass123",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"

    # Setup no longer needed
    status_resp = setup_client.get("/api/v1/setup/status")
    assert status_resp.json()["needs_setup"] is False


def test_setup_complete_can_login_after(setup_client):
    """After setup, the admin should be able to log in."""
    setup_client.post(
        "/api/v1/setup/complete",
        json={
            "admin_name": "Dr. Smith",
            "admin_email": "smith@mit.edu",
            "admin_password": "securepass123",
        },
    )
    login_resp = setup_client.post(
        "/api/v1/auth/login",
        json={"email": "smith@mit.edu", "password": "securepass123"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["user"]["name"] == "Dr. Smith"


def test_setup_complete_blocked_after_first_run(setup_client):
    """Setup should only work once — blocked when admin already exists."""
    setup_client.post(
        "/api/v1/setup/complete",
        json={
            "admin_name": "Dr. Smith",
            "admin_email": "smith@mit.edu",
            "admin_password": "securepass123",
        },
    )
    # Second attempt should fail
    resp = setup_client.post(
        "/api/v1/setup/complete",
        json={
            "admin_name": "Hacker",
            "admin_email": "hack@evil.com",
            "admin_password": "hackpass123",
        },
    )
    assert resp.status_code == 409
    assert "already completed" in resp.json()["detail"]


def test_setup_complete_short_password_rejected(setup_client):
    """Password shorter than 8 characters should be rejected."""
    resp = setup_client.post(
        "/api/v1/setup/complete",
        json={
            "admin_name": "Dr. Smith",
            "admin_email": "smith@mit.edu",
            "admin_password": "short",
        },
    )
    assert resp.status_code == 422


@pytest.mark.parametrize("bad_email", ["notanemail", "missing@domain", "@no-local.com"])
def test_setup_complete_invalid_email_rejected(setup_client, bad_email):
    """Invalid email format should be rejected."""
    resp = setup_client.post(
        "/api/v1/setup/complete",
        json={
            "admin_name": "Dr. Smith",
            "admin_email": bad_email,
            "admin_password": "securepass123",
        },
    )
    assert resp.status_code == 422, (
        f"Expected 422 for email '{bad_email}', got {resp.status_code}"
    )


def test_setup_complete_empty_name_rejected(setup_client):
    """Empty name should be rejected."""
    resp = setup_client.post(
        "/api/v1/setup/complete",
        json={
            "admin_name": "   ",
            "admin_email": "smith@mit.edu",
            "admin_password": "securepass123",
        },
    )
    assert resp.status_code == 422


def test_setup_complete_long_name_rejected(setup_client):
    """Name exceeding 200 characters should be rejected."""
    resp = setup_client.post(
        "/api/v1/setup/complete",
        json={
            "admin_name": "A" * 201,
            "admin_email": "smith@mit.edu",
            "admin_password": "securepass123",
        },
    )
    assert resp.status_code == 422


def test_setup_no_auth_required(setup_client):
    """Setup complete should be accessible without authentication."""
    resp = setup_client.post(
        "/api/v1/setup/complete",
        json={
            "admin_name": "Dr. Smith",
            "admin_email": "smith@mit.edu",
            "admin_password": "securepass123",
        },
    )
    assert resp.status_code != 401
