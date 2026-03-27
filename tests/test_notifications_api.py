"""API-level tests for notification routes -- CRUD, preferences, read status."""

from fastapi.testclient import TestClient


class TestNotificationList:
    """GET /api/v1/notifications/"""

    def test_list_notifications_empty(self, client: TestClient):
        r = client.get("/api/v1/notifications/")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    def test_list_with_unread_only_filter(self, client: TestClient):
        r = client.get("/api/v1/notifications/", params={"unread_only": True})
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["is_read"] is False


class TestNotificationCount:
    """GET /api/v1/notifications/count"""

    def test_unread_count_endpoint(self, client: TestClient):
        r = client.get("/api/v1/notifications/count")
        assert r.status_code == 200
        data = r.json()
        assert "unread_count" in data
        assert isinstance(data["unread_count"], int)


class TestNotificationPreferences:
    """GET/PATCH /api/v1/notifications/preferences"""

    def test_get_preferences(self, client: TestClient):
        r = client.get("/api/v1/notifications/preferences")
        assert r.status_code == 200
        data = r.json()
        assert "in_app" in data
        assert "email_weekly" in data

    def test_update_preferences(self, client: TestClient):
        r = client.patch(
            "/api/v1/notifications/preferences",
            json={"email_weekly": True, "inventory_alerts": False},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["email_weekly"] is True
        assert data["inventory_alerts"] is False

    def test_update_in_app_preference(self, client: TestClient):
        r = client.patch(
            "/api/v1/notifications/preferences",
            json={"in_app": False},
        )
        assert r.status_code == 200
        assert r.json()["in_app"] is False


class TestNotificationMarkRead:
    """POST /api/v1/notifications/read-all"""

    def test_mark_all_read(self, client: TestClient):
        r = client.post("/api/v1/notifications/read-all")
        assert r.status_code == 200
        data = r.json()
        assert "marked" in data
