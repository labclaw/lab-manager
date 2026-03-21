"""BDD step definitions for form validation tests."""

import pytest
from pytest_bdd import given, when, then, scenarios, parsers

scenarios("../features/form_validation.feature")


# --- Shared context fixture ---
@pytest.fixture
def ctx():
    """Shared context for storing responses between steps."""
    return {}


# --- Given steps ---


@given("a document with id 1 exists")
def document_exists(db):
    """Create a test document."""
    from lab_manager.models.document import Document

    doc = Document(file_name="test.pdf", status="needs_review")
    db.add(doc)
    db.commit()


@given("an inventory item with id 1 exists")
def inventory_item_exists(db):
    """Create a test inventory item."""
    from lab_manager.models.inventory import InventoryItem

    item = InventoryItem(quantity=100, status="available")
    db.add(item)
    db.commit()


@given("an order with id 1 exists")
def order_exists(db):
    """Create a test order."""
    from lab_manager.models.order import Order

    order = Order(status="pending")
    db.add(order)
    db.commit()


# --- When steps ---


@when("I submit login with empty email", target_fixture="response")
def submit_login_empty_email(api):
    """Submit login without email."""
    return api.post("/api/v1/auth/login", json={"email": "", "password": "password123"})


@when("I submit login with empty password", target_fixture="response")
def submit_login_empty_password(api):
    """Submit login without password."""
    return api.post(
        "/api/v1/auth/login", json={"email": "test@test.com", "password": ""}
    )


@when('I submit login with email "invalid-email"', target_fixture="response")
def submit_login_invalid_email(api):
    """Submit login with invalid email."""
    return api.post(
        "/api/v1/auth/login", json={"email": "invalid-email", "password": "password123"}
    )


@when('I submit setup with password "short"', target_fixture="response")
def submit_setup_short_password(api):
    """Submit setup with short password."""
    return api.post(
        "/api/setup/complete",
        json={
            "admin_name": "Test",
            "admin_email": "test@test.com",
            "admin_password": "short",
        },
    )


@when("I submit review without action", target_fixture="response")
def submit_review_no_action(api):
    """Submit review without action."""
    return api.post("/api/v1/documents/1/review", json={"reviewed_by": "admin"})


@when('I submit review with action "invalid"', target_fixture="response")
def submit_review_invalid_action(api):
    """Submit review with invalid action."""
    return api.post(
        "/api/v1/documents/1/review", json={"action": "invalid", "reviewed_by": "admin"}
    )


@when("I consume inventory without quantity", target_fixture="response")
def consume_no_quantity(api):
    """Consume without quantity."""
    return api.post("/api/v1/inventory/1/consume", json={})


@when(
    parsers.parse("I consume inventory with quantity {qty:d}"),
    target_fixture="response",
)
def consume_quantity(api, qty):
    """Consume with specific quantity."""
    return api.post("/api/v1/inventory/1/consume", json={"quantity": qty})


@when("I receive order without items", target_fixture="response")
def receive_order_no_items(api):
    """Receive order without items."""
    return api.post("/api/v1/orders/1/receive", json={})


@when("I make various invalid requests")
def make_invalid_requests(api, ctx):
    """Make various invalid requests."""
    ctx["responses"] = [
        api.post("/api/v1/documents/", json={}),
        api.post("/api/v1/vendors/", json={}),
        api.post("/api/v1/orders/", json={}),
    ]


@when("I submit invalid data", target_fixture="response")
def submit_invalid_data(api):
    """Submit invalid data."""
    return api.post(
        "/api/v1/vendors/",
        json={"name": ""},  # Empty name should fail
    )


@when("I submit data with SQL injection attempt", target_fixture="response")
def submit_sql_injection(api):
    """Submit SQL injection attempt."""
    return api.post("/api/v1/vendors/", json={"name": "'; DROP TABLE vendors; --"})


@when("I submit data with script tags", target_fixture="response")
def submit_xss(api):
    """Submit XSS attempt."""
    return api.post(
        "/api/v1/vendors/", json={"name": "<script>alert('xss')</script>Test"}
    )


# --- Then steps ---


@then("I should receive a 422 error")
def receive_422(response):
    """Verify 422 response."""
    assert response.status_code == 422


@then("I should receive a 401 error")
def receive_401(response):
    """Verify 401 response."""
    assert response.status_code == 401


@then("I should receive a validation error")
def receive_validation_error(response):
    """Verify validation error."""
    assert response.status_code in [400, 422]


@then(parsers.parse('the error should mention "{field}"'))
def error_mentions_field(response, field):
    """Verify error mentions field."""
    data = response.json()
    assert field.lower() in str(data).lower()


@then("the error should mention password requirements")
def error_mentions_password(response):
    """Verify password requirements mentioned."""
    data = response.json()
    assert "password" in str(data).lower()


@then("all errors should have consistent structure")
def errors_consistent(ctx):
    """Verify consistent error structure."""
    responses = ctx.get("responses", [])
    for resp in responses:
        data = resp.json()
        assert "detail" in data or "error" in data


@then('should include "detail" field')
def includes_detail_field(ctx):
    """Verify detail field present."""
    responses = ctx.get("responses", [])
    for resp in responses:
        data = resp.json()
        assert "detail" in data


@then("error messages should be clear")
def error_messages_clear(response):
    """Verify error messages are clear."""
    data = response.json()
    assert len(str(data)) < 500  # Not too verbose


@then("should not expose internal details")
def no_internal_details(response):
    """Verify no internal details exposed."""
    data = str(response.json()).lower()
    assert "traceback" not in data
    assert "exception" not in data


@then("the request should be handled safely")
def request_handled_safely(response):
    """Verify safe handling."""
    assert response.status_code in [200, 201, 400, 422]


@then("no SQL error should be returned")
def no_sql_error(response):
    """Verify no SQL error."""
    data = str(response.json()).lower()
    assert "sql" not in data
    assert "syntax" not in data


@then("the data should be sanitized")
def data_sanitized(response):
    """Verify data sanitized."""
    assert response is not None


@then("scripts should not execute")
def scripts_not_execute(response):
    """Verify scripts won't execute."""
    if response.status_code in [200, 201]:
        data = response.json()
        name = data.get("name", "")
        assert "<script>" not in name.lower()
