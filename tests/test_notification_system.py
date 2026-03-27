"""Tests for in-app notification system (models, service, API routes)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from lab_manager.models.alert import Alert
from lab_manager.models.notification import Notification
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


class TestAlertFanout:
    def test_create_alert_notifications_defaults_to_opt_in(
        self, db_session, staff_member
    ):
        alert = Alert(
            alert_type="low_stock",
            severity="warning",
            message="PBS is low",
            entity_type="product",
            entity_id=1,
        )
        db_session.add(alert)
        db_session.flush()

        created = svc.create_alert_notifications(db_session, [alert])

        assert created == 1
        assert svc.get_unread_count(db_session, staff_member.id) == 1
        notif = db_session.scalars(
            select(Notification).where(Notification.staff_id == staff_member.id)
        ).one()
        assert notif.type == "alert"
        assert notif.link == "/alerts"

    def test_create_alert_notifications_respects_disabled_preferences(
        self, db_session, staff_member
    ):
        svc.update_preferences(
            db_session,
            staff_member.id,
            {"in_app": False, "inventory_alerts": False},
        )
        alert = Alert(
            alert_type="expired",
            severity="critical",
            message="Expired reagent",
            entity_type="inventory",
            entity_id=2,
        )
        db_session.add(alert)
        db_session.flush()

        created = svc.create_alert_notifications(db_session, [alert])

        assert created == 0
        assert svc.get_unread_count(db_session, staff_member.id) == 0


# ---------------------------------------------------------------------------
# API: GET /api/v1/notifications
# ---------------------------------------------------------------------------


class TestNotificationsAPI:
    """API tests use auth-disabled middleware which sets staff id=0."""

    def _ensure_system_staff(self, db_session):
        """Ensure a staff record with id=0 exists for the dev-mode middleware."""
        from sqlalchemy import select as sa_select

        existing = db_session.scalars(sa_select(Staff).where(Staff.id == 0)).first()
        if existing:
            return
        # Create staff with ORM to get all defaults, then update id to 0
        s = Staff(name="system", email="system@lab.test", role="admin", is_active=True)
        db_session.add(s)
        db_session.flush()
        if s.id != 0:
            from sqlalchemy import update

            db_session.execute(update(Staff).where(Staff.id == s.id).values(id=0))
            db_session.flush()
            db_session.expire_all()

    def _seed(self, client, db_session):
        """Seed notifications for the default staff id (0, set by middleware)."""
        self._ensure_system_staff(db_session)
        for i in range(3):
            svc.create_notification(
                db_session,
                staff_id=0,
                type="order_request",
                title=f"Order #{i + 1}",
                message=f"Msg #{i + 1}",
                link=f"/orders/{i + 1}",
            )

    def test_list_notifications(self, client, db_session):
        self._seed(client, db_session)
        resp = client.get("/api/v1/notifications/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_list_unread_only(self, client, db_session):
        self._seed(client, db_session)
        # Mark first as read
        notif_id = client.get("/api/v1/notifications/").json()["items"][0]["id"]
        client.post(f"/api/v1/notifications/{notif_id}/read")
        resp = client.get("/api/v1/notifications/?unread_only=true")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_unread_count(self, client, db_session):
        self._seed(client, db_session)
        resp = client.get("/api/v1/notifications/count")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 3

    def test_mark_one_read(self, client, db_session):
        self._seed(client, db_session)
        notif_id = client.get("/api/v1/notifications/").json()["items"][0]["id"]
        resp = client.post(f"/api/v1/notifications/{notif_id}/read")
        assert resp.status_code == 200
        assert resp.json()["is_read"] is True

    def test_mark_one_read_404(self, client, db_session):
        self._seed(client, db_session)
        resp = client.post("/api/v1/notifications/99999/read")
        assert resp.status_code == 404

    def test_mark_all_read(self, client, db_session):
        self._seed(client, db_session)
        resp = client.post("/api/v1/notifications/read-all")
        assert resp.status_code == 200
        assert resp.json()["marked"] == 3
        # Verify count is now 0
        count_resp = client.get("/api/v1/notifications/count")
        assert count_resp.json()["unread_count"] == 0

    def test_get_preferences(self, client, db_session):
        self._seed(client, db_session)
        resp = client.get("/api/v1/notifications/preferences")
        assert resp.status_code == 200
        data = resp.json()
        assert data["in_app"] is True
        assert data["email_weekly"] is False

    def test_update_preferences(self, client, db_session):
        self._seed(client, db_session)
        resp = client.patch(
            "/api/v1/notifications/preferences",
            json={"email_weekly": True, "inventory_alerts": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email_weekly"] is True
        assert data["inventory_alerts"] is False
        assert data["in_app"] is True  # unchanged
