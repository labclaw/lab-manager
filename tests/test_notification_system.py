"""Tests for in-app notification system (models, service, API routes)."""

from __future__ import annotations

import pytest

from lab_manager.models.staff import Staff
from lab_manager.services import notification_service as svc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def staff_member(db_session):
    """Create a test staff member."""
    s = Staff(name="Test User", email="test@lab.org", role="member")
    db_session.add(s)
    db_session.flush()
    db_session.refresh(s)
    return s


@pytest.fixture
def sample_notifications(db_session, staff_member):
    """Create a few test notifications."""
    notifs = []
    for i in range(3):
        n = svc.create_notification(
            db_session,
            staff_id=staff_member.id,
            type="order_request",
            title=f"Order #{i + 1} needs approval",
            message=f"New order request #{i + 1} submitted.",
            link=f"/orders/{i + 1}",
        )
        notifs.append(n)
    return notifs


# ---------------------------------------------------------------------------
# Service: create_notification
# ---------------------------------------------------------------------------


class TestCreateNotification:
    def test_creates_notification(self, db_session, staff_member):
        notif = svc.create_notification(
            db_session,
            staff_id=staff_member.id,
            type="team_invite",
            title="You were invited",
            message="Admin invited you to the team.",
        )
        assert notif.id is not None
        assert notif.staff_id == staff_member.id
        assert notif.type == "team_invite"
        assert notif.is_read is False
        assert notif.read_at is None

    def test_creates_with_link(self, db_session, staff_member):
        notif = svc.create_notification(
            db_session,
            staff_id=staff_member.id,
            type="document_review",
            title="Doc needs review",
            message="Document #5 is ready.",
            link="/documents/5",
        )
        assert notif.link == "/documents/5"


# ---------------------------------------------------------------------------
# Service: get_unread_count
# ---------------------------------------------------------------------------


class TestGetUnreadCount:
    def test_returns_zero_when_no_notifications(self, db_session, staff_member):
        assert svc.get_unread_count(db_session, staff_member.id) == 0

    def test_returns_correct_count(
        self, db_session, staff_member, sample_notifications
    ):
        assert svc.get_unread_count(db_session, staff_member.id) == 3

    def test_excludes_read_notifications(
        self, db_session, staff_member, sample_notifications
    ):
        svc.mark_read(db_session, sample_notifications[0].id, staff_member.id)
        assert svc.get_unread_count(db_session, staff_member.id) == 2


# ---------------------------------------------------------------------------
# Service: mark_read
# ---------------------------------------------------------------------------


class TestMarkRead:
    def test_marks_single_notification_read(
        self, db_session, staff_member, sample_notifications
    ):
        notif = svc.mark_read(db_session, sample_notifications[0].id, staff_member.id)
        assert notif is not None
        assert notif.is_read is True
        assert notif.read_at is not None

    def test_returns_none_for_wrong_staff(
        self, db_session, staff_member, sample_notifications
    ):
        other = Staff(name="Other", email="other@lab.org", role="member")
        db_session.add(other)
        db_session.flush()
        db_session.refresh(other)
        result = svc.mark_read(db_session, sample_notifications[0].id, other.id)
        assert result is None

    def test_idempotent_for_already_read(
        self, db_session, staff_member, sample_notifications
    ):
        svc.mark_read(db_session, sample_notifications[0].id, staff_member.id)
        notif = svc.mark_read(db_session, sample_notifications[0].id, staff_member.id)
        assert notif is not None
        assert notif.is_read is True


# ---------------------------------------------------------------------------
# Service: mark_all_read
# ---------------------------------------------------------------------------


class TestMarkAllRead:
    def test_marks_all_unread(self, db_session, staff_member, sample_notifications):
        count = svc.mark_all_read(db_session, staff_member.id)
        assert count == 3
        assert svc.get_unread_count(db_session, staff_member.id) == 0

    def test_returns_zero_when_none_unread(self, db_session, staff_member):
        count = svc.mark_all_read(db_session, staff_member.id)
        assert count == 0


# ---------------------------------------------------------------------------
# Service: preferences
# ---------------------------------------------------------------------------


class TestPreferences:
    def test_get_creates_default_preferences(self, db_session, staff_member):
        pref = svc.get_preferences(db_session, staff_member.id)
        assert pref.staff_id == staff_member.id
        assert pref.in_app is True
        assert pref.email_weekly is False
        assert pref.order_requests is True

    def test_update_preferences(self, db_session, staff_member):
        svc.get_preferences(db_session, staff_member.id)
        pref = svc.update_preferences(
            db_session, staff_member.id, {"email_weekly": True, "order_requests": False}
        )
        assert pref.email_weekly is True
        assert pref.order_requests is False
        # Others unchanged
        assert pref.in_app is True

    def test_update_ignores_protected_fields(self, db_session, staff_member):
        pref = svc.get_preferences(db_session, staff_member.id)
        original_id = pref.id
        svc.update_preferences(
            db_session, staff_member.id, {"id": 999, "staff_id": 999}
        )
        pref = svc.get_preferences(db_session, staff_member.id)
        assert pref.id == original_id
        assert pref.staff_id == staff_member.id


# ---------------------------------------------------------------------------
# API: GET /api/v1/notifications
# ---------------------------------------------------------------------------


class TestNotificationsAPI:
    def _seed(self, client, db_session):
        """Seed a staff member + notifications via service layer."""
        s = Staff(name="API User", email="api@lab.org", role="admin")
        db_session.add(s)
        db_session.flush()
        db_session.refresh(s)
        for i in range(3):
            svc.create_notification(
                db_session,
                staff_id=s.id,
                type="order_request",
                title=f"Order #{i + 1}",
                message=f"Msg #{i + 1}",
                link=f"/orders/{i + 1}",
            )
        return s

    def test_list_notifications(self, client, db_session):
        s = self._seed(client, db_session)
        resp = client.get(f"/api/v1/notifications/?staff_id={s.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_list_unread_only(self, client, db_session):
        s = self._seed(client, db_session)
        # Mark first as read
        notif_id = client.get(f"/api/v1/notifications/?staff_id={s.id}").json()[
            "items"
        ][0]["id"]
        client.post(f"/api/v1/notifications/{notif_id}/read?staff_id={s.id}")
        resp = client.get(f"/api/v1/notifications/?staff_id={s.id}&unread_only=true")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_unread_count(self, client, db_session):
        s = self._seed(client, db_session)
        resp = client.get(f"/api/v1/notifications/count?staff_id={s.id}")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 3

    def test_mark_one_read(self, client, db_session):
        s = self._seed(client, db_session)
        notif_id = client.get(f"/api/v1/notifications/?staff_id={s.id}").json()[
            "items"
        ][0]["id"]
        resp = client.post(f"/api/v1/notifications/{notif_id}/read?staff_id={s.id}")
        assert resp.status_code == 200
        assert resp.json()["is_read"] is True

    def test_mark_one_read_404(self, client, db_session):
        s = self._seed(client, db_session)
        resp = client.post(f"/api/v1/notifications/99999/read?staff_id={s.id}")
        assert resp.status_code == 404

    def test_mark_all_read(self, client, db_session):
        s = self._seed(client, db_session)
        resp = client.post(f"/api/v1/notifications/read-all?staff_id={s.id}")
        assert resp.status_code == 200
        assert resp.json()["marked"] == 3
        # Verify count is now 0
        count_resp = client.get(f"/api/v1/notifications/count?staff_id={s.id}")
        assert count_resp.json()["unread_count"] == 0

    def test_get_preferences(self, client, db_session):
        s = self._seed(client, db_session)
        resp = client.get(f"/api/v1/notifications/preferences?staff_id={s.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["in_app"] is True
        assert data["email_weekly"] is False

    def test_update_preferences(self, client, db_session):
        s = self._seed(client, db_session)
        resp = client.patch(
            f"/api/v1/notifications/preferences?staff_id={s.id}",
            json={"email_weekly": True, "inventory_alerts": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email_weekly"] is True
        assert data["inventory_alerts"] is False
        assert data["in_app"] is True  # unchanged
