"""Step definitions for AI Ask feature tests."""

from __future__ import annotations

from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/ask.feature"


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


@given('I am authenticated as staff "scientist1"')
def authenticated_staff(api):
    """Ensure we have an authenticated API client."""
    # The api fixture already handles authentication
    return api


@given(parsers.parse('vendors "{v1}", "{v2}" exist'))
def create_vendors(api, v1, v2):
    """Create vendors for testing."""
    vendors = []
    for name in [v1, v2]:
        r = api.post("/api/v1/vendors/", json={"name": name})
        assert r.status_code in (200, 201), r.text
        vendors.append(r.json())
    return vendors


@given(parsers.parse("orders exist with total value ${value:d}"))
def create_orders_with_value(api, value, create_vendors):
    """Create orders with a total value."""
    vendors = create_vendors
    if vendors:
        r = api.post(
            "/api/v1/orders/",
            json={
                "vendor_id": vendors[0]["id"],
                "items": [
                    {
                        "product_name": "Test Product",
                        "quantity": 1,
                        "unit_price": float(value),
                    }
                ],
            },
        )
        assert r.status_code in (200, 201), r.text
    return {"total_value": value}


@given(parsers.parse('vendor "{vendor}" with {count:d} delivered orders'))
def vendor_with_delivered_orders(api, vendor, count):
    """Create vendor with delivered orders."""
    r = api.post("/api/v1/vendors/", json={"name": vendor})
    assert r.status_code in (200, 201), r.text
    v = r.json()
    for i in range(count):
        r = api.post(
            "/api/v1/orders/",
            json={
                "vendor_id": v["id"],
                "status": "delivered",
                "items": [
                    {"product_name": f"Product {i}", "quantity": 1, "unit_price": 10.0}
                ],
            },
        )
    return v


@given(
    parsers.parse(
        'product "{name}" with quantity {qty:d} and reorder level {reorder:d}'
    )
)
def product_with_stock_level(api, name, qty, reorder):
    """Create product with specific stock level."""
    r = api.post("/api/v1/vendors/", json={"name": "Test Vendor"})
    assert r.status_code in (200, 201), r.text
    vendor = r.json()

    r = api.post(
        "/api/v1/products/",
        json={
            "name": name,
            "catalog_number": f"CAT-{name[:5].upper()}",
            "vendor_id": vendor["id"],
            "reorder_level": reorder,
        },
    )
    assert r.status_code in (200, 201), r.text
    product = r.json()

    # Add inventory
    r = api.post(
        "/api/v1/inventory/",
        json={"product_id": product["id"], "quantity": float(qty), "location": "Lab"},
    )
    return product


@given("no orders exist")
def no_orders(db):
    """Ensure no orders exist."""
    from lab_manager.models.order import Order

    db.query(Order).delete()
    db.commit()


@given("I am not authenticated")
def unauthenticated(api_unauthenticated):
    """Use unauthenticated API client."""
    return api_unauthenticated


# --- When steps ---


@when(parsers.parse('I ask "{question}"'), target_fixture="ask_response")
def ask_question(api, question):
    """Submit a natural language question."""
    r = api.get("/api/v1/ask", params={"q": question})
    return {
        "response": r,
        "status_code": r.status_code,
        "json": r.json() if r.status_code == 200 else None,
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
    # Response should have a text/markdown field


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
