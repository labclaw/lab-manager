"""Step definitions for order receiving BDD tests."""

from pytest_bdd import given, when, then, parsers


# Background steps
@given('I am authenticated as "admin"')
def auth_admin(api_client):
    """Authenticate as admin."""
    api_client.login("admin@lab.com", "admin123")


@given(parsers.parse('a vendor "{name}" exists'))
def vendor_exists(api_client, name):
    """Create vendor if needed."""
    api_client.post("/api/v1/vendors", json={"name": name})


@given(parsers.parse('a product "{product}" exists for vendor "{vendor}"'))
def product_for_vendor(api_client, product, vendor):
    """Create product for vendor."""
    vendor_resp = api_client.get(f"/api/v1/vendors?search={vendor}")
    vendor_id = vendor_resp.json()["items"][0]["id"]
    api_client.post("/api/v1/products", json={"name": product, "vendor_id": vendor_id})


@given(parsers.parse('an order exists with status "{status}"'))
def order_with_status(api_client, status):
    """Create order with status."""
    vendor_resp = api_client.get("/api/v1/vendors")
    vendor_id = vendor_resp.json()["items"][0]["id"]
    resp = api_client.post(
        "/api/v1/orders",
        json={
            "vendor_id": vendor_id,
            "status": status,
        },
    )
    api_client.order_id = resp.json()["id"]


@given("the order contains:")
def order_contains(api_client, datatable):
    """Add items to order."""
    order_id = getattr(api_client, "order_id", None)
    if not order_id:
        raise AssertionError("No order created")

    for row in datatable:
        product_resp = api_client.get(f"/api/v1/products?search={row['product']}")
        product_id = product_resp.json()["items"][0]["id"]

        item_data = {"product_id": product_id, "quantity": row["quantity"]}
        if "lot_number" in row:
            item_data["lot_number"] = row["lot_number"]
        if "unit_price" in row:
            item_data["unit_price"] = float(row["unit_price"])
        if "expiration_date" in row:
            item_data["expiration_date"] = row["expiration_date"]

        api_client.post(f"/api/v1/orders/{order_id}/items", json=item_data)


# When steps
@when("I receive the order")
def receive_order(api_client):
    """Receive the order."""
    order_id = getattr(api_client, "order_id", None)
    api_client.response = api_client.post(f"/api/v1/orders/{order_id}/receive")


@when("I try to receive the order")
def try_receive_order(api_client):
    """Try to receive order (may fail)."""
    order_id = getattr(api_client, "order_id", None)
    api_client.response = api_client.post(f"/api/v1/orders/{order_id}/receive")


@when("I partially receive the order with:")
def partial_receive(api_client, datatable):
    """Partially receive order."""
    order_id = getattr(api_client, "order_id", None)
    items = []
    for row in datatable:
        product_resp = api_client.get(f"/api/v1/products?search={row['product']}")
        product_id = product_resp.json()["items"][0]["id"]
        items.append(
            {
                "product_id": product_id,
                "received_quantity": int(row["received_quantity"]),
            }
        )

    api_client.response = api_client.post(
        f"/api/v1/orders/{order_id}/receive", json={"partial": True, "items": items}
    )


@when(parsers.parse('I receive the order to location "{location}"'))
def receive_to_location(api_client, location):
    """Receive order to specific location."""
    order_id = getattr(api_client, "order_id", None)
    loc_resp = api_client.get(f"/api/v1/locations?search={location}")
    location_id = loc_resp.json()["items"][0]["id"]
    api_client.response = api_client.post(
        f"/api/v1/orders/{order_id}/receive", json={"location_id": location_id}
    )


@given(parsers.parse('a location "{name}" exists'))
def location_exists(api_client, name):
    """Create location."""
    api_client.post("/api/v1/locations", json={"name": name})


# Then steps
@then(parsers.parse('the order status should be "{status}"'))
def order_status_is(api_client, status):
    """Verify order status."""
    data = api_client.response.json()
    assert data["status"] == status


@then(parsers.parse("{count:d} inventory items should be created"))
def inventory_count_created(api_client, count):
    """Verify inventory items created."""
    data = api_client.response.json()
    created_items = data.get("created_inventory", [])
    assert len(created_items) == count


@then(parsers.parse('inventory item for "{product}" should have quantity {quantity:d}'))
def inventory_quantity_check(api_client, product, quantity):
    """Verify inventory quantity."""
    inv_resp = api_client.get(f"/api/v1/inventory?search={product}")
    items = inv_resp.json()["items"]
    assert any(item["quantity"] == quantity for item in items)


@then("inventory items should have lot numbers preserved")
def lot_numbers_preserved(api_client):
    """Verify lot numbers."""
    data = api_client.response.json()
    for item in data.get("created_inventory", []):
        assert item.get("lot_number") is not None


@then("the order should be received")
def order_received(api_client):
    """Verify order received."""
    assert api_client.response.status_code == 200
    assert api_client.response.json()["status"] == "received"


@then("inventory items should be created without lot numbers")
def inventory_no_lot(api_client):
    """Verify no lot numbers."""
    data = api_client.response.json()
    for item in data.get("created_inventory", []):
        assert item.get("lot_number") is None


@then(parsers.parse('the request should fail with error "{error}"'))
def request_failed_with_error(api_client, error):
    """Verify request failed."""
    assert api_client.response.status_code >= 400
    assert error.lower() in api_client.response.json().get("detail", "").lower()


@then(parsers.parse("the total inventory value should increase by {amount:Float}"))
def inventory_value_increased(api_client, amount):
    """Verify inventory value increase."""
    data = api_client.response.json()
    assert data.get("value_added", 0) == amount


@then(parsers.parse("{count:d} order item should remain pending"))
def order_items_pending(api_client, count):
    """Verify pending items."""
    data = api_client.response.json()
    pending = sum(
        1 for item in data.get("items", []) if item.get("status") == "pending"
    )
    assert pending == count


@then(parsers.parse('the inventory item should be in location "{location}"'))
def inventory_in_location(api_client, location):
    """Verify inventory location."""
    data = api_client.response.json()
    created = data.get("created_inventory", [])
    assert any(item.get("location", {}).get("name") == location for item in created)


@then(parsers.parse('the inventory item should have expiration date "{date}"'))
def inventory_expiration_date(api_client, date):
    """Verify expiration date."""
    data = api_client.response.json()
    created = data.get("created_inventory", [])
    assert any(item.get("expiration_date") == date for item in created)


@then("an expiring soon alert should be created")
def expiring_alert_created(api_client):
    """Verify expiring alert."""
    alerts = api_client.get("/api/v1/alerts")
    alert_types = [a.get("type") for a in alerts.json().get("items", [])]
    assert "expiring_soon" in alert_types


@then("the alert should reference the inventory item")
def alert_references_inventory(api_client):
    """Verify alert references inventory."""
    alerts = api_client.get("/api/v1/alerts")
    for alert in alerts.json().get("items", []):
        if alert.get("type") == "expiring_soon":
            assert alert.get("inventory_id") is not None
            return
    raise AssertionError("No expiring_soon alert found")
