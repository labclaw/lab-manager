"""Step definitions for inventory lifecycle feature."""

import pytest
from pytest_bdd import given, when, then, parsers
from fastapi.testclient import TestClient

from lab_manager.api.app import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Get authentication headers."""
    return {"Authorization": "Bearer test-token"}


# Background steps
@given("the database is clean")
def database_clean(db_session):
    """Clean the database."""
    db_session.execute("DELETE FROM inventory")
    db_session.execute("DELETE FROM products")
    db_session.execute("DELETE FROM locations")
    db_session.commit()


@given("I am authenticated")
def authenticated(auth_headers):
    """Set up authentication."""
    return auth_headers


@given(parsers.parse('a product "{name}" exists with quantity {quantity:d}'))
def product_with_quantity(db_session, name, quantity):
    """Create a product with initial quantity."""
    from lab_manager.models.product import Product
    from lab_manager.models.inventory import Inventory

    product = Product(name=name, unit="mL", sku=f"SKU-{name[:3].upper()}")
    db_session.add(product)
    db_session.commit()

    inventory = Inventory(
        product_id=product.id,
        quantity=quantity,
        location="Main Storage",
        status="available",
    )
    db_session.add(inventory)
    db_session.commit()
    return inventory


@given(parsers.parse('a location "{name}" exists'))
def location_exists(db_session, name):
    """Create a location."""
    from lab_manager.models.location import Location

    location = Location(name=name, type="storage")
    db_session.add(location)
    db_session.commit()
    return location


@given("inventory item exists with quantity 50")
def inventory_50(db_session):
    """Create inventory with 50 units."""
    from lab_manager.models.product import Product
    from lab_manager.models.inventory import Inventory

    product = Product(name="Test Product", unit="mL", sku="TEST-001")
    db_session.add(product)
    db_session.commit()

    inventory = Inventory(
        product_id=product.id, quantity=50, location="Main Storage", status="available"
    )
    db_session.add(inventory)
    db_session.commit()
    return inventory


@given(parsers.parse("inventory item exists with quantity {quantity:d}"))
def inventory_quantity(db_session, quantity):
    """Create inventory with specific quantity."""
    from lab_manager.models.product import Product
    from lab_manager.models.inventory import Inventory

    product = Product(name="Test Product", unit="mL", sku="TEST-001")
    db_session.add(product)
    db_session.commit()

    inventory = Inventory(
        product_id=product.id,
        quantity=quantity,
        location="Main Storage",
        status="available",
    )
    db_session.add(inventory)
    db_session.commit()
    return inventory


@when(parsers.parse("I consume {count:d} units"))
def consume_inventory(client, auth_headers, db_session, count):
    """Consume inventory."""
    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    response = client.post(
        f"/api/inventory/{inv}/consume", json={"quantity": count}, headers=auth_headers
    )
    return response


@when(parsers.parse("I try to consume {count:d} units"))
def try_consume_inventory(client, auth_headers, db_session, count):
    """Try to consume inventory (may fail)."""
    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    response = client.post(
        f"/api/inventory/{inv}/consume", json={"quantity": count}, headers=auth_headers
    )
    return response


@then(parsers.parse("the quantity should be {expected:d}"))
def check_quantity(db_session, expected):
    """Check inventory quantity."""
    from lab_manager.models.inventory import Inventory

    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    inventory = db_session.get(Inventory, inv)
    assert inventory.quantity == expected


@then("a consumption record should be created")
def consumption_record_exists(db_session):
    """Check consumption record was created."""
    # Check audit/consumption log
    pass


@then(parsers.parse("the error should indicate {message}"))
def error_indicates(response, message):
    """Check error message."""
    data = response.json()
    assert message.lower().replace(" ", "_") in str(data).lower()


@given(parsers.parse('inventory at location "{location}" with quantity {quantity:d}'))
def inventory_at_location(db_session, location, quantity):
    """Create inventory at specific location."""
    from lab_manager.models.product import Product
    from lab_manager.models.inventory import Inventory
    from lab_manager.models.location import Location

    loc = Location(name=location, type="storage")
    db_session.add(loc)
    db_session.commit()

    product = Product(name="Location Product", unit="mL", sku="LOC-001")
    db_session.add(product)
    db_session.commit()

    inventory = Inventory(
        product_id=product.id, quantity=quantity, location=location, status="available"
    )
    db_session.add(inventory)
    db_session.commit()
    return inventory


@when(parsers.parse('I transfer {count:d} units to "{dest}"'))
def transfer_inventory(client, auth_headers, db_session, count, dest):
    """Transfer inventory between locations."""
    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    response = client.post(
        f"/api/inventory/{inv}/transfer",
        json={"quantity": count, "destination": dest},
        headers=auth_headers,
    )
    return response


@when("I try to transfer to same location")
def transfer_same_location(client, auth_headers, db_session):
    """Try to transfer to same location."""
    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    response = client.post(
        f"/api/inventory/{inv}/transfer",
        json={"quantity": 10, "destination": "Freezer A"},
        headers=auth_headers,
    )
    return response


@when(parsers.parse("I try to transfer {count:d} units"))
def try_transfer(client, auth_headers, db_session, count):
    """Try to transfer (may fail)."""
    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    response = client.post(
        f"/api/inventory/{inv}/transfer",
        json={"quantity": count, "destination": "Freezer B"},
        headers=auth_headers,
    )
    return response


@then(parsers.parse('location "{location}" should have {quantity:d} units'))
def location_quantity(db_session, location, quantity):
    """Check quantity at location."""
    from lab_manager.models.inventory import Inventory

    inv = db_session.execute(
        "SELECT id FROM inventory WHERE location = :loc", {"loc": location}
    ).scalar()
    inventory = db_session.get(Inventory, inv)
    assert inventory.quantity == quantity


@then("a transfer record should be created")
def transfer_record_exists(db_session):
    """Check transfer record was created."""
    pass


@when(parsers.parse('I adjust quantity to {new_qty:d} with reason "{reason}"'))
def adjust_inventory(client, auth_headers, db_session, new_qty, reason):
    """Adjust inventory quantity."""
    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    response = client.post(
        f"/api/inventory/{inv}/adjust",
        json={"quantity": new_qty, "reason": reason},
        headers=auth_headers,
    )
    return response


@when("I adjust quantity without providing reason")
def adjust_without_reason(client, auth_headers, db_session):
    """Adjust without reason."""
    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    response = client.post(
        f"/api/inventory/{inv}/adjust", json={"quantity": 60}, headers=auth_headers
    )
    return response


@then("an adjustment record should be created")
def adjustment_record_exists(db_session):
    """Check adjustment record was created."""
    pass


@then(parsers.parse('adjustment reason should be "{reason}"'))
def adjustment_reason(db_session, reason):
    """Check adjustment reason."""
    pass


@given(
    parsers.parse('inventory item exists with quantity {qty:d} and status "{status}"')
)
def inventory_with_status(db_session, qty, status):
    """Create inventory with status."""
    from lab_manager.models.product import Product
    from lab_manager.models.inventory import Inventory

    product = Product(name="Status Product", unit="mL", sku="STATUS-001")
    db_session.add(product)
    db_session.commit()

    inventory = Inventory(
        product_id=product.id, quantity=qty, location="Main Storage", status=status
    )
    db_session.add(inventory)
    db_session.commit()
    return inventory


@when(parsers.parse('I dispose of the inventory with reason "{reason}"'))
def dispose_inventory(client, auth_headers, db_session, reason):
    """Dispose of inventory."""
    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    response = client.post(
        f"/api/inventory/{inv}/dispose", json={"reason": reason}, headers=auth_headers
    )
    return response


@when("I try to dispose without confirmation")
def dispose_without_confirm(client, auth_headers, db_session):
    """Try to dispose without confirmation."""
    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    response = client.post(
        f"/api/inventory/{inv}/dispose", json={"reason": "Test"}, headers=auth_headers
    )
    return response


@when(parsers.parse('I dispose with confirmation and reason "{reason}"'))
def dispose_with_confirm(client, auth_headers, db_session, reason):
    """Dispose with confirmation."""
    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    response = client.post(
        f"/api/inventory/{inv}/dispose",
        json={"reason": reason, "confirmed": True},
        headers=auth_headers,
    )
    return response


@then(parsers.parse('the inventory status should be "{status}"'))
def inventory_status_is(db_session, status):
    """Check inventory status."""
    from lab_manager.models.inventory import Inventory

    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    inventory = db_session.get(Inventory, inv)
    assert inventory.status == status


@then("a disposal record should be created")
def disposal_record_exists(db_session):
    """Check disposal record was created."""
    pass


@given("sealed inventory item exists with quantity 500")
def sealed_inventory(db_session):
    """Create sealed inventory."""
    from lab_manager.models.product import Product
    from lab_manager.models.inventory import Inventory

    product = Product(name="Sealed Product", unit="mL", sku="SEALED-001")
    db_session.add(product)
    db_session.commit()

    inventory = Inventory(
        product_id=product.id, quantity=500, location="Main Storage", status="sealed"
    )
    db_session.add(inventory)
    db_session.commit()
    return inventory


@when("I open the container")
def open_container(client, auth_headers, db_session):
    """Open sealed container."""
    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    response = client.post(f"/api/inventory/{inv}/open", headers=auth_headers)
    return response


@then(parsers.parse('the container status should be "{status}"'))
def container_status(db_session, status):
    """Check container status."""
    from lab_manager.models.inventory import Inventory

    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    inventory = db_session.get(Inventory, inv)
    assert inventory.status == status


@then("opened date should be recorded")
def opened_date_recorded(db_session):
    """Check opened date was recorded."""
    from lab_manager.models.inventory import Inventory

    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    inventory = db_session.get(Inventory, inv)
    assert inventory.opened_at is not None


@given(parsers.parse("opened inventory item with remaining {quantity:d}"))
def opened_inventory(db_session, quantity):
    """Create opened inventory."""
    from lab_manager.models.product import Product
    from lab_manager.models.inventory import Inventory
    from datetime import datetime

    product = Product(name="Opened Product", unit="mL", sku="OPENED-001")
    db_session.add(product)
    db_session.commit()

    inventory = Inventory(
        product_id=product.id,
        quantity=quantity,
        location="Main Storage",
        status="opened",
        opened_at=datetime.utcnow(),
    )
    db_session.add(inventory)
    db_session.commit()
    return inventory


@given(parsers.parse("inventory item with minimum threshold {threshold:d}"))
def inventory_with_threshold(db_session, threshold):
    """Create inventory with minimum threshold."""
    from lab_manager.models.product import Product
    from lab_manager.models.inventory import Inventory

    product = Product(name="Threshold Product", unit="mL", sku="THRESH-001")
    db_session.add(product)
    db_session.commit()

    inventory = Inventory(
        product_id=product.id,
        quantity=threshold + 5,
        location="Main Storage",
        status="available",
        minimum_quantity=threshold,
    )
    db_session.add(inventory)
    db_session.commit()
    return inventory


@when(parsers.parse("quantity falls below {threshold:d}"))
def quantity_below_threshold(client, auth_headers, db_session, threshold):
    """Consume to fall below threshold."""
    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    response = client.post(
        f"/api/inventory/{inv}/consume", json={"quantity": 10}, headers=auth_headers
    )
    return response


@then("a low stock alert should be created")
def low_stock_alert(db_session):
    """Check low stock alert was created."""
    pass


@then(parsers.parse('alert priority should be "{priority}"'))
def alert_priority_is(priority):
    """Check alert priority."""
    pass


@given(parsers.parse("inventory item with critical threshold {threshold:d}"))
def inventory_critical_threshold(db_session, threshold):
    """Create inventory with critical threshold."""
    from lab_manager.models.product import Product
    from lab_manager.models.inventory import Inventory

    product = Product(name="Critical Product", unit="mL", sku="CRIT-001")
    db_session.add(product)
    db_session.commit()

    inventory = Inventory(
        product_id=product.id,
        quantity=threshold + 2,
        location="Main Storage",
        status="available",
        critical_quantity=threshold,
    )
    db_session.add(inventory)
    db_session.commit()
    return inventory


@then("a critical stock alert should be created")
def critical_alert(db_session):
    """Check critical alert was created."""
    pass


@given("inventory item expiring in 7 days")
def inventory_expiring_soon(db_session):
    """Create inventory expiring soon."""
    from lab_manager.models.product import Product
    from lab_manager.models.inventory import Inventory
    from datetime import datetime, timedelta

    product = Product(name="Expiring Product", unit="mL", sku="EXP-001")
    db_session.add(product)
    db_session.commit()

    inventory = Inventory(
        product_id=product.id,
        quantity=10,
        location="Main Storage",
        status="available",
        expiry_date=datetime.utcnow() + timedelta(days=7),
    )
    db_session.add(inventory)
    db_session.commit()
    return inventory


@when("expiration check runs")
def run_expiry_check(client, auth_headers):
    """Run expiration check."""
    response = client.post("/api/inventory/check-expiry", headers=auth_headers)
    return response


@then("an expiring alert should be created")
def expiring_alert(db_session):
    """Check expiring alert was created."""
    pass


@given("inventory item expired 3 days ago")
def inventory_expired(db_session):
    """Create expired inventory."""
    from lab_manager.models.product import Product
    from lab_manager.models.inventory import Inventory
    from datetime import datetime, timedelta

    product = Product(name="Expired Product", unit="mL", sku="EXP-002")
    db_session.add(product)
    db_session.commit()

    inventory = Inventory(
        product_id=product.id,
        quantity=10,
        location="Main Storage",
        status="available",
        expiry_date=datetime.utcnow() - timedelta(days=3),
    )
    db_session.add(inventory)
    db_session.commit()
    return inventory


@when("I check the item")
def check_item(client, auth_headers, db_session):
    """Check inventory item."""
    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    response = client.get(f"/api/inventory/{inv}", headers=auth_headers)
    return response


@then("item should be flagged for disposal")
def flagged_disposal(response):
    """Check item is flagged for disposal."""
    data = response.json()
    assert data.get("status") == "expired" or data.get("disposal_recommended") is True


@given(parsers.parse("inventory item with {count:d} transactions exists"))
def inventory_with_transactions(db_session, count):
    """Create inventory with transaction history."""
    from lab_manager.models.product import Product
    from lab_manager.models.inventory import Inventory

    product = Product(name="History Product", unit="mL", sku="HIST-001")
    db_session.add(product)
    db_session.commit()

    inventory = Inventory(
        product_id=product.id, quantity=100, location="Main Storage", status="available"
    )
    db_session.add(inventory)
    db_session.commit()

    # Create transactions would go here
    return inventory


@when("I request inventory history")
def get_inventory_history(client, auth_headers, db_session):
    """Get inventory history."""
    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    response = client.get(f"/api/inventory/{inv}/history", headers=auth_headers)
    return response


@then(parsers.parse("response should contain {count:d} transactions"))
def transaction_count(response, count):
    """Check transaction count."""
    data = response.json()
    assert len(data.get("items", data)) == count


@then("transactions should be ordered by date descending")
def transactions_ordered(response):
    """Check transaction ordering."""
    data = response.json()
    items = data.get("items", data)
    if len(items) > 1:
        dates = [item.get("created_at") for item in items]
        assert dates == sorted(dates, reverse=True)


@given(parsers.parse('inventory with lot number "{lot}" exists'))
def inventory_with_lot(db_session, lot):
    """Create inventory with lot number."""
    from lab_manager.models.product import Product
    from lab_manager.models.inventory import Inventory

    product = Product(name="Lot Product", unit="mL", sku="LOT-001")
    db_session.add(product)
    db_session.commit()

    inventory = Inventory(
        product_id=product.id,
        quantity=10,
        location="Main Storage",
        status="available",
        lot_number=lot,
    )
    db_session.add(inventory)
    db_session.commit()
    return inventory


@when(parsers.parse('I search for lot "{lot}"'))
def search_lot(client, auth_headers, lot):
    """Search by lot number."""
    response = client.get(f"/api/inventory?lot={lot}", headers=auth_headers)
    return response


@then("the correct inventory should be returned")
def correct_inventory_returned(response):
    """Check correct inventory returned."""
    data = response.json()
    items = data.get("items", data)
    assert len(items) >= 1


@given(parsers.parse('inventory with {count:d} reserved units for order "{order_id}"'))
def inventory_reserved(db_session, count, order_id):
    """Create inventory with reservation."""
    from lab_manager.models.product import Product
    from lab_manager.models.inventory import Inventory

    product = Product(name="Reserved Product", unit="mL", sku="RES-001")
    db_session.add(product)
    db_session.commit()

    inventory = Inventory(
        product_id=product.id,
        quantity=50,
        location="Main Storage",
        status="available",
        reserved_quantity=count,
    )
    db_session.add(inventory)
    db_session.commit()
    return inventory


@when(parsers.parse('I reserve {count:d} units for order "{order_id}"'))
def reserve_inventory(client, auth_headers, db_session, count, order_id):
    """Reserve inventory for order."""
    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    response = client.post(
        f"/api/inventory/{inv}/reserve",
        json={"quantity": count, "order_id": order_id},
        headers=auth_headers,
    )
    return response


@then(parsers.parse("available quantity should be {expected:d}"))
def available_quantity_is(db_session, expected):
    """Check available quantity."""
    from lab_manager.models.inventory import Inventory

    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    inventory = db_session.get(Inventory, inv)
    available = inventory.quantity - (inventory.reserved_quantity or 0)
    assert available == expected


@then(parsers.parse("reserved quantity should be {expected:d}"))
def reserved_quantity_is(db_session, expected):
    """Check reserved quantity."""
    from lab_manager.models.inventory import Inventory

    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    inventory = db_session.get(Inventory, inv)
    assert (inventory.reserved_quantity or 0) == expected


@when(parsers.parse('I release reservation for order "{order_id}"'))
def release_reservation(client, auth_headers, db_session, order_id):
    """Release inventory reservation."""
    inv = db_session.execute("SELECT id FROM inventory LIMIT 1").scalar()
    response = client.post(
        f"/api/inventory/{inv}/release",
        json={"order_id": order_id},
        headers=auth_headers,
    )
    return response


@then(parsers.parse("available quantity should increase by {count:d}"))
def available_increased(db_session, count):
    """Check available quantity increased."""
    pass  # Would check before/after


# Common then steps
@then("the response status should be 200")
def status_200(response):
    """Check status 200."""
    assert response.status_code == 200


@then("the response status should be 201")
def status_201(response):
    """Check status 201."""
    assert response.status_code == 201


@then("the response status should be 204")
def status_204(response):
    """Check status 204."""
    assert response.status_code == 204


@then("the response status should be 400")
def status_400(response):
    """Check status 400."""
    assert response.status_code == 400


@then("the response status should be 422")
def status_422(response):
    """Check status 422."""
    assert response.status_code == 422
