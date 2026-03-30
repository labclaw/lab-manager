"""Security tests for login brute-force lockout and DB error handling."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import bcrypt as _bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.config import get_settings


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _security_engine():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def _security_db(_security_engine):
    with Session(_security_engine) as session:
        yield session


@pytest.fixture
def _security_client(_security_engine, _security_db):
    """TestClient with auth enabled."""
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-signing"
    os.environ["ADMIN_PASSWORD"] = "test-admin-password-12345"
    os.environ["API_KEY"] = "test-api-key-12345"
    os.environ["SECURE_COOKIES"] = "false"
    get_settings.cache_clear()

    import lab_manager.database as db_module

    original_engine = db_module._engine
    original_factory = db_module._session_factory
    db_module._engine = _security_engine
    db_module._session_factory = None

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield _security_db

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_failed_login_increments_counter(_security_client, _security_db):
    """Each failed login must increment failed_login_count in the DB."""
    from lab_manager.models.staff import Staff

    staff = Staff(
        name="Brute Target",
        email="brute@example.com",
        role="admin",
        is_active=True,
        password_hash=_hash_password("realpass"),
        failed_login_count=0,
        locked_until=None,
    )
    _security_db.add(staff)
    _security_db.commit()
    _security_db.refresh(staff)
    staff_id = staff.id

    resp = _security_client.post(
        "/api/v1/auth/login",
        json={"email": "brute@example.com", "password": "wrong1"},
    )
    assert resp.status_code == 401

    _security_db.expire_all()
    s = _security_db.get(Staff, staff_id)
    assert s.failed_login_count == 1

    resp = _security_client.post(
        "/api/v1/auth/login",
        json={"email": "brute@example.com", "password": "wrong2"},
    )
    assert resp.status_code == 401

    _security_db.expire_all()
    s = _security_db.get(Staff, staff_id)
    assert s.failed_login_count == 2


def test_lockout_after_five_failures(_security_client, _security_db):
    """Account must be locked after 5 consecutive failed logins."""
    from lab_manager.models.staff import Staff

    staff = Staff(
        name="Lockout Target",
        email="lockout@example.com",
        role="admin",
        is_active=True,
        password_hash=_hash_password("realpass"),
        failed_login_count=0,
        locked_until=None,
    )
    _security_db.add(staff)
    _security_db.commit()
    _security_db.refresh(staff)
    staff_id = staff.id

    for i in range(5):
        resp = _security_client.post(
            "/api/v1/auth/login",
            json={"email": "lockout@example.com", "password": f"wrong{i}"},
        )
        assert resp.status_code == 401, f"Attempt {i + 1} should be 401"

    _security_db.expire_all()
    s = _security_db.get(Staff, staff_id)
    assert s.failed_login_count == 5
    assert s.locked_until is not None
    locked = (
        s.locked_until.replace(tzinfo=timezone.utc)
        if s.locked_until.tzinfo is None
        else s.locked_until
    )
    assert locked > datetime.now(timezone.utc)

    # 6th attempt: either 403 (locked) or 429 (rate-limited)
    resp = _security_client.post(
        "/api/v1/auth/login",
        json={"email": "lockout@example.com", "password": "realpass"},
    )
    assert resp.status_code in (403, 429), (
        f"Expected 403 or 429, got {resp.status_code}"
    )


def test_db_failure_during_failed_login_count_returns_503(
    _security_client, _security_db
):
    """If DB fails while updating failed_login_count, must return 503 not 401."""
    from lab_manager.models.staff import Staff
    from sqlalchemy.exc import OperationalError

    staff = Staff(
        name="DB Fail Target",
        email="dbfail@example.com",
        role="admin",
        is_active=True,
        password_hash=_hash_password("realpass"),
        failed_login_count=0,
        locked_until=None,
    )
    _security_db.add(staff)
    _security_db.commit()

    with patch(
        "lab_manager.database.get_db_session",
        side_effect=OperationalError("stmt", {}, Exception("connection lost")),
    ):
        resp = _security_client.post(
            "/api/v1/auth/login",
            json={"email": "dbfail@example.com", "password": "wrong"},
        )
        assert resp.status_code == 503, (
            f"Expected 503, got {resp.status_code} — lockout counter silently skipped!"
        )
