"""Tests for authentication middleware, login/logout, and health endpoint."""

from __future__ import annotations

import os

import bcrypt as _bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.config import get_settings


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


@pytest.fixture
def auth_engine():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def auth_db_session(auth_engine):
    with Session(auth_engine) as session:
        yield session


@pytest.fixture
def staff_user(auth_db_session):
    """Create a staff member with a known password."""
    from lab_manager.models.staff import Staff

    staff = Staff(
        name="Test User",
        email="test@shenlab.org",
        role="admin",
        is_active=True,
        password_hash=_hash_password("correctpassword"),
    )
    auth_db_session.add(staff)
    auth_db_session.commit()
    auth_db_session.refresh(staff)
    return staff


@pytest.fixture
def inactive_staff(auth_db_session):
    """Create an inactive staff member."""
    from lab_manager.models.staff import Staff

    staff = Staff(
        name="Inactive User",
        email="inactive@shenlab.org",
        role="member",
        is_active=False,
        password_hash=_hash_password("somepassword"),
    )
    auth_db_session.add(staff)
    auth_db_session.commit()
    auth_db_session.refresh(staff)
    return staff


@pytest.fixture
def auth_client(auth_engine, auth_db_session):
    """TestClient with auth_enabled=True and shared test DB."""
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-signing"
    os.environ["API_KEY"] = "test-api-key-12345"
    os.environ["SECURE_COOKIES"] = "false"
    get_settings.cache_clear()

    # Point database singletons at the test engine so middleware's
    # get_db_session() uses the same database as the test fixtures.
    import lab_manager.database as db_module

    original_engine = db_module._engine
    original_factory = db_module._session_factory
    db_module._engine = auth_engine
    db_module._session_factory = None

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield auth_db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c

    # Restore original singletons
    db_module._engine = original_engine
    db_module._session_factory = original_factory
    os.environ["AUTH_ENABLED"] = "false"
    get_settings.cache_clear()


# --- Health endpoint (always accessible) ---


def test_health_no_auth_required(auth_client):
    """Health endpoint should be accessible without authentication."""
    resp = auth_client.get("/api/health")
    # May be 503 since services aren't running, but should not be 401
    assert resp.status_code != 401
    data = resp.json()
    assert "status" in data
    assert "services" in data


def test_health_reports_service_status(auth_client):
    """Health endpoint should report individual service statuses."""
    resp = auth_client.get("/api/health")
    data = resp.json()
    assert "postgresql" in data["services"]
    assert "meilisearch" in data["services"]
    assert "llm" in data["services"]


# --- Login endpoint ---


def test_login_success(auth_client, staff_user):
    """Valid credentials should return 200 and set session cookie."""
    resp = auth_client.post(
        "/api/auth/login",
        json={"email": "test@shenlab.org", "password": "correctpassword"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["user"]["name"] == "Test User"
    assert "lab_session" in resp.cookies


def test_login_wrong_password(auth_client, staff_user):
    resp = auth_client.post(
        "/api/auth/login",
        json={"email": "test@shenlab.org", "password": "wrongpassword"},
    )
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.json()["detail"]


def test_login_nonexistent_email(auth_client):
    resp = auth_client.post(
        "/api/auth/login",
        json={"email": "nobody@shenlab.org", "password": "anything"},
    )
    assert resp.status_code == 401


def test_login_inactive_user(auth_client, inactive_staff):
    """Inactive users should not be able to log in."""
    resp = auth_client.post(
        "/api/auth/login",
        json={"email": "inactive@shenlab.org", "password": "somepassword"},
    )
    assert resp.status_code == 401


# --- Session-based access ---


def test_authenticated_request_with_session(auth_client, staff_user):
    """After login, session cookie should grant access to protected routes."""
    login_resp = auth_client.post(
        "/api/auth/login",
        json={"email": "test@shenlab.org", "password": "correctpassword"},
    )
    assert login_resp.status_code == 200

    # TestClient automatically includes cookies from previous responses
    resp = auth_client.get("/api/v1/vendors/")
    assert resp.status_code == 200


def test_unauthenticated_request_rejected(auth_client):
    """Without session or API key, protected endpoints should return 401."""
    # Create a fresh client without any cookies
    resp = auth_client.get("/api/v1/vendors/")
    assert resp.status_code == 401


# --- API key fallback ---


def test_api_key_auth_fallback(auth_client):
    """X-Api-Key header should work as auth fallback."""
    resp = auth_client.get(
        "/api/v1/vendors/", headers={"X-Api-Key": "test-api-key-12345"}
    )
    assert resp.status_code == 200


def test_invalid_api_key_rejected(auth_client):
    resp = auth_client.get("/api/v1/vendors/", headers={"X-Api-Key": "wrong-key"})
    assert resp.status_code == 401


# --- Logout ---


def test_logout_then_access_rejected(auth_client, staff_user):
    """After logout, session should be invalidated (cookie deleted)."""
    auth_client.post(
        "/api/auth/login",
        json={"email": "test@shenlab.org", "password": "correctpassword"},
    )
    auth_client.post("/api/auth/logout")
    # Clear cookies from TestClient to simulate fresh browser after cookie deletion
    auth_client.cookies.clear()
    resp = auth_client.get("/api/v1/vendors/")
    assert resp.status_code == 401


# --- Tampered cookie ---


def test_tampered_cookie_rejected(auth_client):
    """A forged/tampered session cookie should be rejected."""
    auth_client.cookies.set("lab_session", "tampered-garbage-value")
    resp = auth_client.get("/api/v1/vendors/")
    assert resp.status_code == 401


# --- User deactivated after login ---


def test_deactivated_user_session_rejected(auth_client, staff_user, auth_db_session):
    """If staff is deactivated, existing session should be rejected."""
    auth_client.post(
        "/api/auth/login",
        json={"email": "test@shenlab.org", "password": "correctpassword"},
    )
    # Deactivate the user
    staff_user.is_active = False
    auth_db_session.commit()
    # Session cookie is still valid but user is inactive
    resp = auth_client.get("/api/v1/vendors/")
    assert resp.status_code == 401


# --- Staff with no password ---


def test_login_no_password_hash(auth_client, auth_db_session):
    """Staff without password_hash should not be able to login."""
    from lab_manager.models.staff import Staff

    staff = Staff(
        name="No Password User",
        email="nopwd@shenlab.org",
        role="member",
        is_active=True,
        password_hash=None,
    )
    auth_db_session.add(staff)
    auth_db_session.commit()

    resp = auth_client.post(
        "/api/auth/login",
        json={"email": "nopwd@shenlab.org", "password": "anything"},
    )
    assert resp.status_code == 401


# --- CSV escape (from PR-1 review) ---


def test_escape_cell_formula_prefixes():
    """Verify _escape_cell handles all dangerous prefixes."""
    from lab_manager.api.routes.export import _escape_cell

    assert _escape_cell(None) == ""
    assert _escape_cell("") == ""
    assert _escape_cell("normal") == "normal"
    assert _escape_cell("=SUM(A1)") == "'=SUM(A1)"
    assert _escape_cell("+cmd") == "'+cmd"
    assert _escape_cell("-cmd") == "'-cmd"
    assert _escape_cell("@evil") == "'@evil"
    assert _escape_cell("\tcmd") == "'\tcmd"
    assert _escape_cell("\rcmd") == "'\rcmd"
    assert _escape_cell("\ncmd") == "'\ncmd"
    assert _escape_cell(42) == 42
    assert _escape_cell(3.14) == 3.14
