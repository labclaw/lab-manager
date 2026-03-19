"""Test telemetry -- usage event tracking, rate limiting, and DAU queries."""

import pytest

from lab_manager.models.usage_event import UsageEvent


@pytest.fixture(autouse=True)
def clear_rate_limits():
    """Clear in-memory rate limit state between tests."""
    import lab_manager.api.routes.telemetry as tel_mod

    tel_mod._rate_limits.clear()
    yield


def test_post_event_endpoint(client, db_session):
    """POST /event should record a usage event."""
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


def test_rate_limiting(client, db_session):
    """Two events for same user+page within 60s should be rate limited."""
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

    events = db_session.query(UsageEvent).filter(UsageEvent.page == "/inventory").all()
    assert len(events) == 1


def test_rate_limit_different_pages(client, db_session):
    """Different pages should not trigger rate limiting."""
    r1 = client.post(
        "/api/v1/telemetry/event",
        params={"event_type": "page_view", "page": "/dashboard"},
    )
    r2 = client.post(
        "/api/v1/telemetry/event",
        params={"event_type": "page_view", "page": "/orders"},
    )
    assert r1.json()["status"] == "ok"
    assert r2.json()["status"] == "ok"


def test_dau_query(client, db_session):
    """GET /dau should return daily active user counts."""
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


def test_dau_multiple_users(client, db_session):
    """DAU should count distinct users."""
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


def test_events_list(client, db_session):
    """GET /events should return recent events."""
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
    assert data[0]["event_type"] == "page_view"


def test_events_filter_by_type(client, db_session):
    """GET /events with event_type filter should only return matching events."""
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
