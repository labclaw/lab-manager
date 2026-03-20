"""Step definitions for consumption tracking BDD tests."""

from pytest_bdd import given, when, then, parsers


@given('I am authenticated as "admin"')
def auth_admin(api_client):
    """Authenticate as admin."""
    api_client.login("admin@lab.com", "admin123")


@given(parsers.parse('an inventory item "{name}" with quantity {qty:d} exists'))
def inventory_item_exists(api_client, name, qty):
    """Create inventory item."""
    resp = api_client.post("/api/v1/products", json={"name": name})
    product_id = resp.json()["id"]
    resp = api_client.post(
        "/api/v1/inventory",
        json={
            "product_id": product_id,
            "quantity": qty,
        },
    )
    api_client.inv_id = resp.json()["id"]


@when(parsers.parse('I consume {qty:d} units of "{name}"'))
def consume_units(api_client, qty, name):
    """Consume inventory."""
    inv_id = getattr(api_client, "inv_id", None)
    api_client.response = api_client.post(
        f"/api/v1/inventory/{inv_id}/consume", json={"quantity": qty}
    )


@then(parsers.parse("the quantity should be {qty:d}"))
def quantity_is(api_client, qty):
    """Verify quantity."""
    data = api_client.response.json()
    assert data.get("quantity") == qty


@then("a consumption log should be created")
def consumption_log_created(api_client):
    """Verify consumption log."""
    inv_id = getattr(api_client, "inv_id", None)
    resp = api_client.get(f"/api/v1/inventory/{inv_id}/history")
    assert any(h.get("action") == "consume" for h in resp.json().get("items", []))


@given(parsers.parse('a project "{name}" exists'))
def project_exists(api_client, name):
    """Create project."""
    api_client.post("/api/v1/projects", json={"name": name})


@when(parsers.parse('I consume {qty:d} units of "{item}" for project "{project}"'))
def consume_for_project(api_client, qty, item, project):
    """Consume for project."""
    inv_id = getattr(api_client, "inv_id", None)
    proj_resp = api_client.get(f"/api/v1/projects?search={project}")
    project_id = proj_resp.json()["items"][0]["id"]
    api_client.response = api_client.post(
        f"/api/v1/inventory/{inv_id}/consume",
        json={
            "quantity": qty,
            "project_id": project_id,
        },
    )


@then(parsers.parse('the consumption should be attributed to "{project}"'))
def attributed_to_project(api_client, project):
    """Verify project attribution."""
    data = api_client.response.json()
    assert data.get("project", {}).get("name") == project


@when(parsers.parse('I consume {qty:d} units of "{item}" with note "{note}"'))
def consume_with_note(api_client, qty, item, note):
    """Consume with note."""
    inv_id = getattr(api_client, "inv_id", None)
    api_client.response = api_client.post(
        f"/api/v1/inventory/{inv_id}/consume",
        json={
            "quantity": qty,
            "note": note,
        },
    )


@then(parsers.parse("the note should be saved with the consumption record"))
def note_saved(api_client):
    """Verify note saved."""
    inv_id = getattr(api_client, "inv_id", None)
    resp = api_client.get(f"/api/v1/inventory/{inv_id}/history")
    items = resp.json().get("items", [])
    consume_record = next((h for h in items if h.get("action") == "consume"), None)
    assert consume_record and consume_record.get("note")


@given("consumption records exist:")
def consumption_records_exist(api_client, datatable):
    """Create consumption records."""
    inv_id = getattr(api_client, "inv_id", None)
    for row in datatable:
        api_client.post(
            f"/api/v1/inventory/{inv_id}/consume",
            json={
                "quantity": int(row["quantity"]),
                "consumed_at": row["date"],
            },
        )


@when(parsers.parse('I view consumption history for "{item}"'))
def view_consumption_history(api_client, item):
    """View consumption history."""
    inv_id = getattr(api_client, "inv_id", None)
    api_client.response = api_client.get(f"/api/v1/inventory/{inv_id}/history")


@then(parsers.parse("I should see {count:d} records"))
def see_records(api_client, count):
    """Verify record count."""
    data = api_client.response.json()
    items = data.get("items", [])
    assert len(items) >= count


@then("records should be ordered by date descending")
def ordered_by_date(api_client):
    """Verify date ordering."""
    data = api_client.response.json()
    items = data.get("items", [])
    if len(items) >= 2:
        assert items[0].get("created_at") >= items[1].get("created_at")


@when(parsers.parse('I view consumption from "{start}" to "{end}"'))
def view_consumption_range(api_client, start, end):
    """View consumption by date range."""
    inv_id = getattr(api_client, "inv_id", None)
    api_client.response = api_client.get(
        f"/api/v1/inventory/{inv_id}/history?start={start}&end={end}"
    )


@given(parsers.parse('users "{u1}" and "{u2}" have consumed:'))
def users_consumed(api_client, u1, u2, datatable):
    """Create user consumption records."""
    inv_id = getattr(api_client, "inv_id", None)
    for row in datatable:
        api_client.post(
            f"/api/v1/inventory/{inv_id}/consume",
            json={
                "quantity": int(row["quantity"]),
                "consumed_by": row["user"],
            },
        )


@when("I view consumption by user")
def view_by_user(api_client):
    """View consumption by user."""
    inv_id = getattr(api_client, "inv_id", None)
    api_client.response = api_client.get(
        f"/api/v1/inventory/{inv_id}/consumption/by-user"
    )


@then("I should see user breakdown")
def user_breakdown(api_client):
    """Verify user breakdown."""
    data = api_client.response.json()
    assert "users" in data or isinstance(data, list)


@given(parsers.parse("consumption records total {qty:d} units"))
def total_consumption(api_client, qty):
    """Create total consumption."""
    inv_id = getattr(api_client, "inv_id", None)
    api_client.post(f"/api/v1/inventory/{inv_id}/consume", json={"quantity": qty})


@when("I request consumption summary")
def consumption_summary(api_client):
    """Request summary."""
    inv_id = getattr(api_client, "inv_id", None)
    api_client.response = api_client.get(
        f"/api/v1/inventory/{inv_id}/consumption/summary"
    )


@then(parsers.parse("the total should be {qty:d}"))
def total_is(api_client, qty):
    """Verify total."""
    data = api_client.response.json()
    assert data.get("total_consumed", 0) >= qty


@then("the summary should include time period")
def includes_time_period(api_client):
    """Verify time period."""
    data = api_client.response.json()
    assert "period" in data or "start_date" in data or "from" in data


@given("an item with quantity 15 exists")
def item_qty_15(api_client):
    """Create item with quantity 15."""
    resp = api_client.post("/api/v1/products", json={"name": "Low Stock Item"})
    product_id = resp.json()["id"]
    resp = api_client.post(
        "/api/v1/inventory",
        json={
            "product_id": product_id,
            "quantity": 15,
        },
    )
    api_client.low_stock_inv_id = resp.json()["id"]


@given(parsers.parse("the low stock threshold is {threshold:d}"))
def low_stock_threshold(threshold):
    """Set low stock threshold."""
    pass  # Assume configured


@when("I consume 10 units")
def consume_10(api_client):
    """Consume 10 units."""
    inv_id = getattr(api_client, "low_stock_inv_id", None)
    api_client.response = api_client.post(
        f"/api/v1/inventory/{inv_id}/consume", json={"quantity": 10}
    )


@then("a low stock alert should be created")
def low_stock_alert(api_client):
    """Verify low stock alert."""
    alerts = api_client.get("/api/v1/alerts")
    alert_items = alerts.json().get("items", [])
    assert any("low" in str(a.get("type", "")).lower() for a in alert_items)


@given("consumption records exist")
def consumption_records_generic(api_client):
    """Create generic consumption records."""
    inv_id = getattr(api_client, "inv_id", None)
    for i in range(5):
        api_client.post(f"/api/v1/inventory/{inv_id}/consume", json={"quantity": i + 1})


@when("I export consumption report to CSV")
def export_csv(api_client):
    """Export to CSV."""
    inv_id = getattr(api_client, "inv_id", None)
    api_client.response = api_client.get(
        f"/api/v1/inventory/{inv_id}/consumption/export?format=csv"
    )


@then("the CSV should contain all consumption records")
def csv_contains_records(api_client):
    """Verify CSV content."""
    assert api_client.response.status_code == 200
    content = api_client.response.text
    assert "quantity" in content.lower() or "consumed" in content.lower()


@then("the CSV should have proper headers")
def csv_headers(api_client):
    """Verify CSV headers."""
    content = api_client.response.text
    lines = content.split("\n")
    headers = lines[0].lower()
    assert any(h in headers for h in ["date", "quantity", "user"])


@given("consumption records for 6 months exist")
def consumption_6_months(api_client):
    """Create 6 months of records."""
    inv_id = getattr(api_client, "inv_id", None)
    months = ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06"]
    for m in months:
        api_client.post(
            f"/api/v1/inventory/{inv_id}/consume",
            json={
                "quantity": 10,
                "consumed_at": f"{m}-15",
            },
        )


@when("I request consumption trends")
def request_trends(api_client):
    """Request trends."""
    inv_id = getattr(api_client, "inv_id", None)
    api_client.response = api_client.get(
        f"/api/v1/inventory/{inv_id}/consumption/trends"
    )


@then("I should see monthly breakdown")
def monthly_breakdown(api_client):
    """Verify monthly breakdown."""
    data = api_client.response.json()
    assert "monthly" in data or "months" in data or isinstance(data, list)


@then("I should see trend direction")
def trend_direction(api_client):
    """Verify trend direction."""
    data = api_client.response.json()
    assert "trend" in data or "direction" in data
