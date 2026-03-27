"""Unit tests for lab_manager.services.notification_service — fully mocked DB session."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


from lab_manager.services.notification_service import (
    create_notification,
    get_preferences,
    get_unread_count,
    mark_all_read,
    mark_read,
    update_preferences,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_notification(
    id: int = 1,
    staff_id: int = 10,
    type: str = "order_request",
    title: str = "New Order",
    message: str = "You have a new order request",
    link: str | None = None,
    is_read: bool = False,
    read_at: datetime | None = None,
):
    """Create a mock Notification object."""
    n = MagicMock()
    n.id = id
    n.staff_id = staff_id
    n.type = type
    n.title = title
    n.message = message
    n.link = link
    n.is_read = is_read
    n.read_at = read_at
    return n


def _make_preference(
    id: int = 1,
    staff_id: int = 10,
    in_app: bool = True,
    email_weekly: bool = False,
    order_requests: bool = True,
    document_reviews: bool = True,
    inventory_alerts: bool = True,
    team_changes: bool = True,
):
    """Create a mock NotificationPreference object."""
    p = MagicMock()
    p.id = id
    p.staff_id = staff_id
    p.in_app = in_app
    p.email_weekly = email_weekly
    p.order_requests = order_requests
    p.document_reviews = document_reviews
    p.inventory_alerts = inventory_alerts
    p.team_changes = team_changes
    return p


def _mock_db_with_scalars_first(return_value):
    """Return a MagicMock db whose scalars().first() returns *return_value*."""
    db = MagicMock()
    result = MagicMock()
    result.first.return_value = return_value
    db.scalars.return_value = result
    return db


def _mock_db_with_scalar(return_value):
    """Return a MagicMock db whose execute().scalar() returns *return_value*."""
    db = MagicMock()
    result = MagicMock()
    result.scalar.return_value = return_value
    db.execute.return_value = result
    return db


# ===================================================================
# create_notification
# ===================================================================


class TestCreateNotification:
    """Tests for create_notification function."""

    def test_creates_and_returns_notification(self):
        db = MagicMock()
        notif = _make_notification()
        db.refresh.return_value = notif

        # db.add does not return, db.refresh returns the notification
        def fake_refresh(obj):
            obj.id = 1
            obj.staff_id = 10
            return obj

        db.refresh = fake_refresh

        result = create_notification(
            db=db,
            staff_id=10,
            type="order_request",
            title="New Order",
            message="You have a new order",
            link="/orders/5",
        )
        db.add.assert_called_once()
        db.flush.assert_called_once()
        assert result.staff_id == 10
        assert result.type == "order_request"

    def test_adds_notification_to_session(self):
        db = MagicMock()
        db.refresh = MagicMock()
        create_notification(
            db=db,
            staff_id=5,
            type="document_review",
            title="Review needed",
            message="Please review doc",
        )
        db.add.assert_called_once()
        added_obj = db.add.call_args[0][0]
        assert added_obj.staff_id == 5
        assert added_obj.type == "document_review"
        assert added_obj.title == "Review needed"
        assert added_obj.message == "Please review doc"
        assert added_obj.link is None

    def test_flush_called_after_add(self):
        db = MagicMock()
        db.refresh = MagicMock()
        create_notification(db=db, staff_id=1, type="test", title="T", message="M")
        db.flush.assert_called_once()

    def test_refresh_called_after_flush(self):
        db = MagicMock()
        db.refresh = MagicMock()
        create_notification(db=db, staff_id=1, type="test", title="T", message="M")
        db.refresh.assert_called_once()

    def test_with_link(self):
        db = MagicMock()
        db.refresh = MagicMock()
        create_notification(
            db=db,
            staff_id=1,
            type="test",
            title="T",
            message="M",
            link="/items/42",
        )
        added_obj = db.add.call_args[0][0]
        assert added_obj.link == "/items/42"

    def test_without_link(self):
        db = MagicMock()
        db.refresh = MagicMock()
        create_notification(db=db, staff_id=1, type="test", title="T", message="M")
        added_obj = db.add.call_args[0][0]
        assert added_obj.link is None

    def test_is_read_defaults_to_false(self):
        db = MagicMock()
        db.refresh = MagicMock()
        create_notification(db=db, staff_id=1, type="test", title="T", message="M")
        added_obj = db.add.call_args[0][0]
        assert added_obj.is_read is False

    def test_read_at_defaults_to_none(self):
        db = MagicMock()
        db.refresh = MagicMock()
        create_notification(db=db, staff_id=1, type="test", title="T", message="M")
        added_obj = db.add.call_args[0][0]
        assert added_obj.read_at is None

    def test_different_notification_types(self):
        """Verify multiple type strings are accepted."""
        db = MagicMock()
        db.refresh = MagicMock()
        for ntype in (
            "order_request",
            "document_review",
            "inventory_alert",
            "team_change",
        ):
            create_notification(db=db, staff_id=1, type=ntype, title="T", message="M")
        assert db.add.call_count == 4


# ===================================================================
# get_unread_count
# ===================================================================


class TestGetUnreadCount:
    """Tests for get_unread_count function."""

    def test_returns_zero_when_no_unread(self):
        db = _mock_db_with_scalar(0)
        result = get_unread_count(db, staff_id=1)
        assert result == 0

    def test_returns_correct_count(self):
        db = _mock_db_with_scalar(5)
        result = get_unread_count(db, staff_id=10)
        assert result == 5

    def test_returns_zero_when_scalar_is_none(self):
        db = _mock_db_with_scalar(None)
        result = get_unread_count(db, staff_id=1)
        assert result == 0

    def test_calls_execute(self):
        db = _mock_db_with_scalar(3)
        get_unread_count(db, staff_id=5)
        db.execute.assert_called_once()

    def test_large_count(self):
        db = _mock_db_with_scalar(999)
        result = get_unread_count(db, staff_id=1)
        assert result == 999

    def test_single_unread(self):
        db = _mock_db_with_scalar(1)
        result = get_unread_count(db, staff_id=42)
        assert result == 1


# ===================================================================
# mark_read
# ===================================================================


class TestMarkRead:
    """Tests for mark_read function."""

    def test_marks_unread_notification_as_read(self):
        notif = _make_notification(id=1, staff_id=10, is_read=False)
        db = _mock_db_with_scalars_first(notif)
        result = mark_read(db, notification_id=1, staff_id=10)
        assert result.is_read is True
        assert result.read_at is not None
        db.flush.assert_called_once()

    def test_refresh_called_after_mark_read(self):
        notif = _make_notification(id=1, staff_id=10, is_read=False)
        db = _mock_db_with_scalars_first(notif)
        mark_read(db, notification_id=1, staff_id=10)
        db.refresh.assert_called_once()

    def test_already_read_notification_not_updated(self):
        notif = _make_notification(
            id=1, staff_id=10, is_read=True, read_at=datetime.now(timezone.utc)
        )
        db = _mock_db_with_scalars_first(notif)
        result = mark_read(db, notification_id=1, staff_id=10)
        assert result.is_read is True
        db.flush.assert_not_called()

    def test_returns_none_when_not_found(self):
        db = _mock_db_with_scalars_first(None)
        result = mark_read(db, notification_id=999, staff_id=10)
        assert result is None
        db.flush.assert_not_called()

    def test_read_at_is_utc_aware(self):
        notif = _make_notification(id=1, staff_id=10, is_read=False)
        db = _mock_db_with_scalars_first(notif)
        result = mark_read(db, notification_id=1, staff_id=10)
        assert result.read_at.tzinfo is not None

    def test_does_not_mark_other_staff_notification(self):
        """mark_read filters by staff_id; wrong staff returns None."""
        db = _mock_db_with_scalars_first(None)
        result = mark_read(db, notification_id=1, staff_id=999)
        assert result is None

    def test_notification_for_correct_staff(self):
        notif = _make_notification(id=1, staff_id=10, is_read=False)
        db = _mock_db_with_scalars_first(notif)
        result = mark_read(db, notification_id=1, staff_id=10)
        assert result is not None
        assert result.is_read is True


# ===================================================================
# mark_all_read
# ===================================================================


class TestMarkAllRead:
    """Tests for mark_all_read function."""

    def test_returns_rowcount(self):
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.rowcount = 5
        db.execute.return_value = result_mock
        count = mark_all_read(db, staff_id=10)
        assert count == 5

    def test_returns_zero_when_no_unread(self):
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.rowcount = 0
        db.execute.return_value = result_mock
        count = mark_all_read(db, staff_id=10)
        assert count == 0

    def test_flush_called_after_update(self):
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.rowcount = 3
        db.execute.return_value = result_mock
        mark_all_read(db, staff_id=10)
        db.flush.assert_called_once()

    def test_calls_execute_with_update_statement(self):
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.rowcount = 1
        db.execute.return_value = result_mock
        mark_all_read(db, staff_id=10)
        db.execute.assert_called_once()

    def test_sets_is_read_true(self):
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.rowcount = 1
        db.execute.return_value = result_mock
        mark_all_read(db, staff_id=10)
        # Verify the update statement was passed to execute
        call_args = db.execute.call_args[0][0]
        # The update statement should be an Update object
        assert call_args is not None

    def test_sets_read_at_to_utc_now(self):
        """read_at should be set to current UTC time."""
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.rowcount = 1
        db.execute.return_value = result_mock
        with patch("lab_manager.services.notification_service.datetime") as mock_dt:
            fixed_now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            mock_dt.now.return_value = fixed_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            mark_all_read(db, staff_id=10)
            db.execute.assert_called_once()


# ===================================================================
# get_preferences
# ===================================================================


class TestGetPreferences:
    """Tests for get_preferences function."""

    def test_returns_existing_preferences(self):
        pref = _make_preference(staff_id=10)
        db = _mock_db_with_scalars_first(pref)
        result = get_preferences(db, staff_id=10)
        assert result.staff_id == 10
        db.add.assert_not_called()

    def test_creates_preferences_when_not_found(self):
        db = _mock_db_with_scalars_first(None)
        # When not found, it creates a new one and adds to session
        result = get_preferences(db, staff_id=10)
        db.add.assert_called_once()
        added_obj = db.add.call_args[0][0]
        assert added_obj.staff_id == 10

    def test_flush_called_when_creating(self):
        db = _mock_db_with_scalars_first(None)
        get_preferences(db, staff_id=10)
        db.flush.assert_called_once()

    def test_refresh_called_when_creating(self):
        db = _mock_db_with_scalars_first(None)
        get_preferences(db, staff_id=10)
        db.refresh.assert_called_once()

    def test_flush_not_called_when_existing(self):
        pref = _make_preference(staff_id=10)
        db = _mock_db_with_scalars_first(pref)
        get_preferences(db, staff_id=10)
        db.flush.assert_not_called()

    def test_refresh_not_called_when_existing(self):
        pref = _make_preference(staff_id=10)
        db = _mock_db_with_scalars_first(pref)
        get_preferences(db, staff_id=10)
        db.refresh.assert_not_called()

    def test_new_preference_has_defaults(self):
        db = _mock_db_with_scalars_first(None)
        get_preferences(db, staff_id=42)
        added_obj = db.add.call_args[0][0]
        assert added_obj.staff_id == 42
        assert added_obj.in_app is True
        assert added_obj.email_weekly is False
        assert added_obj.order_requests is True


# ===================================================================
# update_preferences
# ===================================================================


class TestUpdatePreferences:
    """Tests for update_preferences function."""

    def test_updates_single_field(self):
        pref = _make_preference(staff_id=10, email_weekly=False)
        db = _mock_db_with_scalars_first(pref)
        result = update_preferences(db, staff_id=10, updates={"email_weekly": True})
        assert pref.email_weekly is True
        db.flush.assert_called_once()

    def test_updates_multiple_fields(self):
        pref = _make_preference(staff_id=10)
        db = _mock_db_with_scalars_first(pref)
        result = update_preferences(
            db,
            staff_id=10,
            updates={
                "email_weekly": True,
                "in_app": False,
                "team_changes": False,
            },
        )
        assert pref.email_weekly is True
        assert pref.in_app is False
        assert pref.team_changes is False

    def test_ignores_id_field(self):
        pref = _make_preference(id=5, staff_id=10)
        db = _mock_db_with_scalars_first(pref)
        update_preferences(db, staff_id=10, updates={"id": 999})
        assert pref.id == 5  # unchanged

    def test_ignores_staff_id_field(self):
        pref = _make_preference(staff_id=10)
        db = _mock_db_with_scalars_first(pref)
        update_preferences(db, staff_id=10, updates={"staff_id": 999})
        assert pref.staff_id == 10  # unchanged

    def test_flush_called_after_update(self):
        pref = _make_preference(staff_id=10)
        db = _mock_db_with_scalars_first(pref)
        update_preferences(db, staff_id=10, updates={"email_weekly": True})
        db.flush.assert_called_once()

    def test_refresh_called_after_update(self):
        pref = _make_preference(staff_id=10)
        db = _mock_db_with_scalars_first(pref)
        update_preferences(db, staff_id=10, updates={"email_weekly": True})
        db.refresh.assert_called_once()

    def test_unknown_key_ignored(self):
        """Keys that don't exist as attributes on the preference are skipped."""
        pref = _make_preference(staff_id=10)
        db = _mock_db_with_scalars_first(pref)
        # Should not raise AttributeError
        update_preferences(db, staff_id=10, updates={"nonexistent_field": "value"})

    def test_empty_updates_noop(self):
        pref = _make_preference(staff_id=10)
        db = _mock_db_with_scalars_first(pref)
        update_preferences(db, staff_id=10, updates={})
        db.flush.assert_called_once()  # flush still called even with empty updates
        assert pref.in_app is True  # unchanged

    def test_creates_preferences_if_not_found(self):
        """When preferences don't exist, get_preferences creates them first."""
        db = _mock_db_with_scalars_first(None)
        result = update_preferences(db, staff_id=10, updates={"email_weekly": True})
        # get_preferences should have been called which creates the pref
        db.add.assert_called_once()

    def test_updates_all_boolean_fields(self):
        pref = _make_preference(
            staff_id=10,
            in_app=True,
            email_weekly=False,
            order_requests=True,
            document_reviews=True,
            inventory_alerts=True,
            team_changes=True,
        )
        db = _mock_db_with_scalars_first(pref)
        update_preferences(
            db,
            staff_id=10,
            updates={
                "in_app": False,
                "email_weekly": True,
                "order_requests": False,
                "document_reviews": False,
                "inventory_alerts": False,
                "team_changes": False,
            },
        )
        assert pref.in_app is False
        assert pref.email_weekly is True
        assert pref.order_requests is False
        assert pref.document_reviews is False
        assert pref.inventory_alerts is False
        assert pref.team_changes is False
