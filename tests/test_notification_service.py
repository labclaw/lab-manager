"""Comprehensive unit tests for notification_service module.

Tests all public functions directly at the service layer:
  - create_notification
  - get_unread_count
  - mark_read
  - mark_all_read
  - get_preferences
  - update_preferences

Covers happy paths, edge cases, boundary conditions, and isolation
between different staff members.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from lab_manager.models.notification import Notification, NotificationPreference
from lab_manager.models.staff import Staff
from lab_manager.services import notification_service as svc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def staff(db_session):
    """Create a single test staff member."""
    s = Staff(name="Test User", email="test@lab.org", role="member")
    db_session.add(s)
    db_session.flush()
    db_session.refresh(s)
    return s


@pytest.fixture
def other_staff(db_session):
    """Create a second staff member for isolation tests."""
    s = Staff(name="Other User", email="other@lab.org", role="pi")
    db_session.add(s)
    db_session.flush()
    db_session.refresh(s)
    return s


@pytest.fixture
def make_notification(db_session, staff):
    """Factory fixture to create notifications with sensible defaults."""

    def _make(
        staff_id=None,
        type="info",
        title="Test",
        message="Test message",
        link=None,
        is_read=False,
    ):
        if staff_id is None:
            staff_id = staff.id
        n = svc.create_notification(
            db_session,
            staff_id=staff_id,
            type=type,
            title=title,
            message=message,
            link=link,
        )
        if is_read:
            n.is_read = True
            n.read_at = datetime.now(timezone.utc)
            db_session.flush()
            db_session.refresh(n)
        return n

    return _make


# ---------------------------------------------------------------------------
# create_notification
# ---------------------------------------------------------------------------


class TestCreateNotification:
    """Tests for svc.create_notification()."""

    def test_creates_with_required_fields(self, db_session, staff):
        notif = svc.create_notification(
            db_session,
            staff_id=staff.id,
            type="info",
            title="Hello",
            message="World",
        )
        assert notif.id is not None
        assert notif.staff_id == staff.id
        assert notif.type == "info"
        assert notif.title == "Hello"
        assert notif.message == "World"
        assert notif.is_read is False
        assert notif.read_at is None
        assert notif.link is None

    def test_creates_with_link(self, db_session, staff):
        notif = svc.create_notification(
            db_session,
            staff_id=staff.id,
            type="order",
            title="Order",
            message="New order",
            link="/orders/42",
        )
        assert notif.link == "/orders/42"

    def test_creates_with_link_none_explicit(self, db_session, staff):
        notif = svc.create_notification(
            db_session,
            staff_id=staff.id,
            type="alert",
            title="Alert",
            message="Something happened",
            link=None,
        )
        assert notif.link is None

    def test_persists_to_db(self, db_session, staff):
        notif = svc.create_notification(
            db_session,
            staff_id=staff.id,
            type="info",
            title="Persist check",
            message="Should persist",
        )
        from sqlalchemy import select

        result = db_session.scalars(
            select(Notification).where(Notification.id == notif.id)
        ).first()
        assert result is not None
        assert result.title == "Persist check"

    def test_sets_created_at(self, db_session, staff):
        notif = svc.create_notification(
            db_session,
            staff_id=staff.id,
            type="info",
            title="Timestamp",
            message="Check timestamp",
        )
        assert notif.created_at is not None
        assert isinstance(notif.created_at, datetime)

    def test_different_staff_members(self, db_session, staff, other_staff):
        n1 = svc.create_notification(
            db_session, staff_id=staff.id, type="a", title="A", message="a"
        )
        n2 = svc.create_notification(
            db_session, staff_id=other_staff.id, type="b", title="B", message="b"
        )
        assert n1.staff_id == staff.id
        assert n2.staff_id == other_staff.id
        assert n1.id != n2.id

    def test_various_type_strings(self, db_session, staff):
        for ntype in (
            "info",
            "alert",
            "order_request",
            "document_review",
            "team_invite",
        ):
            notif = svc.create_notification(
                db_session, staff_id=staff.id, type=ntype, title="T", message="M"
            )
            assert notif.type == ntype

    def test_long_title(self, db_session, staff):
        title = "A" * 200
        notif = svc.create_notification(
            db_session, staff_id=staff.id, type="info", title=title, message="M"
        )
        assert notif.title == title

    def test_long_message(self, db_session, staff):
        msg = "B" * 1000
        notif = svc.create_notification(
            db_session, staff_id=staff.id, type="info", title="T", message=msg
        )
        assert notif.message == msg


# ---------------------------------------------------------------------------
# get_unread_count
# ---------------------------------------------------------------------------


class TestGetUnreadCount:
    """Tests for svc.get_unread_count()."""

    def test_returns_zero_when_no_notifications(self, db_session, staff):
        assert svc.get_unread_count(db_session, staff.id) == 0

    def test_returns_correct_count_after_creation(self, db_session, make_notification):
        make_notification(title="N1")
        make_notification(title="N2")
        make_notification(title="N3")
        # Use staff.id from the fixture (staff_id defaults to staff.id in make_notification)
        notif0 = make_notification(title="ref")
        assert svc.get_unread_count(db_session, notif0.staff_id) == 4

    def test_excludes_read_notifications(self, db_session, make_notification):
        make_notification(title="Unread")
        make_notification(title="Read", is_read=True)
        notif0 = make_notification(title="ref")
        assert svc.get_unread_count(db_session, notif0.staff_id) == 2

    def test_all_read_returns_zero(self, db_session, make_notification):
        make_notification(title="N1", is_read=True)
        make_notification(title="N2", is_read=True)
        notif0 = make_notification(title="ref", is_read=True)
        assert svc.get_unread_count(db_session, notif0.staff_id) == 0

    def test_isolates_by_staff(self, db_session, staff, other_staff, make_notification):
        make_notification(staff_id=staff.id, title="Staff 1")
        make_notification(staff_id=staff.id, title="Staff 1 too")
        make_notification(staff_id=other_staff.id, title="Staff 2")
        assert svc.get_unread_count(db_session, staff.id) == 2
        assert svc.get_unread_count(db_session, other_staff.id) == 1

    def test_nonexistent_staff_returns_zero(self, db_session):
        assert svc.get_unread_count(db_session, staff_id=99999) == 0

    def test_returns_int_not_none(self, db_session, staff):
        result = svc.get_unread_count(db_session, staff.id)
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# mark_read
# ---------------------------------------------------------------------------


class TestMarkRead:
    """Tests for svc.mark_read()."""

    def test_marks_unread_as_read(self, db_session, make_notification):
        notif = make_notification(title="Unread")
        result = svc.mark_read(db_session, notif.id, notif.staff_id)
        assert result is not None
        assert result.is_read is True
        assert result.read_at is not None

    def test_sets_read_at_to_datetime(self, db_session, make_notification):
        notif = make_notification(title="Time check")
        result = svc.mark_read(db_session, notif.id, notif.staff_id)
        assert isinstance(result.read_at, datetime)
        # SQLite strips tzinfo on round-trip; just verify a datetime was set
        assert result.read_at is not None

    def test_returns_notification_object(self, db_session, make_notification):
        notif = make_notification(title="Return check")
        result = svc.mark_read(db_session, notif.id, notif.staff_id)
        assert isinstance(result, Notification)
        assert result.id == notif.id

    def test_returns_none_for_wrong_staff_id(
        self, db_session, staff, other_staff, make_notification
    ):
        notif = make_notification(staff_id=staff.id, title="Owner")
        result = svc.mark_read(db_session, notif.id, other_staff.id)
        assert result is None

    def test_returns_none_for_nonexistent_notification(self, db_session, staff):
        result = svc.mark_read(db_session, notification_id=99999, staff_id=staff.id)
        assert result is None

    def test_idempotent_on_already_read(self, db_session, make_notification):
        notif = make_notification(title="Already read", is_read=True)
        original_read_at = notif.read_at
        result = svc.mark_read(db_session, notif.id, notif.staff_id)
        assert result is not None
        assert result.is_read is True
        # read_at should NOT change on re-mark (no flush/refresh path taken)
        assert result.read_at == original_read_at

    def test_does_not_affect_other_notifications(self, db_session, make_notification):
        n1 = make_notification(title="First")
        n2 = make_notification(title="Second")
        svc.mark_read(db_session, n1.id, n1.staff_id)
        # Refresh n2 from DB to confirm it's still unread
        db_session.refresh(n2)
        assert n2.is_read is False

    def test_mark_read_decrements_unread_count(self, db_session, make_notification):
        n1 = make_notification(title="N1")
        make_notification(title="N2")
        staff_id = n1.staff_id
        assert svc.get_unread_count(db_session, staff_id) == 2
        svc.mark_read(db_session, n1.id, staff_id)
        assert svc.get_unread_count(db_session, staff_id) == 1


# ---------------------------------------------------------------------------
# mark_all_read
# ---------------------------------------------------------------------------


class TestMarkAllRead:
    """Tests for svc.mark_all_read()."""

    def test_marks_all_unread(self, db_session, make_notification):
        make_notification(title="N1")
        make_notification(title="N2")
        make_notification(title="N3")
        ref = make_notification(title="ref")
        staff_id = ref.staff_id
        count = svc.mark_all_read(db_session, staff_id)
        assert count == 4
        assert svc.get_unread_count(db_session, staff_id) == 0

    def test_returns_zero_when_no_unread(self, db_session, staff):
        count = svc.mark_all_read(db_session, staff.id)
        assert count == 0

    def test_returns_zero_when_all_already_read(self, db_session, make_notification):
        make_notification(title="Read 1", is_read=True)
        make_notification(title="Read 2", is_read=True)
        ref = make_notification(title="ref", is_read=True)
        count = svc.mark_all_read(db_session, ref.staff_id)
        assert count == 0

    def test_marks_only_unread_leaves_read_untouched(
        self, db_session, make_notification
    ):
        n_read = make_notification(title="Already read", is_read=True)
        make_notification(title="Unread")
        ref = make_notification(title="ref")
        staff_id = ref.staff_id
        original_read_at = n_read.read_at
        count = svc.mark_all_read(db_session, staff_id)
        assert count == 2  # the 2 unread ones
        db_session.refresh(n_read)
        # The already-read notification's read_at should not change
        assert n_read.read_at == original_read_at

    def test_sets_read_at_on_all_marked(self, db_session, make_notification):
        n1 = make_notification(title="N1")
        n2 = make_notification(title="N2")
        staff_id = n1.staff_id
        svc.mark_all_read(db_session, staff_id)
        db_session.refresh(n1)
        db_session.refresh(n2)
        assert n1.read_at is not None
        assert n2.read_at is not None

    def test_isolates_by_staff(self, db_session, staff, other_staff, make_notification):
        make_notification(staff_id=staff.id, title="S1")
        make_notification(staff_id=staff.id, title="S2")
        make_notification(staff_id=other_staff.id, title="O1")
        count = svc.mark_all_read(db_session, staff.id)
        assert count == 2
        assert svc.get_unread_count(db_session, other_staff.id) == 1

    def test_nonexistent_staff_returns_zero(self, db_session):
        count = svc.mark_all_read(db_session, staff_id=99999)
        assert count == 0

    def test_partial_read_then_mark_all(self, db_session, make_notification):
        n1 = make_notification(title="N1")
        make_notification(title="N2")
        make_notification(title="N3")
        staff_id = n1.staff_id
        svc.mark_read(db_session, n1.id, staff_id)
        count = svc.mark_all_read(db_session, staff_id)
        assert count == 2  # only the remaining 2 unread


# ---------------------------------------------------------------------------
# get_preferences
# ---------------------------------------------------------------------------


class TestGetPreferences:
    """Tests for svc.get_preferences()."""

    def test_creates_default_preferences_for_new_staff(self, db_session, staff):
        pref = svc.get_preferences(db_session, staff.id)
        assert pref is not None
        assert pref.id is not None
        assert pref.staff_id == staff.id

    def test_default_values(self, db_session, staff):
        pref = svc.get_preferences(db_session, staff.id)
        assert pref.in_app is True
        assert pref.email_weekly is False
        assert pref.order_requests is True
        assert pref.document_reviews is True
        assert pref.inventory_alerts is True
        assert pref.team_changes is True

    def test_returns_existing_preferences(self, db_session, staff):
        pref1 = svc.get_preferences(db_session, staff.id)
        pref2 = svc.get_preferences(db_session, staff.id)
        assert pref1.id == pref2.id
        assert pref1.staff_id == pref2.staff_id

    def test_different_staff_get_different_preferences(
        self, db_session, staff, other_staff
    ):
        pref1 = svc.get_preferences(db_session, staff.id)
        pref2 = svc.get_preferences(db_session, other_staff.id)
        assert pref1.id != pref2.id
        assert pref1.staff_id == staff.id
        assert pref2.staff_id == other_staff.id

    def test_returns_notification_preference_type(self, db_session, staff):
        pref = svc.get_preferences(db_session, staff.id)
        assert isinstance(pref, NotificationPreference)


# ---------------------------------------------------------------------------
# update_preferences
# ---------------------------------------------------------------------------


class TestUpdatePreferences:
    """Tests for svc.update_preferences()."""

    def test_update_single_field(self, db_session, staff):
        pref = svc.update_preferences(db_session, staff.id, {"email_weekly": True})
        assert pref.email_weekly is True

    def test_update_multiple_fields(self, db_session, staff):
        pref = svc.update_preferences(
            db_session,
            staff.id,
            {"email_weekly": True, "inventory_alerts": False, "in_app": False},
        )
        assert pref.email_weekly is True
        assert pref.inventory_alerts is False
        assert pref.in_app is False

    def test_update_does_not_change_untouched_fields(self, db_session, staff):
        svc.update_preferences(db_session, staff.id, {"email_weekly": True})
        pref = svc.get_preferences(db_session, staff.id)
        assert pref.order_requests is True
        assert pref.document_reviews is True
        assert pref.inventory_alerts is True
        assert pref.team_changes is True

    def test_update_ignores_id_field(self, db_session, staff):
        pref = svc.get_preferences(db_session, staff.id)
        original_id = pref.id
        svc.update_preferences(db_session, staff.id, {"id": 99999})
        pref = svc.get_preferences(db_session, staff.id)
        assert pref.id == original_id

    def test_update_ignores_staff_id_field(self, db_session, staff, other_staff):
        svc.update_preferences(db_session, staff.id, {"staff_id": other_staff.id})
        pref = svc.get_preferences(db_session, staff.id)
        assert pref.staff_id == staff.id

    def test_update_ignores_unknown_fields(self, db_session, staff):
        pref = svc.update_preferences(
            db_session, staff.id, {"nonexistent_field": "value"}
        )
        assert pref is not None
        assert not hasattr(pref, "nonexistent_field")

    def test_update_empty_dict_does_nothing(self, db_session, staff):
        original = svc.get_preferences(db_session, staff.id)
        updated = svc.update_preferences(db_session, staff.id, {})
        assert updated.id == original.id
        assert updated.in_app == original.in_app
        assert updated.email_weekly == original.email_weekly

    def test_creates_preferences_if_not_exist(self, db_session, staff):
        """update_preferences calls get_preferences internally, which auto-creates."""
        # Don't call get_preferences first — update_preferences should handle it
        pref = svc.update_preferences(db_session, staff.id, {"email_weekly": True})
        assert pref is not None
        assert pref.staff_id == staff.id
        assert pref.email_weekly is True

    def test_update_boolean_false_values(self, db_session, staff):
        svc.get_preferences(db_session, staff.id)
        pref = svc.update_preferences(
            db_session,
            staff.id,
            {
                "in_app": False,
                "order_requests": False,
                "document_reviews": False,
                "inventory_alerts": False,
                "team_changes": False,
            },
        )
        assert pref.in_app is False
        assert pref.order_requests is False
        assert pref.document_reviews is False
        assert pref.inventory_alerts is False
        assert pref.team_changes is False

    def test_toggle_preference_back_and_forth(self, db_session, staff):
        svc.update_preferences(db_session, staff.id, {"in_app": False})
        pref = svc.get_preferences(db_session, staff.id)
        assert pref.in_app is False

        svc.update_preferences(db_session, staff.id, {"in_app": True})
        pref = svc.get_preferences(db_session, staff.id)
        assert pref.in_app is True

    def test_update_isolates_by_staff(self, db_session, staff, other_staff):
        svc.update_preferences(db_session, staff.id, {"email_weekly": True})
        svc.update_preferences(db_session, other_staff.id, {"email_weekly": False})
        p1 = svc.get_preferences(db_session, staff.id)
        p2 = svc.get_preferences(db_session, other_staff.id)
        assert p1.email_weekly is True
        assert p2.email_weekly is False


# ---------------------------------------------------------------------------
# Cross-function integration (service-level)
# ---------------------------------------------------------------------------


class TestCrossFunctionIntegration:
    """Tests verifying multiple service functions work together correctly."""

    def test_create_mark_read_then_verify_count(self, db_session, make_notification):
        n1 = make_notification(title="N1")
        n2 = make_notification(title="N2")
        staff_id = n1.staff_id
        assert svc.get_unread_count(db_session, staff_id) == 2

        svc.mark_read(db_session, n1.id, staff_id)
        assert svc.get_unread_count(db_session, staff_id) == 1

        svc.mark_read(db_session, n2.id, staff_id)
        assert svc.get_unread_count(db_session, staff_id) == 0

    def test_create_mark_all_read_then_individual(self, db_session, make_notification):
        n1 = make_notification(title="N1")
        staff_id = n1.staff_id
        svc.mark_all_read(db_session, staff_id)

        # mark_read on already-read notification is idempotent
        result = svc.mark_read(db_session, n1.id, staff_id)
        assert result is not None
        assert result.is_read is True

    def test_full_lifecycle(self, db_session, staff):
        # 1. Create notifications
        n1 = svc.create_notification(
            db_session, staff.id, "info", "Title 1", "Message 1"
        )
        n2 = svc.create_notification(
            db_session, staff.id, "alert", "Title 2", "Message 2", link="/test"
        )
        assert svc.get_unread_count(db_session, staff.id) == 2

        # 2. Mark one as read
        svc.mark_read(db_session, n1.id, staff.id)
        assert svc.get_unread_count(db_session, staff.id) == 1

        # 3. Mark all as read
        count = svc.mark_all_read(db_session, staff.id)
        assert count == 1
        assert svc.get_unread_count(db_session, staff.id) == 0

        # 4. Preferences lifecycle
        pref = svc.get_preferences(db_session, staff.id)
        assert pref.in_app is True
        svc.update_preferences(db_session, staff.id, {"in_app": False})
        pref = svc.get_preferences(db_session, staff.id)
        assert pref.in_app is False
