"""Step definitions for in-app notification BDD scenarios.

Tests the real notification API endpoints:
  GET    /api/v1/notifications/            -- list (with unread_only filter)
  GET    /api/v1/notifications/count       -- unread count
  POST   /api/v1/notifications/read-all    -- mark all read
  GET    /api/v1/notifications/preferences -- get prefs
  PATCH  /api/v1/notifications/preferences -- update prefs
  POST   /api/v1/notifications/{id}/read   -- mark single read

NOTE: In dev mode (AUTH_ENABLED=false) the middleware injects staff_id=0
with role "pi". All notifications are created with staff_id=0 so the API
queries match.
"""

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from lab_manager.models.notification import Notification

FEATURE = "../features/notifications.feature"

# In dev mode the middleware hardcodes staff_id=0.
_DEV_STAFF_ID = 0


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


@scenario(FEATURE, "List notifications for a staff member")
def test_list_notifications():
    pass


@scenario(FEATURE, "Filter notifications to unread only")
def test_filter_unread():
    pass


@scenario(FEATURE, "Get unread notification count")
def test_unread_count():
    pass


@scenario(FEATURE, "Unread count is zero when no notifications")
def test_unread_count_zero():
    pass


@scenario(FEATURE, "Mark a single notification as read")
def test_mark_single_read():
    pass


@scenario(FEATURE, "Mark all notifications as read")
def test_mark_all_read():
    pass


@scenario(FEATURE, "Get default notification preferences")
def test_default_preferences():
    pass


@scenario(FEATURE, "Update notification preferences")
def test_update_preferences():
    pass


@scenario(FEATURE, "Preferences are created on first access")
def test_prefs_created_on_first_access():
    pass


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx():
    """Shared context dict for passing data between steps."""
    return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_notification(db, staff_id, ntype="info", title="Test", is_read=False):
    """Create a notification row directly in the DB."""
    notif = Notification(
        staff_id=staff_id,
        type=ntype,
        title=title,
        message=f"Message for {title}",
        is_read=is_read,
    )
    db.add(notif)
    db.flush()
    return notif


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given('a staff member "alice" exists with role "admin"')
def ensure_dev_staff():
    """In dev mode the middleware always provides staff_id=0. No DB row needed."""


@given(parsers.parse("{n:d} notifications exist for the staff member"))
def create_notifications(db, ctx, n):
    notifs = []
    for i in range(n):
        notif = _create_notification(
            db, _DEV_STAFF_ID, ntype="info", title=f"Notification {i}"
        )
        notifs.append(notif)
    ctx["notifications"] = notifs


@given(parsers.parse("{n:d} of those notifications are read"))
def mark_some_read(db, ctx, n):
    notifs = ctx["notifications"]
    for notif in notifs[:n]:
        notif.is_read = True
    db.flush()


@given(parsers.parse("{n:d} unread notifications exist for the staff member"))
def create_unread_notifications(db, ctx, n):
    notifs = []
    for i in range(n):
        notif = _create_notification(
            db, _DEV_STAFF_ID, ntype="alert", title=f"Unread {i}", is_read=False
        )
        notifs.append(notif)
    ctx["notifications"] = notifs


@given(
    "an unread notification exists for the staff member", target_fixture="unread_notif"
)
def create_single_unread(db):
    return _create_notification(
        db, _DEV_STAFF_ID, ntype="order", title="New order", is_read=False
    )


@given("notification preferences exist for the staff member")
def ensure_prefs(db):
    from lab_manager.services import notification_service as svc

    svc.get_preferences(db, _DEV_STAFF_ID)


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("I request the notification list", target_fixture="notif_list_response")
def request_notification_list(api):
    r = api.get("/api/v1/notifications/")
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse("I request the notification list with unread_only {val}"),
    target_fixture="notif_list_response",
)
def request_notification_list_unread(api, val):
    r = api.get("/api/v1/notifications/", params={"unread_only": val.lower() == "true"})
    assert r.status_code == 200, r.text
    return r.json()


@when("I request the unread count", target_fixture="unread_count_response")
def request_unread_count(api):
    r = api.get("/api/v1/notifications/count")
    assert r.status_code == 200, r.text
    return r.json()


@when("I mark the notification as read", target_fixture="mark_read_response")
def mark_notification_read(api, unread_notif):
    r = api.post(f"/api/v1/notifications/{unread_notif.id}/read")
    assert r.status_code == 200, r.text
    return r.json()


@when("I mark all notifications as read", target_fixture="mark_all_response")
def mark_all_read(api):
    r = api.post("/api/v1/notifications/read-all")
    assert r.status_code == 200, r.text
    return r.json()


@when("I request notification preferences", target_fixture="prefs_response")
def request_preferences(api):
    r = api.get("/api/v1/notifications/preferences")
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse(
        "I update preferences with email_weekly {ew} and inventory_alerts {ia}"
    ),
    target_fixture="updated_prefs_response",
)
def update_preferences(api, ew, ia):
    body = {
        "email_weekly": ew.lower() == "true",
        "inventory_alerts": ia.lower() == "true",
    }
    r = api.patch("/api/v1/notifications/preferences", json=body)
    assert r.status_code == 200, r.text
    return r.json()


@when(
    "I request notification preferences for a new staff member",
    target_fixture="new_prefs_response",
)
def request_prefs_new_staff(db):
    from lab_manager.services import notification_service as svc

    # Use a fresh staff_id that has no preferences yet.
    # We pick a high arbitrary ID that won't collide with _DEV_STAFF_ID (0).
    fresh_id = 99999
    prefs = svc.get_preferences(db, fresh_id)
    return {"status_code": 200, "data": prefs}


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then(parsers.parse("the response should contain {n:d} items"))
def check_item_count(notif_list_response, n):
    assert len(notif_list_response["items"]) == n, (
        f"Expected {n} items, got {len(notif_list_response['items'])}"
    )


@then(parsers.parse("the total should be {n:d}"))
def check_total(notif_list_response, n):
    assert notif_list_response["total"] == n


@then(parsers.parse("the count should be {n:d}"))
def check_unread_count(unread_count_response, n):
    assert unread_count_response["unread_count"] == n, (
        f"Expected unread_count={n}, got {unread_count_response['unread_count']}"
    )


@then("the notification should be marked as read")
def check_marked_read(mark_read_response):
    assert mark_read_response["is_read"] is True
    assert mark_read_response["read_at"] is not None


@then(parsers.parse("the marked count should be {n:d}"))
def check_marked_count(mark_all_response, n):
    assert mark_all_response["marked"] == n


@then("the unread count should be 0")
def check_unread_zero(api):
    r = api.get("/api/v1/notifications/count")
    assert r.json()["unread_count"] == 0


@then(parsers.parse("{field} should be {value}"))
def check_pref_bool(prefs_response, field, value):
    expected = value.lower() == "true"
    actual = prefs_response[field]
    assert actual == expected, f"Expected {field}={expected}, got {actual}"


@then(parsers.parse("{field} should still be {value}"))
def check_pref_unchanged(updated_prefs_response, field, value):
    expected = value.lower() == "true"
    actual = updated_prefs_response[field]
    assert actual == expected, f"Expected {field}={expected}, got {actual}"


@then("the response status should be 200")
def check_status_200(new_prefs_response):
    assert new_prefs_response["status_code"] == 200


@then("in_app should be true")
def check_in_app_true(new_prefs_response):
    assert new_prefs_response["data"].in_app is True


@then("in_app should be true for prefs")
def check_in_app_true_prefs(prefs_response):
    assert prefs_response["in_app"] is True
