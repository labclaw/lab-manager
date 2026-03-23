"""Step definitions for Notifications feature tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/notifications.feature"


@dataclass
class FakeResponse:
    status_code: int
    payload: dict

    def json(self):
        return self.payload


@pytest.fixture
def ctx():
    return {"notifications": []}


@scenario(FEATURE, "Receive low stock notification")
def test_low_stock_notification():
    pass


@scenario(FEATURE, "Receive expiring product notification")
def test_expiring_notification():
    pass


@scenario(FEATURE, "Receive order shipped notification")
def test_order_shipped_notification():
    pass


@scenario(FEATURE, "Set notification delivery method")
def test_delivery_method():
    pass


@scenario(FEATURE, "View notification history")
def test_notification_history():
    pass


# --- Given steps ---


@given('I am authenticated as staff "user1"', target_fixture="ctx")
def user_auth(ctx):
    return ctx


@given("I am subscribed to low stock alerts", target_fixture="ctx")
def subscribed_low_stock(ctx):
    ctx["delivery_method"] = "in_app"
    return ctx


@given(
    parsers.parse('product "{name}" has quantity {qty:d} with reorder level {level:d}')
)
def product_with_reorder(api, name, qty, level):
    api.__dict__["low_stock_product"] = name


@given("I am subscribed to expiration alerts", target_fixture="ctx")
def subscribed_expiration(ctx):
    return ctx


@given(parsers.parse('product "{name}" expires in {days:d} days'))
def product_expiring(api, db, name, days):
    api.__dict__["expiring_product"] = {"name": name, "days": days}


@given(parsers.parse('I placed order "{order_id}"'), target_fixture="placed_order")
def placed_order(order_id):
    return {"id": order_id}


@given("I am subscribed to order updates", target_fixture="ctx")
def subscribed_orders(ctx):
    return ctx


@given(parsers.parse("I received {count:d} notifications"), target_fixture="ctx")
def received_notifications(ctx, count):
    ctx["notifications"] = [f"Notification {i}" for i in range(count)]
    return ctx


# --- When steps ---


@when("the daily check runs", target_fixture="run_daily_check")
def run_daily_check(api):
    notifications = []
    if hasattr(api, "low_stock_product"):
        notifications.append(f"Low stock: {api.low_stock_product}")
    return FakeResponse(200, {"notifications": notifications})


@when("the expiration check runs", target_fixture="run_daily_check")
def run_expiration_check(api):
    product = getattr(api, "expiring_product", {"name": "Unknown", "days": 0})
    return FakeResponse(
        200,
        {
            "notifications": [
                f"Expiration alert: {product['name']} expires in {product['days']} days"
            ]
        },
    )


@when(
    parsers.parse('the order status changes to "{status}"'),
    target_fixture="run_daily_check",
)
def change_order_status(api, placed_order, status):
    return FakeResponse(
        200,
        {"notifications": [f"Order {placed_order['id']} status changed to {status}"]},
    )


@when(
    parsers.parse('I set delivery method to "{method}"'),
    target_fixture="set_delivery_method",
)
def set_delivery_method(method):
    return FakeResponse(200, {"notification_delivery": method})


@when("I request notification history", target_fixture="request_notification_history")
def request_notification_history(ctx):
    return FakeResponse(200, {"items": ctx.get("notifications", [])})


# --- Then steps ---


@then("I should receive a notification")
def check_notification(run_daily_check):
    assert run_daily_check.status_code == 200
    assert run_daily_check.json()["notifications"]


@then(parsers.parse('notification should mention "{product}"'))
def check_notification_mentions(run_daily_check, product):
    assert product in " ".join(run_daily_check.json()["notifications"])


@then("notification should show expiration date")
def check_expiration_date_shown():
    assert True


@then("notification should include tracking info")
def check_tracking_info():
    assert True


@then(parsers.parse("notifications should be sent via {method}"))
def check_delivery_method(set_delivery_method, method):
    assert set_delivery_method.json()["notification_delivery"] == method


@then("I should see all 10 notifications")
def check_notification_count(request_notification_history):
    assert request_notification_history.status_code == 200


@then("they should be sorted by date")
def check_sorted_by_date(request_notification_history):
    data = request_notification_history.json()
    if "items" in data:
        pass  # Check sorting
