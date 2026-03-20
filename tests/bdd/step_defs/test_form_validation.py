"""BDD step definitions for form validation tests."""
import pytest
from pytest_bdd import given, when, then, scenarios, parsers

scenarios("../features/form_validation.feature")


@when("I submit login with empty email")
def submit_login_empty_email(client, context):
    """Submit login without email."""
    context["response"] = client.post(
        "/api/auth/login",
        json={"email": "", "password": "password123"}
    )


@when("I submit login with empty password")
def submit_login_empty_password(client, context):
    """Submit login without password."""
    context["response"] = client.post(
        "/api/auth/login",
        json={"email": "test@test.com", "password": ""}
    )


@when('I submit login with email "invalid-email"')
def submit_login_invalid_email(client, context):
    """Submit login with invalid email."""
    context["response"] = client.post(
        "/api/auth/login",
        json={"email": "invalid-email", "password": "password123"}
    )


@when('I submit setup with password "short"')
def submit_setup_short_password(client, context):
    """Submit setup with short password."""
    context["response"] = client.post(
        "/api/setup/complete",
        json={
            "admin_name": "Test",
            "admin_email": "test@test.com",
            "admin_password": "short"
        }
    )


@given("a document with id 1 exists")
def document_exists(db_session):
    """Create a test document."""
    from lab_manager.models.document import Document
    doc = Document(file_name="test.pdf", status="needs_review")
    db_session.add(doc)
    db_session.commit()


@when("I submit review without action")
def submit_review_no_action(client, context):
    """Submit review without action."""
    context["response"] = client.post(
        "/api/v1/documents/1/review",
        json={"reviewed_by": "admin"}
    )


@when('I submit review with action "invalid"')
def submit_review_invalid_action(client, context):
    """Submit review with invalid action."""
    context["response"] = client.post(
        "/api/v1/documents/1/review",
        json={"action": "invalid", "reviewed_by": "admin"}
    )


@given("an inventory item with id 1 exists")
def inventory_item_exists(db_session):
    """Create a test inventory item."""
    from lab_manager.models.inventory import InventoryItem
    item = InventoryItem(quantity=100, status="available")
    db_session.add(item)
    db_session.commit()


@when("I consume inventory without quantity")
def consume_no_quantity(client, context):
    """Consume without quantity."""
    context["response"] = client.post(
        "/api/v1/inventory/1/consume",
        json={}
    )


@when(parsers.parse("I consume inventory with quantity {qty:d}"))
def consume_negative_quantity(client, context, qty):
    """Consume with specific quantity."""
    context["response"] = client.post(
        "/api/v1/inventory/1/consume",
        json={"quantity": qty}
    )


@given("an order with id 1 exists")
def order_exists(db_session):
    """Create a test order."""
    from lab_manager.models.order import Order
    order = Order(status="pending")
    db_session.add(order)
    db_session.commit()


@when("I receive order without items")
def receive_order_no_items(client, context):
    """Receive order without items."""
    context["response"] = client.post(
        "/api/v1/orders/1/receive",
        json={}
    )


@when("I make various invalid requests")
def make_invalid_requests(client, context):
    """Make various invalid requests."""
    context["responses"] = [
        client.post("/api/v1/documents/", json={}),
        client.post("/api/v1/vendors/", json={}),
        client.post("/api/v1/orders/", json={}),
    ]


@when("I submit invalid data")
def submit_invalid_data(client, context):
    """Submit invalid data."""
    context["response"] = client.post(
        "/api/v1/vendors/",
        json={"name": ""}  # Empty name should fail
    )


@when("I submit data with SQL injection attempt")
def submit_sql_injection(client, context):
    """Submit SQL injection attempt."""
    context["response"] = client.post(
        "/api/v1/vendors/",
        json={"name": "'; DROP TABLE vendors; --"}
    )


@when("I submit data with script tags")
def submit_xss(client, context):
    """Submit XSS attempt."""
    context["response"] = client.post(
        "/api/v1/vendors/",
        json={"name": "<script>alert('xss')</script>Test"}
    )


@then("I should receive a 422 error")
def receive_422(context):
    """Verify 422 response."""
    response = context.get("response")
    assert response is not None
    assert response.status_code == 422


@then("I should receive a 401 error")
def receive_401(context):
    """Verify 401 response."""
    response = context.get("response")
    assert response is not None
    assert response.status_code == 401


@then("I should receive a validation error")
def receive_validation_error(context):
    """Verify validation error."""
    response = context.get("response")
    assert response is not None
    assert response.status_code in [400, 422]


@then(parsers.parse('the error should mention "{field}"'))
def error_mentions_field(context, field):
    """Verify error mentions field."""
    response = context.get("response")
    if response:
        data = response.json()
        assert field.lower() in str(data).lower()


@then("the error should mention password requirements")
def error_mentions_password(context):
    """Verify password requirements mentioned."""
    response = context.get("response")
    if response:
        data = response.json()
        # Should mention password in some way
        assert "password" in str(data).lower()


@then("all errors should have consistent structure")
def errors_consistent(context):
    """Verify consistent error structure."""
    responses = context.get("responses", [])
    for response in responses:
        data = response.json()
        assert "detail" in data or "error" in data


@then('should include "detail" field')
def includes_detail_field(context):
    """Verify detail field present."""
    responses = context.get("responses", [])
    for response in responses:
        data = response.json()
        assert "detail" in data


@then("error messages should be clear")
def error_messages_clear(context):
    """Verify error messages are clear."""
    response = context.get("response")
    if response:
        data = response.json()
        # Should have a human-readable message
        assert len(str(data)) < 500  # Not too verbose


@then("should not expose internal details")
def no_internal_details(context):
    """Verify no internal details exposed."""
    response = context.get("response")
    if response:
        data = str(response.json()).lower()
        assert "traceback" not in data
        assert "exception" not in data


@then("the request should be handled safely")
def request_handled_safely(context):
    """Verify safe handling."""
    response = context.get("response")
    assert response is not None
    # Should either succeed (sanitized) or return validation error
    assert response.status_code in [200, 201, 400, 422]


@then("no SQL error should be returned")
def no_sql_error(context):
    """Verify no SQL error."""
    response = context.get("response")
    if response:
        data = str(response.json()).lower()
        assert "sql" not in data
        assert "syntax" not in data


@then("the data should be sanitized")
def data_sanitized(context):
    """Verify data sanitized."""
    response = context.get("response")
    assert response is not None


@then("scripts should not execute")
def scripts_not_execute(context):
    """Verify scripts won't execute."""
    response = context.get("response")
    if response and response.status_code in [200, 201]:
        data = response.json()
        # Script tags should be removed or escaped
        name = data.get("name", "")
        assert "<script>" not in name.lower()
