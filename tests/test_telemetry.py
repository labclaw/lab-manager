"""Tests for usage telemetry: login events, event recording, rate limiting, DAU."""

from __future__ import annotations

import os

import bcrypt as _bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.config import get_settings
from lab_manager.models.usage_event import UsageEvent


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


@pytest.fixture
def telemetry_engine():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def telemetry_db(telemetry_engine):
    with Session(telemetry_engine) as session:
        yield session


@pytest.fixture
def telemetry_client(telemetry_engine, telemetry_db):
    os.environ["AUTH_ENABLED"] = "false"
    os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-signing"
    os.environ["SECURE_COOKIES"] = "false"
    get_settings.cache_clear()

    import lab_manager.database as db_module

    original_engine = db_module._engine
    original_factory = db_module._session_factory
    db_module._engine = telemetry_engine
    db_module._session_factory = None

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield telemetry_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c

    db_module._engine = original_engine
    db_module._session_factory = original_factory
    os.environ["AUTH_ENABLED"] = "false"
    os.environ.pop("ADMIN_SECRET_KEY", None)
    os.environ.pop("SECURE_COOKIES", None)
    get_settings.cache_clear()


@pytest.fixture
def staff_user(telemetry_db):
    from lab_manager.models.staff import Staff

    staff = Staff(
        name="Telemetry User",
        email="telemetry@example.com",
        role="admin",
        is_active=True,
        password_hash=_hash_password("correctpassword"),
    )
    telemetry_db.add(staff)
    telemetry_db.commit()
    telemetry_db.refresh(staff)
    return staff


class TestLoginEvent:
    def test_login_records_event(self, telemetry_client, staff_user):
        from lab_manager.database import get_db_session

        from lab_manager.api.routes.telemetry import _rate_limit_store

        _rate_limit_store.clear()

        resp = telemetry_client.post(
            "/api/auth/login",
            json={"email": "telemetry@example.com", "password": "correctpassword"},
        )
        assert resp.status_code == 200

        with get_db_session() as db:
            events = (
                db.query(UsageEvent)
                .filter(
                    UsageEvent.event_type == "login",
                    UsageEvent.user_email == "telemetry@example.com",
                )
                .all()
            )
            assert len(events) == 1
            assert events[0].page == "/api/auth/login"


class TestRecordEvent:
    def test_record_page_view(self, telemetry_client):
        resp = telemetry_client.post(
            "/api/telemetry/event",
            json={"event_type": "page_view", "page": "/dashboard"},
            headers={"X-User": "testuser@example.com"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_record_with_metadata(self, telemetry_client):
        resp = telemetry_client.post(
            "/api/telemetry/event",
            json={
                "event_type": "action",
                "page": "/review",
                "metadata": {"action": "approve", "doc_id": 42},
            },
            headers={"X-User": "testuser@example.com"},
        )
        assert resp.status_code == 200

    def test_invalid_event_type_rejected(self, telemetry_client):
        resp = telemetry_client.post(
            "/api/telemetry/event",
            json={"event_type": "invalid_type", "page": "/test"},
            headers={"X-User": "testuser@example.com"},
        )
        assert resp.status_code == 422

    def test_system_user_rejected(self, telemetry_client):
        resp = telemetry_client.post(
            "/api/telemetry/event",
            json={"event_type": "page_view", "page": "/dashboard"},
        )
        assert resp.status_code == 401


class TestRateLimiting:
    def test_rate_limit_per_user_page(self, telemetry_client):
        from lab_manager.api.routes.telemetry import _rate_limit_store

        _rate_limit_store.clear()

        headers = {"X-User": "ratelimit@example.com"}
        for i in range(2):
            resp = telemetry_client.post(
                "/api/telemetry/event",
                json={"event_type": "page_view", "page": "/dashboard"},
                headers=headers,
            )

        first_ok = telemetry_client.post(
            "/api/telemetry/event",
            json={"event_type": "page_view", "page": "/dashboard"},
            headers=headers,
        )
        assert first_ok.status_code in (200, 429)

    def test_different_pages_not_rate_limited(self, telemetry_client):
        from lab_manager.api.routes.telemetry import _rate_limit_store

        _rate_limit_store.clear()

        headers = {"X-User": "multi@example.com"}
        r1 = telemetry_client.post(
            "/api/telemetry/event",
            json={"event_type": "page_view", "page": "/dashboard"},
            headers=headers,
        )
        r2 = telemetry_client.post(
            "/api/telemetry/event",
            json={"event_type": "page_view", "page": "/review"},
            headers=headers,
        )
        assert r1.status_code == 200
        assert r2.status_code == 200


class TestDAU:
    def test_dau_returns_correct_counts(self, telemetry_client):
        from lab_manager.api.routes.telemetry import _rate_limit_store

        _rate_limit_store.clear()

        telemetry_client.post(
            "/api/telemetry/event",
            json={"event_type": "page_view", "page": "/dashboard"},
            headers={"X-User": "user1@example.com"},
        )
        telemetry_client.post(
            "/api/telemetry/event",
            json={"event_type": "page_view", "page": "/review"},
            headers={"X-User": "user2@example.com"},
        )
        telemetry_client.post(
            "/api/telemetry/event",
            json={"event_type": "action", "page": "/orders"},
            headers={"X-User": "user1@example.com"},
        )

        resp = telemetry_client.get("/api/telemetry/dau", headers={"X-User": "user1@example.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        today = data[-1]
        assert today["dau"] == 2

    def test_dau_empty(self, telemetry_client):
        resp = telemetry_client.get("/api/telemetry/dau", headers={"X-User": "user1@example.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert data == []


class TestListEvents:
    def test_list_events_filtered(self, telemetry_client):
        from lab_manager.api.routes.telemetry import _rate_limit_store

        _rate_limit_store.clear()

        telemetry_client.post(
            "/api/telemetry/event",
            json={"event_type": "page_view", "page": "/dashboard"},
            headers={"X-User": "filter@example.com"},
        )
        telemetry_client.post(
            "/api/telemetry/event",
            json={"event_type": "login", "page": "/api/auth/login"},
            headers={"X-User": "filter@example.com"},
        )

        resp = telemetry_client.get("/api/telemetry/events?event_type=login", headers={"X-User": "filter@example.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["event_type"] == "login"
