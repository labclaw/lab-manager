"""API-level tests for telemetry routes -- event recording, DAU, event listing."""

import pytest

from lab_manager.models.usage_event import UsageEvent


@pytest.fixture(autouse=True)
def clear_rate_limits():
    """Clear in-memory rate limit state between tests."""
    import lab_manager.api.routes.telemetry as tel_mod

    tel_mod._rate_limits.clear()
    yield


class TestRecordEvent:
    """Tests for POST /api/v1/telemetry/event"""

    def test_record_event_success(self, client, db_session):
        resp = client.post(
            "/api/v1/telemetry/event",
            params={"event_type": "page_view", "page": "/dashboard"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        events = db_session.query(UsageEvent).all()
        assert len(events) >= 1
        assert events[-1].event_type == "page_view"
        assert events[-1].page == "/dashboard"

    def test_record_event_without_page(self, client, db_session):
        resp = client.post(
            "/api/v1/telemetry/event",
            params={"event_type": "login"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        events = db_session.query(UsageEvent).all()
        assert len(events) >= 1
        assert events[-1].event_type == "login"
        assert events[-1].page is None

    def test_record_event_missing_event_type_returns_422(self, client):
        resp = client.post("/api/v1/telemetry/event")
        assert resp.status_code == 422

    def test_record_event_stores_user_from_auth(self, client, db_session):
        resp = client.post(
            "/api/v1/telemetry/event",
            params={"event_type": "click", "page": "/orders"},
            headers={"X-User": "researcher@lab.org"},
        )
        assert resp.status_code == 200

        events = db_session.query(UsageEvent).all()
        assert len(events) >= 1
        assert events[-1].user_email == "researcher@lab.org"

    def test_rate_limiting_same_user_same_page(self, client, db_session):
        resp1 = client.post(
            "/api/v1/telemetry/event",
            params={"event_type": "page_view", "page": "/inventory"},
        )
        assert resp1.json()["status"] == "ok"

        resp2 = client.post(
            "/api/v1/telemetry/event",
            params={"event_type": "page_view", "page": "/inventory"},
        )
        assert resp2.json()["status"] == "rate_limited"

        events = (
            db_session.query(UsageEvent).filter(UsageEvent.page == "/inventory").all()
        )
        assert len(events) == 1

    def test_rate_limiting_different_pages_not_limited(self, client, db_session):
        r1 = client.post(
            "/api/v1/telemetry/event",
            params={"event_type": "page_view", "page": "/a"},
        )
        r2 = client.post(
            "/api/v1/telemetry/event",
            params={"event_type": "page_view", "page": "/b"},
        )
        assert r1.json()["status"] == "ok"
        assert r2.json()["status"] == "ok"

    def test_rate_limiting_no_page_uses_global_key(self, client, db_session):
        resp1 = client.post(
            "/api/v1/telemetry/event",
            params={"event_type": "heartbeat"},
        )
        assert resp1.json()["status"] == "ok"

        resp2 = client.post(
            "/api/v1/telemetry/event",
            params={"event_type": "heartbeat"},
        )
        assert resp2.json()["status"] == "rate_limited"

    def test_rate_limiting_different_users_same_page(self, client, db_session):
        r1 = client.post(
            "/api/v1/telemetry/event",
            params={"event_type": "page_view", "page": "/shared"},
            headers={"X-User": "alice@lab.org"},
        )
        r2 = client.post(
            "/api/v1/telemetry/event",
            params={"event_type": "page_view", "page": "/shared"},
            headers={"X-User": "bob@lab.org"},
        )
        assert r1.json()["status"] == "ok"
        assert r2.json()["status"] == "ok"


class TestDailyActiveUsers:
    """Tests for GET /api/v1/telemetry/dau"""

    def test_dau_empty(self, client):
        resp = client.get("/api/v1/telemetry/dau")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_dau_with_events(self, client, db_session):
        for page in ["/dashboard", "/inventory"]:
            db_session.add(
                UsageEvent(
                    user_email="test@example.com",
                    event_type="page_view",
                    page=page,
                )
            )
        db_session.commit()

        resp = client.get("/api/v1/telemetry/dau?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "date" in data[0]
        assert "dau" in data[0]
        assert data[0]["dau"] >= 1

    def test_dau_distinct_users(self, client, db_session):
        for email in ["a@example.com", "b@example.com", "a@example.com"]:
            db_session.add(
                UsageEvent(
                    user_email=email,
                    event_type="page_view",
                    page="/dashboard",
                )
            )
        db_session.commit()

        resp = client.get("/api/v1/telemetry/dau?days=30")
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["dau"] == 2

    def test_dau_days_param_default(self, client):
        resp = client.get("/api/v1/telemetry/dau")
        assert resp.status_code == 200

    def test_dau_days_param_custom(self, client, db_session):
        db_session.add(
            UsageEvent(
                user_email="test@example.com",
                event_type="page_view",
                page="/dash",
            )
        )
        db_session.commit()

        resp = client.get("/api/v1/telemetry/dau?days=7")
        assert resp.status_code == 200

    def test_dau_days_param_invalid_too_large(self, client):
        resp = client.get("/api/v1/telemetry/dau?days=100")
        assert resp.status_code == 422

    def test_dau_days_param_invalid_zero(self, client):
        resp = client.get("/api/v1/telemetry/dau?days=0")
        assert resp.status_code == 422


class TestListEvents:
    """Tests for GET /api/v1/telemetry/events"""

    def test_list_events_empty(self, client):
        resp = client.get("/api/v1/telemetry/events")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_events_returns_events(self, client, db_session):
        db_session.add(
            UsageEvent(
                user_email="list@example.com",
                event_type="page_view",
                page="/documents",
            )
        )
        db_session.commit()

        resp = client.get("/api/v1/telemetry/events")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        event = data[0]
        assert event["event_type"] == "page_view"
        assert event["user_email"] == "list@example.com"
        assert event["page"] == "/documents"
        assert "id" in event
        assert "timestamp" in event

    def test_list_events_filter_by_type(self, client, db_session):
        db_session.add(
            UsageEvent(user_email="f@example.com", event_type="login", page="/login")
        )
        db_session.add(
            UsageEvent(user_email="f@example.com", event_type="page_view", page="/dash")
        )
        db_session.commit()

        resp = client.get("/api/v1/telemetry/events?event_type=login")
        data = resp.json()
        assert all(e["event_type"] == "login" for e in data)

    def test_list_events_filter_nonexistent_type(self, client, db_session):
        db_session.add(
            UsageEvent(user_email="x@example.com", event_type="click", page="/btn")
        )
        db_session.commit()

        resp = client.get("/api/v1/telemetry/events?event_type=nonexistent")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_events_limit_param(self, client, db_session):
        for i in range(5):
            db_session.add(
                UsageEvent(
                    user_email=f"limit{i}@example.com",
                    event_type="page_view",
                    page=f"/page{i}",
                )
            )
        db_session.commit()

        resp = client.get("/api/v1/telemetry/events?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) <= 2

    def test_list_events_limit_default(self, client):
        resp = client.get("/api/v1/telemetry/events")
        assert resp.status_code == 200

    def test_list_events_limit_invalid_zero(self, client):
        resp = client.get("/api/v1/telemetry/events?limit=0")
        assert resp.status_code == 422

    def test_list_events_limit_invalid_too_large(self, client):
        resp = client.get("/api/v1/telemetry/events?limit=501")
        assert resp.status_code == 422

    def test_list_events_ordered_by_created_at_desc(self, client, db_session):
        db_session.add(
            UsageEvent(user_email="first@example.com", event_type="click", page="/a")
        )
        db_session.commit()
        db_session.add(
            UsageEvent(user_email="second@example.com", event_type="click", page="/b")
        )
        db_session.commit()

        resp = client.get("/api/v1/telemetry/events")
        data = resp.json()
        assert len(data) >= 2
        assert data[0]["user_email"] == "second@example.com"

    def test_list_events_timestamp_field(self, client, db_session):
        db_session.add(
            UsageEvent(user_email="ts@example.com", event_type="page_view", page="/ts")
        )
        db_session.commit()

        resp = client.get("/api/v1/telemetry/events")
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["timestamp"] is not None


class TestEviction:
    """Tests for _evict_stale behavior."""

    def test_evict_stale_entries(self, client, db_session):
        import time

        import lab_manager.api.routes.telemetry as tel_mod

        original_max = tel_mod._MAX_STORE_SIZE
        tel_mod._MAX_STORE_SIZE = 2

        try:
            old_time = time.monotonic() - 120
            tel_mod._rate_limits["old1:page"] = old_time
            tel_mod._rate_limits["old2:page"] = old_time
            tel_mod._rate_limits["old3:page"] = old_time

            resp = client.post(
                "/api/v1/telemetry/event",
                params={"event_type": "test", "page": "/new"},
            )
            assert resp.status_code == 200

            assert "old1:page" not in tel_mod._rate_limits
            assert "old2:page" not in tel_mod._rate_limits
            assert "old3:page" not in tel_mod._rate_limits
        finally:
            tel_mod._MAX_STORE_SIZE = original_max
            tel_mod._rate_limits.clear()

    def test_no_eviction_below_threshold(self):
        import lab_manager.api.routes.telemetry as tel_mod

        original = dict(tel_mod._rate_limits)
        tel_mod._rate_limits["a:b"] = 1.0

        try:
            tel_mod._evict_stale()
            assert "a:b" in tel_mod._rate_limits
        finally:
            tel_mod._rate_limits.clear()
            tel_mod._rate_limits.update(original)
