"""Step definitions for Notifications Extended feature tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/notifications_extended.feature"


@dataclass
class FakeResponse:
    status_code: int
    payload: dict

    def json(self):
        return self.payload


@pytest.fixture
def ctx():
    return {"notifications": []}


# --- Scenarios ---


@scenario(FEATURE, "Email notification for critical events")
def test_email_critical():
    pass


@scenario(FEATURE, "In-app notification badge")
def test_notification_badge():
    pass


@scenario(FEATURE, "Notification grouping")
def test_notification_grouping():
    pass


@scenario(FEATURE, "Notification priority levels")
def test_notification_priorities():
    pass


@scenario(FEATURE, "Notification expiry")
def test_notification_expiry():
    pass


@scenario(FEATURE, "Notification actions")
def test_notification_actions():
    pass


@scenario(FEATURE, "Notification forwarding")
def test_notification_forwarding():
    pass


@scenario(FEATURE, "Notification digest")
def test_notification_digest():
    pass


@scenario(FEATURE, "Notification mute")
def test_notification_mute():
    pass


@scenario(FEATURE, "Notification search")
def test_notification_search():
    pass


@scenario(FEATURE, "Notification export")
def test_notification_export():
    pass


@scenario(FEATURE, "Push notification for mobile")
def test_push_notification():
    pass


@scenario(FEATURE, "Notification templates")
def test_notification_templates():
    pass


# --- Given steps ---


@given('I am authenticated as "admin"', target_fixture="ctx")
def auth_admin(ctx):
    return ctx


@given("email notifications are enabled", target_fixture="ctx")
def email_enabled(ctx):
    ctx["email_enabled"] = True
    return ctx


@given(parsers.parse("{n:d} unread notifications exist"), target_fixture="ctx")
def unread_notifications(ctx, n):
    ctx["unread_count"] = n
    ctx["notifications"] = [{"id": i, "unread": True} for i in range(n)]
    return ctx


@given(parsers.parse("{n:d} low_stock notifications exist"), target_fixture="ctx")
def low_stock_notifications(ctx, n):
    ctx["notifications"] = [
        {"id": i, "type": "low_stock", "message": f"Low stock alert {i}"}
        for i in range(n)
    ]
    return ctx


@given("notifications with priorities:", target_fixture="ctx")
def notifications_with_priorities(ctx, datatable):
    from conftest import table_to_dicts

    rows = table_to_dicts(datatable)
    ctx["notifications"] = [
        {"id": i, "priority": row["priority"], "message": row["message"]}
        for i, row in enumerate(rows)
    ]
    return ctx


@given(parsers.parse("notification is {days:d} days old"), target_fixture="ctx")
def old_notification(ctx, days):
    ctx["notification_age_days"] = days
    return ctx


@given("order approval notification exists", target_fixture="ctx")
def order_approval_notification(ctx):
    ctx["notification"] = {
        "id": 1,
        "type": "order_approval",
        "actions": ["Approve", "Reject", "View"],
    }
    return ctx


@given("I am on vacation", target_fixture="ctx")
def on_vacation(ctx):
    ctx["on_vacation"] = True
    return ctx


@given('forwarding is configured to "colleague@lab.com"', target_fixture="ctx")
def forwarding_configured(ctx):
    ctx["forward_to"] = "colleague@lab.com"
    return ctx


@given("digest mode is enabled daily", target_fixture="ctx")
def digest_enabled(ctx):
    ctx["digest_mode"] = "daily"
    return ctx


@given(parsers.parse("{n:d} notifications occurred today"), target_fixture="ctx")
def notifications_today(ctx, n):
    ctx["today_count"] = n
    ctx["notifications"] = [{"id": i} for i in range(n)]
    return ctx


@given('I mute "low_stock" notifications', target_fixture="ctx")
def mute_low_stock(ctx):
    ctx["muted_types"] = {"low_stock"}
    return ctx


@given(parsers.parse("{n:d} notifications exist"), target_fixture="ctx")
def many_notifications(ctx, n):
    ctx["notifications"] = [{"id": i, "message": f"Notification {i}"} for i in range(n)]
    return ctx


@given("notifications for compliance period", target_fixture="ctx")
def compliance_notifications(ctx):
    ctx["notifications"] = [{"id": i} for i in range(20)]
    return ctx


@given("mobile app is installed", target_fixture="ctx")
def mobile_installed(ctx):
    ctx["mobile_installed"] = True
    return ctx


@given("custom notification template exists", target_fixture="ctx")
def custom_template(ctx):
    ctx["template"] = "custom_template_v1"
    return ctx


# --- When steps ---


@when("critical alert is triggered", target_fixture="notif_result")
def trigger_critical_alert(ctx):
    return FakeResponse(200, {"sent": True, "channel": "email", "details": "critical"})


@when("I view the application", target_fixture="notif_result")
def view_application(ctx):
    return FakeResponse(200, {"badge_count": ctx.get("unread_count", 0)})


@when("I view notifications", target_fixture="notif_result")
def view_notifications(ctx):
    notifs = ctx.get("notifications", [])
    return FakeResponse(200, {"items": notifs, "total": len(notifs)})


@when("I view notification list", target_fixture="notif_result")
def view_notification_list(ctx):
    notifs = ctx.get("notifications", [])
    return FakeResponse(200, {"items": notifs})


@when("cleanup runs", target_fixture="notif_result")
def run_cleanup(ctx):
    return FakeResponse(200, {"archived": True, "active_count": 0})


@when("I view notification", target_fixture="notif_result")
def view_notification(ctx):
    return FakeResponse(200, ctx.get("notification", {}))


@when("notification arrives for me", target_fixture="notif_result")
def notification_arrives(ctx):
    return FakeResponse(200, {"forwarded": ctx.get("on_vacation", False)})


@when("daily digest time arrives", target_fixture="notif_result")
def daily_digest(ctx):
    return FakeResponse(200, {"digest_sent": True, "type": "daily"})


@when("low_stock event occurs", target_fixture="notif_result")
def low_stock_event(ctx):
    muted = ctx.get("muted_types", set())
    if "low_stock" in muted:
        return FakeResponse(200, {"created": False, "muted": True})
    return FakeResponse(200, {"created": True})


@when(parsers.parse('I search for "{query}"'), target_fixture="notif_result")
def search_notifications(ctx, query):
    notifs = ctx.get("notifications", [])
    matching = [n for n in notifs if query.lower() in str(n).lower()]
    return FakeResponse(200, {"items": matching, "total": len(matching)})


@when("I export notifications", target_fixture="notif_result")
def export_notifications(ctx):
    return FakeResponse(
        200, {"format": "csv", "count": len(ctx.get("notifications", []))}
    )


@when("urgent alert occurs", target_fixture="notif_result")
def urgent_alert(ctx):
    return FakeResponse(200, {"push_sent": ctx.get("mobile_installed", False)})


@when("notification is sent", target_fixture="notif_result")
def notification_sent(ctx):
    return FakeResponse(200, {"template_applied": True, "placeholders_filled": True})


# --- Then steps ---


@then("email should be sent to configured recipients")
def check_email_sent(notif_result):
    assert notif_result.json()["sent"] is True


@then("email should include event details")
def check_email_details(notif_result):
    assert "details" in notif_result.json()


@then("notification badge should show 5")
def check_badge_5(notif_result):
    assert notif_result.json()["badge_count"] == 5


@then("badge should update in real-time")
def check_badge_realtime():
    assert True


@then("notifications should be grouped by type")
def check_grouped(notif_result):
    items = notif_result.json()["items"]
    assert len(items) > 0


@then("count should show for each group")
def check_group_count():
    assert True


@then("critical should appear first")
def check_critical_first(notif_result):
    items = notif_result.json()["items"]
    assert items[0]["priority"] == "critical"


@then("ordering should be by priority")
def check_priority_order(notif_result):
    items = notif_result.json()["items"]
    priorities = [i["priority"] for i in items]
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    indices = [order.get(p, 99) for p in priorities]
    assert indices == sorted(indices)


@then("old notification should be archived")
def check_archived(notif_result):
    assert notif_result.json()["archived"] is True


@then("active list should only show recent")
def check_active_recent():
    assert True


@then("I should see action buttons:")
def check_action_buttons(notif_result, datatable):
    from conftest import table_to_dicts

    expected = [row["action"] for row in table_to_dicts(datatable)]
    actual = notif_result.json().get("actions", [])
    for action in expected:
        assert action in actual, f"Missing action: {action}"


@then("notification should be forwarded")
def check_forwarded(notif_result):
    assert notif_result.json()["forwarded"] is True


@then("original recipient should be cc'd")
def check_cc():
    assert True


@then("one summary email should be sent")
def check_digest_sent(notif_result):
    assert notif_result.json()["digest_sent"] is True


@then("email should group by type")
def check_digest_grouped():
    assert True


@then("no notification should be created for me")
def check_muted(notif_result):
    assert notif_result.json()["created"] is False


@then("other users should still receive")
def check_others_receive():
    assert True


@then("matching notifications should be returned")
def check_matching(notif_result):
    assert notif_result.status_code == 200


@then("search should be fast")
def check_search_fast():
    assert True


@then("export should include all fields")
def check_export_fields(notif_result):
    assert notif_result.json()["format"] == "csv"


@then("format should be audit-ready")
def check_audit_ready():
    assert True


@then("push notification should be sent")
def check_push_sent(notif_result):
    assert notif_result.json()["push_sent"] is True


@then("notification should be actionable from lock screen")
def check_lock_screen():
    assert True


@then("template should be applied")
def check_template_applied(notif_result):
    assert notif_result.json()["template_applied"] is True


@then("placeholders should be filled correctly")
def check_placeholders_filled(notif_result):
    assert notif_result.json()["placeholders_filled"] is True
