"""Tests for enhanced settings-related endpoints (config + auth/me)."""

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
def settings_engine():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def settings_db(settings_engine):
    with Session(settings_engine) as session:
        yield session


@pytest.fixture
def admin_user(settings_db):
    from lab_manager.models.staff import Staff

    staff = Staff(
        name="Admin User",
        email="admin@test.com",
        role="admin",
        is_active=True,
        password_hash=_hash_password("admin123"),
    )
    settings_db.add(staff)
    settings_db.commit()
    settings_db.refresh(staff)
    return staff


@pytest.fixture
def member_user(settings_db):
    from lab_manager.models.staff import Staff

    staff = Staff(
        name="Lab Member",
        email="member@test.com",
        role="member",
        is_active=True,
        password_hash=_hash_password("member123"),
    )
    settings_db.add(staff)
    settings_db.commit()
    settings_db.refresh(staff)
    return staff


@pytest.fixture
def settings_client(settings_engine, settings_db):
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["ADMIN_SECRET_KEY"] = "settings-test-secret-key"
    os.environ["ADMIN_PASSWORD"] = "settings-test-password"
    os.environ["API_KEY"] = "settings-test-api-key"
    os.environ["SECURE_COOKIES"] = "false"
    get_settings.cache_clear()

    import lab_manager.database as db_module

    original_engine = db_module._engine
    original_factory = db_module._session_factory
    db_module._engine = settings_engine
    db_module._session_factory = None

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield settings_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c

    db_module._engine = original_engine
    db_module._session_factory = original_factory
    os.environ["AUTH_ENABLED"] = "false"
    os.environ.pop("ADMIN_SECRET_KEY", None)
    os.environ.pop("ADMIN_PASSWORD", None)
    os.environ.pop("API_KEY", None)
    get_settings.cache_clear()


# --- /api/v1/config must NOT expose model names ---


def test_config_hides_model_fields(settings_client):
    """Config endpoint must not expose internal model names (security hardening)."""
    resp = settings_client.get("/api/v1/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "lab_name" in data
    assert "version" in data
    # Model names must not leak to public endpoint
    assert "ocr_model" not in data
    assert "extraction_model" not in data
    assert "rag_model" not in data
    assert "ocr_tier" not in data


# --- /api/v1/auth/me returns email and role ---


def test_auth_me_returns_email_and_role(settings_client, admin_user):
    """Auth/me should return email and role for authenticated users."""
    login_resp = settings_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "admin123"},
    )
    assert login_resp.status_code == 200

    resp = settings_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    user = data["user"]
    assert user["name"] == "Admin User"
    assert user["email"] == "admin@test.com"
    assert user["role"] == "admin"


def test_auth_me_member_role(settings_client, member_user):
    """Auth/me should return 'member' role for non-admin users."""
    login_resp = settings_client.post(
        "/api/v1/auth/login",
        json={"email": "member@test.com", "password": "member123"},
    )
    assert login_resp.status_code == 200

    resp = settings_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    user = data["user"]
    assert user["name"] == "Lab Member"
    assert user["email"] == "member@test.com"
    assert user["role"] == "member"


def test_auth_me_no_auth_returns_role(settings_client):
    """When auth is disabled, /auth/me should still return role field."""
    os.environ["AUTH_ENABLED"] = "false"
    get_settings.cache_clear()

    # Need a fresh app for the setting to take effect
    from lab_manager.api.app import create_app

    app = create_app()
    with TestClient(app) as c:
        resp = c.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        user = data["user"]
        assert "role" in user

    os.environ["AUTH_ENABLED"] = "true"
    get_settings.cache_clear()
