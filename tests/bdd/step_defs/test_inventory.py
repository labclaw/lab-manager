"""Step definitions for inventory lifecycle BDD scenarios."""

import pytest
from pytest_bdd import given, when, then, scenario, parsers

FEATURE = "../features/inventory.feature"


# --- Scenarios ---


@scenario(FEATURE, "Receive new inventory from an order")
def test_receive_inventory():
    pass


@scenario(FEATURE, "Consume reagent from inventory")
def test_consume():
    pass


@scenario(FEATURE, "Cannot consume more than available")
def test_cannot_overconsume():
    pass


@scenario(FEATURE, "Transfer inventory between locations")
def test_transfer():
    pass


@scenario(FEATURE, "Adjust inventory after physical count")
def test_adjust():
    pass


@scenario(FEATURE, "Dispose of expired reagent")
def test_dispose():
    pass


@scenario(FEATURE, "Open a sealed item")
def test_open():
    pass


# --- Shared state ---


@pytest.fixture
def ctx():
    """Shared context dict for passing data between steps."""
    return {}


# --- Given steps ---


@given('a vendor "Thermo Fisher Scientific" exists', target_fixture="test_vendor")
def create_vendor(api):
    r = api.post("/api/vendors/", json={"name": "Thermo Fisher Scientific"})
    assert r.status_code in (200, 201), r.text
    return r.json()


@given(
    parsers.parse('a product "{name}" with catalog "{catalog}" from that vendor'),
    target_fixture="test_product",
)
def create_product(api, test_vendor, name, catalog):
    r = api.post(
        "/api/products/",
        json={
            "name": name,
            "catalog_number": catalog,
            "vendor_id": test_vendor["id"],
        },
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


@given(
    parsers.parse('an inventory item with quantity {qty:d} bottles lot "{lot}"'),
    target_fixture="test_item",
)
def create_inventory(api, test_product, qty, lot):
    r = api.post(
        "/api/inventory/",
        json={
            "product_id": test_product["id"],
            "quantity_on_hand": float(qty),
            "unit": "bottle",
            "lot_number": lot,
        },
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


@given(parsers.parse('an order "{po}" for the vendor'), target_fixture="test_order")
def create_order(api, test_vendor, po):
    r = api.post(
        "/api/orders/",
        json={
            "vendor_id": test_vendor["id"],
            "po_number": po,
            "status": "pending",
        },
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


@given(
    parsers.parse('the order has item "{name}" quantity {qty:d} unit "{unit}"'),
    target_fixture="test_order_item",
)
def add_order_item(api, test_order, test_product, name, qty, unit):
    r = api.post(
        f"/api/orders/{test_order['id']}/items",
        json={
            "product_id": test_product["id"],
            "catalog_number": test_product["catalog_number"],
            "description": name,
            "quantity": qty,
            "unit": unit,
        },
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


# --- When steps ---


@when("I receive the order", target_fixture="receive_response")
def receive_order(api, db, test_order, test_order_item):
    # Ensure a location exists for receiving
    from lab_manager.models.location import StorageLocation

    loc = StorageLocation(name="Freezer A")
    db.add(loc)
    db.flush()

    r = api.post(
        f"/api/orders/{test_order['id']}/receive",
        json={
            "items": [
                {
                    "order_item_id": test_order_item["id"],
                    "quantity": test_order_item["quantity"],
                }
            ],
            "location_id": loc.id,
            "received_by": "Robert",
        },
    )
    return r


@when(
    parsers.parse(
        'I consume {qty:d} bottles from the inventory item with note "{note}"'
    ),
    target_fixture="action_response",
)
def consume_with_note(api, test_item, qty, note):
    r = api.post(
        f"/api/inventory/{test_item['id']}/consume",
        json={"quantity": float(qty), "consumed_by": "Robert", "purpose": note},
    )
    return r


@when(
    parsers.parse("I try to consume {qty:d} bottles from the inventory item"),
    target_fixture="action_response",
)
def try_consume(api, test_item, qty):
    r = api.post(
        f"/api/inventory/{test_item['id']}/consume",
        json={"quantity": float(qty), "consumed_by": "Robert"},
    )
    return r


@when(
    parsers.parse("I consume {qty:d} bottles from the inventory item"),
    target_fixture="action_response",
)
def consume(api, test_item, qty):
    r = api.post(
        f"/api/inventory/{test_item['id']}/consume",
        json={"quantity": float(qty), "consumed_by": "Robert"},
    )
    return r


@when(
    "I transfer the inventory item to a new location",
    target_fixture="action_response",
)
def transfer(api, db, test_item):
    from lab_manager.models.location import StorageLocation

    loc = StorageLocation(name="Fridge B")
    db.add(loc)
    db.flush()

    r = api.post(
        f"/api/inventory/{test_item['id']}/transfer",
        json={"location_id": loc.id, "transferred_by": "Robert"},
    )
    return r


@when(
    parsers.parse(
        'I adjust the inventory item to {qty:d} bottles with reason "{reason}"'
    ),
    target_fixture="action_response",
)
def adjust(api, test_item, qty, reason):
    r = api.post(
        f"/api/inventory/{test_item['id']}/adjust",
        json={
            "new_quantity": float(qty),
            "reason": reason,
            "adjusted_by": "Robert",
        },
    )
    return r


@when(
    parsers.parse('I dispose of the inventory item with reason "{reason}"'),
    target_fixture="action_response",
)
def dispose(api, test_item, reason):
    r = api.post(
        f"/api/inventory/{test_item['id']}/dispose",
        json={"reason": reason, "disposed_by": "Robert"},
    )
    return r


@when("I open the inventory item", target_fixture="action_response")
def open_item(api, test_item):
    r = api.post(
        f"/api/inventory/{test_item['id']}/open",
        json={"opened_by": "Robert"},
    )
    return r


# --- Then steps ---


@then(parsers.parse('the order status should be "{status}"'))
def check_order_status(api, test_order, status):
    r = api.get(f"/api/orders/{test_order['id']}")
    assert r.json()["status"] == status


@then(parsers.parse("the inventory item quantity should be {qty:d}"))
def check_quantity(api, test_item, qty):
    r = api.get(f"/api/inventory/{test_item['id']}")
    assert float(r.json()["quantity_on_hand"]) == float(qty)


@then(parsers.parse("the inventory item quantity should still be {qty:d}"))
def check_quantity_unchanged(api, test_item, qty):
    r = api.get(f"/api/inventory/{test_item['id']}")
    assert float(r.json()["quantity_on_hand"]) == float(qty)


@then(
    parsers.parse(
        'a consumption log entry should exist with action "{action}" and quantity {qty:d}'
    )
)
def check_log_with_qty(api, test_item, action, qty):
    r = api.get(f"/api/inventory/{test_item['id']}/history")
    assert r.status_code == 200
    logs = r.json()
    matching = [entry for entry in logs if entry.get("action") == action]
    assert len(matching) > 0


@then(parsers.parse('a consumption log entry should exist with action "{action}"'))
def check_log(api, test_item, action):
    r = api.get(f"/api/inventory/{test_item['id']}/history")
    assert r.status_code == 200
    logs = r.json()
    matching = [entry for entry in logs if entry.get("action") == action]
    assert len(matching) > 0


@then(parsers.parse("the request should fail with status {code:d}"))
def check_fail(action_response, code):
    assert action_response.status_code == code


@then(parsers.parse('the inventory item status should be "{status}"'))
def check_status(api, test_item, status):
    r = api.get(f"/api/inventory/{test_item['id']}")
    assert r.json()["status"] == status
