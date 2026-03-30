"""E2E tests for notification endpoints.

Tests notification listing, unread count, mark-read, mark-all-read,
and preference management.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from lab_manager.database import get_db
from lab_manager.services import notification_service as svc


@pytest.fixture()
def _seed_notification(authenticated_client: TestClient | httpx.Client) -> int:
    """Insert a notification directly via the DB and return its id.

    We reach into the app's DB session to call the service layer since
    there is no public API for creating notifications.
    """
    # Determine staff_id from the auth state
    me_resp = authenticated_client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200, f"Failed to get current user: {me_resp.text}"
    staff_id = me_resp.json()["user"]["id"]

    app = authenticated_client.app  # type: ignore[attr-defined]
    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        notif = svc.create_notification(
            db,
            staff_id=staff_id,
            type="order_request",
            title="E2E test notification",
            message="You have a new order request",
            link="/orders/1",
        )
        db.commit()
        return notif.id
    except Exception:
        db.rollback()
        raise


@pytest.mark.e2e
class TestNotificationList:
    """Tests for GET /api/v1/notifications/."""

    def test_list_notifications(self, authenticated_client: TestClient | httpx.Client):
        """GET / returns paginated notification list."""
        resp = authenticated_client.get("/api/v1/notifications/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data or isinstance(data, list)

    def test_list_unread_only(self, authenticated_client: TestClient | httpx.Client):
        """GET /?unread_only=true returns only unread notifications."""
        resp = authenticated_client.get(
            "/api/v1/notifications/", params={"unread_only": True}
        )
        assert resp.status_code == 200

    def test_list_pagination(self, authenticated_client: TestClient | httpx.Client):
        """GET / supports page and page_size params."""
        resp = authenticated_client.get(
            "/api/v1/notifications/", params={"page": 1, "page_size": 10}
        )
        assert resp.status_code == 200
        data = resp.json()
        if "page" in data:
            assert data["page"] == 1

    def test_list_with_seeded_notification(
        self,
        authenticated_client: TestClient | httpx.Client,
        _seed_notification: int,
    ):
        """GET / returns the seeded notification."""
        resp = authenticated_client.get("/api/v1/notifications/")
        assert resp.status_code == 200
        data = resp.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        ids = [n["id"] for n in items]
        assert _seed_notification in ids


@pytest.mark.e2e
class TestUnreadCount:
    """Tests for GET /api/v1/notifications/count."""

    def test_unread_count(self, authenticated_client: TestClient | httpx.Client):
        """GET /count returns unread_count."""
        resp = authenticated_client.get("/api/v1/notifications/count")
        assert resp.status_code == 200
        data = resp.json()
        assert "unread_count" in data
        assert isinstance(data["unread_count"], int)

    def test_unread_count_after_seed(
        self,
        authenticated_client: TestClient | httpx.Client,
        _seed_notification: int,
    ):
        """Unread count is >= 1 after seeding a notification."""
        resp = authenticated_client.get("/api/v1/notifications/count")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] >= 1


@pytest.mark.e2e
class TestMarkRead:
    """Tests for POST /api/v1/notifications/{id}/read."""

    def test_mark_read(
        self,
        authenticated_client: TestClient | httpx.Client,
        _seed_notification: int,
    ):
        """POST /{id}/read marks a notification as read."""
        resp = authenticated_client.post(
            f"/api/v1/notifications/{_seed_notification}/read"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_read"] is True
        assert data["read_at"] is not None

    def test_mark_read_idempotent(
        self,
        authenticated_client: TestClient | httpx.Client,
        _seed_notification: int,
    ):
        """Marking the same notification read twice still returns 200."""
        authenticated_client.post(f"/api/v1/notifications/{_seed_notification}/read")
        resp = authenticated_client.post(
            f"/api/v1/notifications/{_seed_notification}/read"
        )
        assert resp.status_code == 200

    def test_mark_read_nonexistent(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /{id}/read with invalid id returns 404."""
        resp = authenticated_client.post("/api/v1/notifications/999999/read")
        assert resp.status_code == 404


@pytest.mark.e2e
class TestMarkAllRead:
    """Tests for POST /api/v1/notifications/read-all."""

    def test_mark_all_read(self, authenticated_client: TestClient | httpx.Client):
        """POST /read-all returns marked count."""
        resp = authenticated_client.post("/api/v1/notifications/read-all")
        assert resp.status_code == 200
        data = resp.json()
        assert "marked" in data
        assert isinstance(data["marked"], int)

    def test_mark_all_read_clears_count(
        self,
        authenticated_client: TestClient | httpx.Client,
        _seed_notification: int,
    ):
        """After read-all, unread count should be 0."""
        authenticated_client.post("/api/v1/notifications/read-all")
        resp = authenticated_client.get("/api/v1/notifications/count")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0


@pytest.mark.e2e
class TestPreferences:
    """Tests for GET/PATCH /api/v1/notifications/preferences."""

    def test_get_preferences(self, authenticated_client: TestClient | httpx.Client):
        """GET /preferences returns preference object."""
        resp = authenticated_client.get("/api/v1/notifications/preferences")
        assert resp.status_code == 200
        data = resp.json()
        assert "in_app" in data
        assert "email_weekly" in data
        assert "order_requests" in data
        assert "document_reviews" in data
        assert "inventory_alerts" in data
        assert "team_changes" in data

    def test_get_preferences_defaults(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Default preferences have expected values."""
        resp = authenticated_client.get("/api/v1/notifications/preferences")
        assert resp.status_code == 200
        data = resp.json()
        assert data["in_app"] is True
        assert data["email_weekly"] is False
        assert data["order_requests"] is True

    def test_update_preferences(self, authenticated_client: TestClient | httpx.Client):
        """PATCH /preferences updates specified fields."""
        resp = authenticated_client.patch(
            "/api/v1/notifications/preferences",
            json={"email_weekly": True, "team_changes": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email_weekly"] is True
        assert data["team_changes"] is False

    def test_update_preferences_partial(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """PATCH /preferences with one field only updates that field."""
        # Ensure known state first
        authenticated_client.patch(
            "/api/v1/notifications/preferences",
            json={"in_app": True},
        )
        resp = authenticated_client.patch(
            "/api/v1/notifications/preferences",
            json={"inventory_alerts": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["inventory_alerts"] is False
        # in_app should remain True from the previous update
        assert data["in_app"] is True

    def test_preferences_idempotent(
        self,
        authenticated_client: TestClient | httpx.Client,
    ):
        """GET preferences twice returns same staff_id (no duplicate rows)."""
        resp1 = authenticated_client.get("/api/v1/notifications/preferences")
        resp2 = authenticated_client.get("/api/v1/notifications/preferences")
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["id"] == resp2.json()["id"]
