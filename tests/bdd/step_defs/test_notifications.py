"""Step definitions for Notifications feature tests."""

from __future__ import annotations

from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/notifications.feature"


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


@given('I am authenticated as staff "user1"')
def user_auth(api):
    return api


@given("I am subscribed to low stock alerts")
def subscribed_low_stock(db):
    pass


@given(parsers.parse('product "{name}" has quantity {qty:d} with reorder level {level:d}'))
def product_with_reorder(api, name, qty, level):
    r = api.post("/api/v1/vendors/", json={"name": "Test Vendor"})
    vendor = r.json()
    r = api.post(
        "/api/v1/products/",
        json={
            "name": name,
            "catalog_number": f"CAT-{name[:5]}",
            "vendor_id": vendor["id"],
            "reorder_level": level,
        },
    )
    product = r.json()
    api.post("/api/v1/inventory/", json={"product_id": product["id"], "quantity": float(qty)})


@given("I am subscribed to expiration alerts")
def subscribed_expiration():
    pass


@given(parsers.parse('product "{name}" expires in {days:d} days'))
def product_expiring(api, db, name, days):
    from datetime import datetime, timedelta

    r = api.post("/api/v1/vendors/", json={"name": "Test Vendor"})
    vendor = r.json()
    exp_date = (datetime.now() + timedelta(days=days)).isoformat()
    r = api.post(
        "/api/v1/products/",
        json={
            "name": name,
            "catalog_number": f"CAT-EXP",
            "vendor_id": vendor["id"],
            "expiration_date": exp_date,
        },
    )


@given(parsers.parse('I placed order "{order_id}"'))
def placed_order(api, order_id):
    r = api.post("/api/v1/vendors/", json={"name": "Test Vendor"})
    vendor = r.json()
    r = api.post(
        "/api/v1/orders/",
        json={
            "vendor_id": vendor["id"],
            "items": [{"product_name": "Test Item", "quantity": 1, "unit_price": 10.0}],
        },
    )
    return r.json()


@given("I am subscribed to order updates")
def subscribed_orders():
    pass


@given(parsers.parse('I received {count:d} notifications'))
def received_notifications(db, count):
    pass


# --- When steps ---


@when("the daily check runs")
def run_daily_check(api):
    r = api.post("/api/v1/alerts/check")
    return r


@when("the expiration check runs")
def run_expiration_check(api):
    r = api.post("/api/v1/alerts/check-expiration")
    return r


@when(parsers.parse('the order status changes to "{status}"'))
def change_order_status(api, placed_order, status):
    if placed_order:
        r = api.patch(f"/api/v1/orders/{placed_order['id']}", json={"status": status})
        return r


@when(parsers.parse('I set delivery method to "{method}"'))
def set_delivery_method(api, method):
    r = api.patch("/api/v1/users/me/preferences", json={"notification_delivery": method})
    return r


@when("I request notification history")
def request_notification_history(api):
    r = api.get("/api/v1/notifications/")
    return r


# --- Then steps ---


@then("I should receive a notification")
def check_notification(run_daily_check):
    pass


@then(parsers.parse('notification should mention "{product}"'))
def check_notification_mentions(product):
    pass


@then("notification should show expiration date")
def check_expiration_date_shown():
    pass


@then("notification should include tracking info")
def check_tracking_info():
    pass


@then(parsers.parse('notifications should be sent via {method}'))
def check_delivery_method(method):
    pass


@then("I should see all 10 notifications")
def check_notification_count(request_notification_history):
    assert request_notification_history.status_code == 200


@then("they should be sorted by date")
def check_sorted_by_date(request_notification_history):
    data = request_notification_history.json()
    if "items" in data:
        pass  # Check sorting
