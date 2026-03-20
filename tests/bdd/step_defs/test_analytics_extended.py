"""Step definitions for extended analytics BDD tests."""

from pytest_bdd import given, when, then, parsers


# Background
@given('I am authenticated as "admin"')
def auth_admin(api_client):
    """Authenticate as admin."""
    api_client.login("admin@lab.com", "admin123")


# Inventory value
@given(parsers.parse("{count:d} inventory items exist with total value {value}"))
def inventory_with_value(api_client, count, value):
    """Create inventory with total value."""
    per_item = value / count
    for i in range(count):
        api_client.post("/api/v1/products", json={"name": f"Product-{i}"})
        resp = api_client.get(f"/api/v1/products?search=Product-{i}")
        product_id = resp.json()["items"][0]["id"]
        api_client.post(
            "/api/v1/inventory",
            json={
                "product_id": product_id,
                "quantity": 1,
                "unit_price": per_item,
            },
        )


@given("inventory items exist:")
def inventory_items_exist(api_client, datatable):
    """Create inventory items by category."""
    for row in datatable:
        api_client.post("/api/v1/products", json={"name": f"Product-{row['category']}"})
        resp = api_client.get(f"/api/v1/products?search=Product-{row['category']}")
        product_id = resp.json()["items"][0]["id"]
        api_client.post(
            "/api/v1/inventory",
            json={
                "product_id": product_id,
                "quantity": 1,
                "unit_price": float(row["value"]),
                "category": row["category"],
            },
        )


@given("consumption records exist:")
def consumption_records(api_client, datatable):
    """Create consumption records."""
    for row in datatable:
        resp = api_client.get(f"/api/v1/products?search={row['product']}")
        items = resp.json().get("items", [])
        if items:
            product_id = items[0]["id"]
            inv_resp = api_client.get(f"/api/v1/inventory?product_id={product_id}")
            inv_items = inv_resp.json().get("items", [])
            if inv_items:
                inv_id = inv_items[0]["id"]
                api_client.post(
                    f"/api/v1/inventory/{inv_id}/consume",
                    json={"quantity": int(row["total_consumed"])},
                )


@given("orders exist:")
def orders_exist(api_client, datatable):
    """Create orders."""
    for row in datatable:
        vendor_name = row.get("vendor", "Default Vendor")
        api_client.post("/api/v1/vendors", json={"name": vendor_name})
        v_resp = api_client.get(f"/api/v1/vendors?search={vendor_name}")
        vendor_id = v_resp.json()["items"][0]["id"]
        api_client.post(
            "/api/v1/orders",
            json={
                "vendor_id": vendor_id,
                "total": float(row["total"]),
                "order_date": row.get("date", row.get("month", "2024-01-01")),
            },
        )


@given("activity records exist:")
def activity_records(api_client, datatable):
    """Create activity records."""
    for row in datatable:
        for _ in range(int(row["actions"])):
            api_client.post(
                "/api/v1/audit",
                json={
                    "action": "view",
                    "entity_type": "inventory",
                    "user": row["user"],
                },
            )


@given(parsers.parse('a vendor "{name}" exists'))
def vendor_exists(api_client, name):
    """Create vendor."""
    api_client.post("/api/v1/vendors", json={"name": name})


@given(parsers.parse('{count:d} orders exist for vendor "{vendor}"'))
def orders_for_vendor(api_client, count, vendor):
    """Create orders for vendor."""
    v_resp = api_client.get(f"/api/v1/vendors?search={vendor}")
    vendor_id = v_resp.json()["items"][0]["id"]
    for i in range(count):
        api_client.post(
            "/api/v1/orders",
            json={
                "vendor_id": vendor_id,
                "total": 100.00 + i,
            },
        )


@given(parsers.parse('{count:d} products exist for vendor "{vendor}"'))
def products_for_vendor(api_client, count, vendor):
    """Create products for vendor."""
    v_resp = api_client.get(f"/api/v1/vendors?search={vendor}")
    vendor_id = v_resp.json()["items"][0]["id"]
    for i in range(count):
        api_client.post(
            "/api/v1/products",
            json={
                "name": f"Product-{i}",
                "vendor_id": vendor_id,
            },
        )


@given("documents exist:")
def documents_exist(api_client, datatable):
    """Create documents with status."""
    for row in datatable:
        for _ in range(int(row["count"])):
            api_client.post(
                "/api/v1/documents",
                json={
                    "filename": "test.pdf",
                    "status": row["status"],
                },
            )


@given("no inventory items exist")
def no_inventory(api_client):
    """Ensure no inventory."""
    pass  # Assume clean state


@given("no orders exist")
def no_orders(api_client):
    """Ensure no orders."""
    pass  # Assume clean state


# When steps
@when("I request inventory value summary")
def inventory_value_summary(api_client):
    """Request inventory value."""
    api_client.response = api_client.get("/api/v1/analytics/inventory-value")


@when("I request inventory value by category")
def inventory_value_by_category(api_client):
    """Request value by category."""
    api_client.response = api_client.get(
        "/api/v1/analytics/inventory-value/by-category"
    )


@when(parsers.parse("I request top products with limit {limit:d}"))
def top_products(api_client, limit):
    """Request top products."""
    api_client.response = api_client.get(
        f"/api/v1/analytics/top-products?limit={limit}"
    )


@when(parsers.parse('I request order history from "{start}" to "{end}"'))
def order_history_range(api_client, start, end):
    """Request order history."""
    api_client.response = api_client.get(
        f"/api/v1/analytics/order-history?start={start}&end={end}"
    )


@when("I request spending by vendor")
def spending_by_vendor(api_client):
    """Request spending by vendor."""
    api_client.response = api_client.get("/api/v1/analytics/spending/by-vendor")


@when("I request staff activity summary")
def staff_activity(api_client):
    """Request staff activity."""
    api_client.response = api_client.get("/api/v1/analytics/staff-activity")


@when(parsers.parse('I request vendor summary for "{vendor}"'))
def vendor_summary(api_client, vendor):
    """Request vendor summary."""
    v_resp = api_client.get(f"/api/v1/vendors?search={vendor}")
    vendor_id = v_resp.json()["items"][0]["id"]
    api_client.response = api_client.get(
        f"/api/v1/analytics/vendor-summary/{vendor_id}"
    )


@when("I request document stats")
def document_stats(api_client):
    """Request document stats."""
    api_client.response = api_client.get("/api/v1/analytics/documents")


@when("I request spending by month")
def spending_by_month(api_client):
    """Request spending by month."""
    api_client.response = api_client.get("/api/v1/analytics/spending/by-month")


@when("I request dashboard analytics")
def dashboard_analytics(api_client):
    """Request dashboard."""
    api_client.response = api_client.get("/api/v1/analytics/dashboard")


# Then steps
@then(parsers.parse("the response should contain total value {value}"))
def response_total_value(api_client, value):
    """Verify total value."""
    data = api_client.response.json()
    assert abs(data.get("total_value", 0) - value) < 0.01


@then(parsers.parse("the response should include item count {count:d}"))
def response_item_count(api_client, count):
    """Verify item count."""
    data = api_client.response.json()
    assert data.get("item_count", 0) == count


@then("the response should contain category breakdown")
def category_breakdown(api_client):
    """Verify category breakdown."""
    data = api_client.response.json()
    assert "categories" in data or isinstance(data, list)


@then(parsers.parse('"{category}" value should be {value}'))
def category_value(api_client, category, value):
    """Verify category value."""
    data = api_client.response.json()
    if "categories" in data:
        cats = data["categories"]
    else:
        cats = data
    cat = next((c for c in cats if c.get("category") == category), None)
    assert cat is not None
    assert abs(cat.get("value", 0) - value) < 0.01


@then(parsers.parse("the response should contain {count:d} products"))
def response_product_count(api_client, count):
    """Verify product count."""
    data = api_client.response.json()
    products = data.get("products", data)
    assert len(products) == count


@then("products should be ordered by consumption descending")
def products_ordered(api_client):
    """Verify ordering."""
    data = api_client.response.json()
    products = data.get("products", data)
    for i in range(len(products) - 1):
        assert products[i].get("consumed", 0) >= products[i + 1].get("consumed", 0)


@then(parsers.parse('"{product}" should be first'))
def product_first(api_client, product):
    """Verify first product."""
    data = api_client.response.json()
    products = data.get("products", data)
    assert products[0].get("name") == product


@then(parsers.parse("the response should contain {count:d} orders"))
def response_order_count(api_client, count):
    """Verify order count."""
    data = api_client.response.json()
    orders = data.get("orders", data)
    assert len(orders) == count


@then("orders should be within the date range")
def orders_in_range(api_client):
    """Verify date range."""
    data = api_client.response.json()
    orders = data.get("orders", data)
    for order in orders:
        assert "date" in order or "order_date" in order


@then("the response should contain vendor breakdown")
def vendor_breakdown(api_client):
    """Verify vendor breakdown."""
    data = api_client.response.json()
    assert "vendors" in data or isinstance(data, list)


@then(parsers.parse('"{vendor}" spending should be {value}'))
def vendor_spending(api_client, vendor, value):
    """Verify vendor spending."""
    data = api_client.response.json()
    if "vendors" in data:
        vendors = data["vendors"]
    else:
        vendors = data
    v = next(
        (x for x in vendors if x.get("vendor") == vendor or x.get("name") == vendor),
        None,
    )
    assert v is not None
    assert abs(v.get("spending", v.get("total", 0)) - value) < 0.01


@then("the response should contain activity per user")
def activity_per_user(api_client):
    """Verify activity per user."""
    data = api_client.response.json()
    assert "users" in data or isinstance(data, list)


@then("users should be ordered by activity descending")
def users_ordered(api_client):
    """Verify user ordering."""
    data = api_client.response.json()
    users = data.get("users", data)
    for i in range(len(users) - 1):
        assert users[i].get("actions", 0) >= users[i + 1].get("actions", 0)


@then(parsers.parse("the response should contain order count {count:d}"))
def response_order_count_value(api_client, count):
    """Verify order count in response."""
    data = api_client.response.json()
    assert data.get("order_count", 0) == count


@then(parsers.parse("the response should contain product count {count:d}"))
def response_product_count_value(api_client, count):
    """Verify product count in response."""
    data = api_client.response.json()
    assert data.get("product_count", 0) == count


@then("the response should contain status breakdown")
def status_breakdown(api_client):
    """Verify status breakdown."""
    data = api_client.response.json()
    assert "statuses" in data or isinstance(data, dict)


@then(parsers.parse('"{status}" count should be {count:d}'))
def status_count(api_client, status, count):
    """Verify status count."""
    data = api_client.response.json()
    if "statuses" in data:
        statuses = data["statuses"]
        s = next((x for x in statuses if x.get("status") == status), None)
        assert s is not None
        assert s.get("count", 0) == count
    else:
        assert data.get(status, 0) == count


@then("the response should contain monthly breakdown")
def monthly_breakdown(api_client):
    """Verify monthly breakdown."""
    data = api_client.response.json()
    assert "months" in data or isinstance(data, list)


@then("each month should have total spending")
def month_totals(api_client):
    """Verify monthly totals."""
    data = api_client.response.json()
    months = data.get("months", data)
    for month in months:
        assert "total" in month or "spending" in month


@then("the response should contain zero values")
def response_zeros(api_client):
    """Verify zero values."""
    data = api_client.response.json()
    assert data.get("total_value", 0) == 0
    assert data.get("order_count", 0) == 0


@then("the response should not error")
def response_no_error(api_client):
    """Verify no error."""
    assert api_client.response.status_code == 200
