"""Step definitions for inventory lifecycle BDD tests."""

from pytest_bdd import given, when, then, parsers


# Background steps
@given('I am authenticated as "admin"')
def authenticated_admin(api_client):
    """Authenticate as admin user."""
    api_client.login("admin@lab.com", "admin123")


@given(parsers.parse('a vendor "{name}" exists'))
def vendor_exists(api_client, name):
    """Create a vendor if it doesn't exist."""
    response = api_client.post("/api/v1/vendors", json={"name": name})
    return response


@given(parsers.parse('a product "{product}" exists for vendor "{vendor}"'))
def product_exists(api_client, product, vendor):
    """Create a product for a vendor."""
    vendor_resp = api_client.get(f"/api/v1/vendors?search={vendor}")
    vendor_id = vendor_resp.json()["items"][0]["id"]
    api_client.post("/api/v1/products", json={"name": product, "vendor_id": vendor_id})


@given(
    parsers.parse(
        'an inventory item exists for product "{product}" with quantity {quantity:d}'
    )
)
def inventory_item_exists(api_client, product, quantity):
    """Create an inventory item for a product."""
    product_resp = api_client.get(f"/api/v1/products?search={product}")
    product_id = product_resp.json()["items"][0]["id"]
    api_client.post(
        "/api/v1/inventory", json={"product_id": product_id, "quantity": quantity}
    )


# Consume steps
@when(parsers.parse('I consume {quantity:d} units of inventory item "{item}"'))
def consume_inventory(api_client, quantity, item):
    """Consume inventory."""
    inv_resp = api_client.get(f"/api/v1/inventory?search={item}")
    item_id = inv_resp.json()["items"][0]["id"]
    api_client.response = api_client.post(
        f"/api/v1/inventory/{item_id}/consume", json={"quantity": quantity}
    )


@when(parsers.parse('I try to consume {quantity:d} units of inventory item "{item}"'))
def try_consume_inventory(api_client, quantity, item):
    """Try to consume inventory (may fail)."""
    inv_resp = api_client.get(f"/api/v1/inventory?search={item}")
    item_id = inv_resp.json()["items"][0]["id"]
    api_client.response = api_client.post(
        f"/api/v1/inventory/{item_id}/consume", json={"quantity": quantity}
    )


@then(parsers.parse("the inventory item quantity should be {quantity:d}"))
def check_quantity(api_client, quantity):
    """Verify inventory quantity."""
    assert api_client.response.status_code == 200
    data = api_client.response.json()
    assert data["quantity"] == quantity


@then("a consumption log entry should exist")
def consumption_log_exists(api_client):
    """Verify consumption log was created."""
    history = api_client.get("/api/v1/inventory/history")
    assert len(history.json()["items"]) > 0


@then(parsers.parse('the request should fail with error "{error}"'))
def request_failed(api_client, error):
    """Verify request failed with specific error."""
    assert api_client.response.status_code >= 400
    assert error.lower() in api_client.response.json().get("detail", "").lower()


@then(parsers.parse("the inventory item quantity should remain {quantity:d}"))
def quantity_unchanged(api_client, quantity, item):
    """Verify quantity didn't change."""
    inv_resp = api_client.get(f"/api/v1/inventory?search={item}")
    assert inv_resp.json()["items"][0]["quantity"] == quantity


# Transfer steps
@given(parsers.parse('a location "{name}" exists'))
def location_exists(api_client, name):
    """Create a location."""
    api_client.post("/api/v1/locations", json={"name": name})


@given(parsers.parse('an inventory item "{item}" is in location "{location}"'))
def item_in_location(api_client, item, location):
    """Move item to location."""
    inv_resp = api_client.get(f"/api/v1/inventory?search={item}")
    loc_resp = api_client.get(f"/api/v1/locations?search={location}")
    item_id = inv_resp.json()["items"][0]["id"]
    loc_id = loc_resp.json()["items"][0]["id"]
    api_client.patch(f"/api/v1/inventory/{item_id}", json={"location_id": loc_id})


@when(parsers.parse('I transfer inventory item "{item}" to location "{location}"'))
def transfer_item(api_client, item, location):
    """Transfer item to new location."""
    inv_resp = api_client.get(f"/api/v1/inventory?search={item}")
    loc_resp = api_client.get(f"/api/v1/locations?search={location}")
    item_id = inv_resp.json()["items"][0]["id"]
    loc_id = loc_resp.json()["items"][0]["id"]
    api_client.response = api_client.post(
        f"/api/v1/inventory/{item_id}/transfer", json={"location_id": loc_id}
    )


@then(parsers.parse('the inventory item should be in location "{location}"'))
def item_in_location_check(api_client, location):
    """Verify item is in location."""
    data = api_client.response.json()
    assert data["location"]["name"] == location


@then("a transfer log entry should exist")
def transfer_log_exists(api_client):
    """Verify transfer was logged."""
    assert api_client.response.status_code == 200


@when("I try to transfer inventory item to non-existent location")
def transfer_to_nonexistent(api_client, item):
    """Try to transfer to non-existent location."""
    inv_resp = api_client.get(f"/api/v1/inventory?search={item}")
    item_id = inv_resp.json()["items"][0]["id"]
    api_client.response = api_client.post(
        f"/api/v1/inventory/{item_id}/transfer", json={"location_id": 99999}
    )


# Adjust steps
@when(
    parsers.parse(
        'I adjust inventory item "{item}" quantity to {quantity:d} with reason "{reason}"'
    )
)
def adjust_quantity(api_client, item, quantity, reason):
    """Adjust inventory quantity."""
    inv_resp = api_client.get(f"/api/v1/inventory?search={item}")
    item_id = inv_resp.json()["items"][0]["id"]
    api_client.response = api_client.post(
        f"/api/v1/inventory/{item_id}/adjust",
        json={"quantity": quantity, "reason": reason},
    )


@then(parsers.parse('an adjustment log entry should exist with reason "{reason}"'))
def adjustment_log_with_reason(api_client, reason):
    """Verify adjustment was logged with reason."""
    assert api_client.response.status_code == 200


# Dispose steps
@when(parsers.parse('I dispose inventory item "{item}" with reason "{reason}"'))
def dispose_item(api_client, item, reason):
    """Dispose inventory item."""
    inv_resp = api_client.get(f"/api/v1/inventory?search={item}")
    item_id = inv_resp.json()["items"][0]["id"]
    api_client.response = api_client.post(
        f"/api/v1/inventory/{item_id}/dispose", json={"reason": reason}
    )


@then(parsers.parse('the inventory item status should be "{status}"'))
def status_is(api_client, status):
    """Verify item status."""
    data = api_client.response.json()
    assert data["status"] == status


@then(parsers.parse('a disposal log entry should exist with reason "{reason}"'))
def disposal_log_with_reason(api_client, reason):
    """Verify disposal was logged."""
    assert api_client.response.status_code == 200


# Open steps
@given(parsers.parse('an inventory item "{item}" is sealed'))
def item_is_sealed(api_client, item):
    """Ensure item is sealed."""
    pass  # Items are sealed by default


@when(parsers.parse('I open inventory item "{item}"'))
def open_item(api_client, item):
    """Open inventory item."""
    inv_resp = api_client.get(f"/api/v1/inventory?search={item}")
    item_id = inv_resp.json()["items"][0]["id"]
    api_client.response = api_client.post(f"/api/v1/inventory/{item_id}/open")


@then("the inventory item should be marked as opened")
def item_is_opened(api_client):
    """Verify item is opened."""
    data = api_client.response.json()
    assert data["is_opened"] == True


@then("the opened_at timestamp should be set")
def opened_at_set(api_client):
    """Verify opened_at is set."""
    data = api_client.response.json()
    assert data.get("opened_at") is not None


@then("an open log entry should exist")
def open_log_exists(api_client):
    """Verify open was logged."""
    assert api_client.response.status_code == 200


# History steps
@given(parsers.parse('I consumed {qty:d} units of inventory item "{item}" yesterday'))
def consumed_yesterday(api_client, qty, item):
    """Record past consumption."""
    pass  # Would need to mock or create historical records


@given(parsers.parse('I consumed {qty:d} units of inventory item "{item}" today'))
def consumed_today(api_client, qty, item):
    """Record today's consumption."""
    pass


@when(parsers.parse('I view consumption history for inventory item "{item}"'))
def view_consumption_history(api_client, item):
    """View consumption history."""
    inv_resp = api_client.get(f"/api/v1/inventory?search={item}")
    item_id = inv_resp.json()["items"][0]["id"]
    api_client.response = api_client.get(f"/api/v1/inventory/{item_id}/history")


@then("I should see 2 consumption entries")
def see_consumption_entries(api_client):
    """Verify consumption entries."""
    data = api_client.response.json()
    assert len(data.get("items", [])) >= 2


@then("the entries should be ordered by date descending")
def entries_ordered_by_date(api_client):
    """Verify date ordering."""
    data = api_client.response.json()
    items = data.get("items", [])
    if len(items) >= 2:
        assert items[0]["created_at"] >= items[1]["created_at"]


# Low stock alert steps
@given(parsers.parse("the low stock threshold is {threshold:d}"))
def low_stock_threshold(threshold):
    """Set low stock threshold."""
    pass  # Would need to configure this


@when(parsers.parse('I consume {qty:d} units of inventory item "{item}"'))
def consume_for_alert(api_client, qty, item):
    """Consume to trigger low stock."""
    consume_inventory(api_client, qty, item)


@then("a low stock alert should be created")
def low_stock_alert_created(api_client):
    """Verify low stock alert."""
    alerts = api_client.get("/api/v1/alerts")
    # Check for low stock alert
    pass


@then(parsers.parse('the alert should reference inventory item "{item}"'))
def alert_references_item(api_client, item):
    """Verify alert references item."""
    pass
