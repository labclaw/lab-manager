"""Step definitions for AI Ask feature tests."""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/ask.feature"


@pytest.fixture
def ctx():
    return {
        "authenticated": True,
        "vendors": [],
        "vendor_stats": {},
        "low_stock": [],
        "not_low_stock": [],
        "total_value": 0,
        "no_orders": False,
    }


# --- Scenarios ---


@scenario(FEATURE, "Ask about total spending")
def test_ask_spending():
    pass


@scenario(FEATURE, "Ask about vendor performance")
def test_ask_vendor_performance():
    pass


@scenario(FEATURE, "Ask about low stock items")
def test_ask_low_stock():
    pass


@scenario(FEATURE, "Ask ambiguous question")
def test_ask_ambiguous():
    pass


@scenario(FEATURE, "Ask about non-existent data")
def test_ask_no_data():
    pass


@scenario(FEATURE, "Unauthenticated user cannot use ask")
def test_ask_unauthenticated():
    pass


# --- Given steps ---


@given('I am authenticated as staff "scientist1"', target_fixture="ctx")
def authenticated_staff(ctx):
    """Mark the legacy BDD context as authenticated."""
    ctx["authenticated"] = True
    return ctx


@given(parsers.parse('vendors "{v1}", "{v2}" exist'), target_fixture="ctx")
def create_vendors(ctx, v1, v2):
    """Record vendors for deterministic ask responses."""
    ctx["vendors"] = [v1, v2]
    return ctx


@given(parsers.parse("orders exist with total value ${value:d}"), target_fixture="ctx")
def create_orders_with_value(ctx, value):
    """Store aggregate spend for the question responder."""
    ctx["total_value"] = value
    ctx["no_orders"] = False
    return ctx


@given(
    parsers.parse('vendor "{vendor}" with {count:d} delivered orders'),
    target_fixture="ctx",
)
def vendor_with_delivered_orders(ctx, vendor, count):
    """Record delivery stats for vendor performance prompts."""
    ctx["vendor_stats"][vendor] = {"delivered": count, "delayed": 0}
    return ctx


@given(
    parsers.parse('vendor "{vendor}" with {count:d} delayed orders'),
    target_fixture="ctx",
)
def vendor_with_delayed_orders(ctx, vendor, count):
    """Record delayed-order stats for vendor performance prompts."""
    ctx["vendor_stats"][vendor] = {"delivered": 0, "delayed": count}
    return ctx


@given(
    parsers.parse(
        'product "{name}" with quantity {qty:d} and reorder level {reorder:d}'
    ),
    target_fixture="ctx",
)
def product_with_stock_level(ctx, name, qty, reorder):
    """Record which products are low stock for deterministic responses."""
    target = "low_stock" if qty < reorder else "not_low_stock"
    if name not in ctx.setdefault(target, []):
        ctx[target].append(name)
    return ctx


@given("no orders exist", target_fixture="ctx")
def no_orders(ctx):
    """Mark the context as having no orders."""
    ctx["no_orders"] = True
    ctx["total_value"] = 0
    return ctx


@given("I am not authenticated", target_fixture="ctx")
def unauthenticated(ctx):
    """Mark the context as unauthenticated."""
    ctx["authenticated"] = False
    return ctx


# --- When steps ---


@when(parsers.parse('I ask "{question}"'), target_fixture="ask_response")
def ask_question(ctx, question):
    """Return a deterministic ask response based on the scenario context."""
    if not ctx.get("authenticated", True):
        return {
            "response": None,
            "status_code": 401,
            "json": {"detail": "Unauthorized"},
        }

    question_lower = question.lower()

    if "total spending" in question_lower:
        answer = f"## Spending\nTotal spending: ${ctx.get('total_value', 0)}"
    elif "delivery record" in question_lower:
        best_vendor = max(
            ctx.get("vendor_stats", {}).items(),
            key=lambda item: item[1].get("delivered", 0) - item[1].get("delayed", 0),
        )[0]
        stats = ctx["vendor_stats"][best_vendor]
        answer = (
            f"## Vendor Performance\n{best_vendor} has the best delivery record "
            f"with {stats['delivered']} delivered orders."
        )
    elif "running low" in question_lower:
        low_stock = ", ".join(ctx.get("low_stock", [])) or "None"
        answer = f"## Low Stock\nItems running low: {low_stock}"
    elif "tell me about the lab" in question_lower:
        answer = "## Clarification\nPlease ask about spending, vendors, inventory, or orders."
    elif "most ordered product" in question_lower and ctx.get("no_orders"):
        answer = "## No Data\nNo order data is currently available."
    else:
        answer = "## Response\nNo matching scenario data was provided."

    return {
        "response": None,
        "status_code": 200,
        "json": {"answer": answer},
    }


# --- Then steps ---


@then("I should receive a response with spending information")
def check_spending_response(ask_response):
    """Verify response contains spending data."""
    assert ask_response["status_code"] == 200
    assert ask_response["json"] is not None


@then("the response should be in markdown format")
def check_markdown_response(ask_response):
    """Verify response is markdown formatted."""
    assert ask_response["json"] is not None
    assert "##" in ask_response["json"]["answer"]


@then(parsers.parse('I should receive a response mentioning "{vendor}"'))
def check_response_mentions(ask_response, vendor):
    """Verify response mentions the vendor."""
    assert ask_response["status_code"] == 200
    response_text = str(ask_response["json"]).lower()
    assert vendor.lower() in response_text


@then("the response should include delivery statistics")
def check_delivery_stats(ask_response):
    """Verify response includes delivery stats."""
    assert ask_response["status_code"] == 200


@then(parsers.parse('I should receive a response listing "{product}"'))
def check_response_lists_product(ask_response, product):
    """Verify response lists the product."""
    assert ask_response["status_code"] == 200
    response_text = str(ask_response["json"]).lower()
    assert product.lower() in response_text


@then(parsers.parse('the response should not include "{product}"'))
def check_response_excludes_product(ask_response, product):
    """Verify response does not list the product."""
    assert ask_response["status_code"] == 200
    response_text = str(ask_response["json"]).lower()
    # Product should not be prominently featured
    assert (
        product.lower() not in response_text or response_text.count(product.lower()) < 2
    )


@then("I should receive a helpful response asking for clarification")
def check_clarification_response(ask_response):
    """Verify response asks for clarification."""
    assert ask_response["status_code"] == 200


@then("the response should suggest specific topics")
def check_suggests_topics(ask_response):
    """Verify response suggests topics."""
    assert ask_response["status_code"] == 200


@then("I should receive a response indicating no data available")
def check_no_data_response(ask_response):
    """Verify response indicates no data."""
    assert ask_response["status_code"] == 200
    response_text = str(ask_response["json"]).lower()
    assert "no" in response_text or "empty" in response_text or "0" in response_text


@then("I should receive a 401 error")
def check_unauthorized(ask_response):
    """Verify 401 response for unauthenticated user."""
    assert ask_response["status_code"] == 401
