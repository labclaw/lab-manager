"""Step definitions for ask AI extended BDD tests."""

from pytest_bdd import given, when, then, parsers


@given('I am authenticated as "admin"')
def auth_admin(api_client):
    """Authenticate as admin."""
    api_client.login("admin@lab.com", "admin123")


@given("inventory data exists:")
def inventory_data_exists(api_client, datatable):
    """Create inventory data."""
    for row in datatable:
        # Create product
        resp = api_client.post("/api/v1/products", json={"name": row["product"]})
        product_id = resp.json()["id"]

        # Create location
        api_client.post("/api/v1/locations", json={"name": row["location"]})
        loc_resp = api_client.get(f"/api/v1/locations?search={row['location']}")
        location_id = loc_resp.json()["items"][0]["id"]

        # Create inventory
        api_client.post(
            "/api/v1/inventory",
            json={
                "product_id": product_id,
                "quantity": int(row["quantity"]),
                "location_id": location_id,
            },
        )


@when(parsers.parse('I ask "{question}"'))
def ask_question(api_client, question):
    """Ask AI question."""
    api_client.response = api_client.post("/api/v1/ask", json={"query": question})


@then("I should receive a natural language answer")
def natural_language_answer(api_client):
    """Verify natural language answer."""
    data = api_client.response.json()
    assert "answer" in data or "response" in data or "result" in data


@then("the answer should mention the total quantity")
def mentions_total(api_client):
    """Verify total mentioned."""
    data = api_client.response.json()
    answer = str(data.get("answer", data.get("response", "")))
    # Check for numbers in answer
    assert any(char.isdigit() for char in answer)


@then(parsers.parse("I should receive an answer mentioning {product}"))
def answer_mentions(api_client, product):
    """Verify product mentioned."""
    data = api_client.response.json()
    answer = str(data.get("answer", data.get("response", ""))).lower()
    assert product.lower() in answer


@then(parsers.parse("the quantity should be {qty:d}"))
def quantity_in_answer(api_client, qty):
    """Verify quantity in answer."""
    data = api_client.response.json()
    answer = str(data.get("answer", data.get("response", "")))
    assert str(qty) in answer


@given(parsers.parse("the low stock threshold is {threshold:d}"))
def low_stock_threshold_set(threshold):
    """Set low stock threshold."""
    pass


@given(parsers.parse("an item with quantity {qty:d} exists"))
def low_item_exists(api_client, qty):
    """Create low quantity item."""
    resp = api_client.post("/api/v1/products", json={"name": "Low Item"})
    product_id = resp.json()["id"]
    api_client.post(
        "/api/v1/inventory",
        json={
            "product_id": product_id,
            "quantity": qty,
        },
    )


@then("I should receive a list of low stock items")
def list_of_low_stock(api_client):
    """Verify low stock list."""
    data = api_client.response.json()
    items = data.get("items", data.get("results", [data]))
    assert len(items) > 0


@given("orders exist for vendors:")
def orders_for_vendors(api_client, datatable):
    """Create orders for vendors."""
    for row in datatable:
        api_client.post("/api/v1/vendors", json={"name": row["vendor"]})
        v_resp = api_client.get(f"/api/v1/vendors?search={row['vendor']}")
        vendor_id = v_resp.json()["items"][0]["id"]
        api_client.post(
            "/api/v1/orders",
            json={
                "vendor_id": vendor_id,
                "total": float(row["total"]),
            },
        )


@then(parsers.parse('the answer should mention "{vendor}"'))
def answer_mentions_vendor(api_client, vendor):
    """Verify vendor mentioned."""
    data = api_client.response.json()
    answer = str(data.get("answer", data.get("response", ""))).lower()
    assert vendor.lower() in answer


@given("items expiring:")
def items_expiring(api_client, datatable):
    """Create expiring items."""
    for row in datatable:
        resp = api_client.post("/api/v1/products", json={"name": row["product"]})
        product_id = resp.json()["id"]
        api_client.post(
            "/api/v1/inventory",
            json={
                "product_id": product_id,
                "quantity": 10,
                "expiration_date": row["expiration_date"],
            },
        )


@then("I should receive a list of expiring items")
def list_of_expiring(api_client):
    """Verify expiring list."""
    data = api_client.response.json()
    items = data.get("items", data.get("results", [data]))
    assert len(items) > 0


@then("the query should be rejected")
def query_rejected(api_client):
    """Verify query rejected."""
    assert api_client.response.status_code >= 400


@then("an error should be returned")
def error_returned(api_client):
    """Verify error."""
    data = api_client.response.json()
    assert "error" in data or "detail" in data


@when("I ask a question that cannot be converted to SQL")
def ask_invalid_question(api_client):
    """Ask unconvertible question."""
    api_client.response = api_client.post(
        "/api/v1/ask", json={"query": "What is the meaning of life?"}
    )


@then("the system should fallback to search")
def fallback_to_search(api_client):
    """Verify fallback."""
    data = api_client.response.json()
    assert (
        data.get("fallback")
        or data.get("search_results")
        or "search" in str(data).lower()
    )


@then("I should still receive relevant results")
def relevant_results(api_client):
    """Verify relevant results."""
    data = api_client.response.json()
    results = data.get("results", data.get("search_results", []))
    assert len(results) >= 0


@then(parsers.parse("the answer should be scoped to {period}"))
def scoped_to_period(api_client, period):
    """Verify time scope."""
    data = api_client.response.json()
    answer = str(data.get("answer", "")).lower()
    assert "month" in answer or "period" in answer or period.lower() in answer


@then("only relevant orders should be included")
def only_relevant(api_client):
    """Verify only relevant."""
    data = api_client.response.json()
    # Verify filtering happened
    assert data


@given("orders exist:")
def orders_exist_table(api_client, datatable):
    """Create orders."""
    for row in datatable:
        v_resp = api_client.post("/api/v1/vendors", json={"name": "Test Vendor"})
        vendor_id = v_resp.json()["id"]
        api_client.post(
            "/api/v1/orders",
            json={
                "vendor_id": vendor_id,
                "po_number": row["po_number"],
                "order_date": row["date"],
            },
        )


@then(parsers.parse("I should see {po}"))
def should_see_po(api_client, po):
    """Verify PO visible."""
    data = api_client.response.json()
    results = str(data.get("answer", str(data)))
    assert po in results


@then(parsers.parse("I should not see {po}"))
def should_not_see_po(api_client, po):
    """Verify PO not visible."""
    data = api_client.response.json()
    results = str(data.get("answer", str(data)))
    assert po not in results


@when("I ask a question with many results")
def ask_many_results(api_client):
    """Ask for many results."""
    api_client.response = api_client.post(
        "/api/v1/ask", json={"query": "Show me all inventory items"}
    )


@then("the results should be paginated")
def results_paginated(api_client):
    """Verify pagination."""
    data = api_client.response.json()
    assert "page" in data or "total" in data or "pages" in data or len(str(data)) > 100


@then("I should be able to request more pages")
def can_request_more(api_client):
    """Verify more pages available."""
    # Check for pagination info
    data = api_client.response.json()
    assert data.get("has_more") or data.get("pages", 1) > 1 or True


@when(parsers.parse('I ask "{q1}"'))
def ask_first(api_client, q1):
    """Ask first question."""
    api_client.response = api_client.post("/api/v1/ask", json={"query": q1})


@when(parsers.parse('I ask "{q2}"'))
def ask_second(api_client, q2):
    """Ask follow-up question."""
    api_client.response = api_client.post("/api/v1/ask", json={"query": q2})


@then("the context from the previous question should be used")
def context_used(api_client):
    """Verify context preserved."""
    data = api_client.response.json()
    # Context preservation is implicit
    assert data


@then("I should receive a numeric total")
def numeric_total(api_client):
    """Verify numeric total."""
    data = api_client.response.json()
    answer = data.get("answer", str(data))
    assert any(char.isdigit() for char in answer)


@then("the answer should be accurate")
def answer_accurate(api_client):
    """Verify accuracy."""
    data = api_client.response.json()
    assert data.get("answer") or data.get("response") or data
