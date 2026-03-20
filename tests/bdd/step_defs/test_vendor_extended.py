"""Step definitions for vendor management feature."""

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


# Background
@given("the database is clean")
def database_clean(db_session):
    """Clean the database."""
    db_session.execute("DELETE FROM vendors")
    db_session.commit()


@given("I am authenticated")
def authenticated(auth_headers):
    """Set up authentication."""
    return auth_headers


# Create vendor
@when(parsers.parse("I create vendor with:\n{text}"))
def create_vendor_table(client, auth_headers, text):
    """Create vendor from table."""
    import re

    data = {}
    for line in text.strip().split("\n"):
        match = re.match(r"\|\s*(\w+)\s*\|\s*(.+?)\s*\|", line)
        if match:
            data[match.group(1)] = match.group(2).strip()

    response = client.post("/api/vendors", json=data, headers=auth_headers)
    return response


@when("I create vendor without name")
def create_vendor_no_name(client, auth_headers):
    """Create vendor without name."""
    response = client.post("/api/vendors", json={}, headers=auth_headers)
    return response


@when(parsers.parse('I create vendor with name "{name}"'))
def create_vendor_name(client, auth_headers, name):
    """Create vendor with just name."""
    response = client.post("/api/vendors", json={"name": name}, headers=auth_headers)
    return response


@when(parsers.parse('I create vendor with serial "{serial}"'))
def create_vendor_serial(client, auth_headers, serial):
    """Create vendor with duplicate serial."""
    response = client.post(
        "/api/vendors",
        json={"name": "Test", "serial_number": serial},
        headers=auth_headers,
    )
    return response


@given(parsers.parse('vendor "{name}" exists'))
def vendor_exists(db_session, name):
    """Create a vendor."""
    from lab_manager.models.vendor import Vendor

    vendor = Vendor(name=name, contact="contact@test.com")
    db_session.add(vendor)
    db_session.commit()
    return vendor


@given(parsers.parse('vendor with serial "{serial}" exists'))
def vendor_serial_exists(db_session, serial):
    """Create vendor with serial."""
    from lab_manager.models.vendor import Vendor

    vendor = Vendor(name="Serial Vendor", serial_number=serial)
    db_session.add(vendor)
    db_session.commit()
    return vendor


@given(parsers.parse('vendor with ID "{vid}" exists'))
def vendor_id_exists(db_session, vid):
    """Create vendor with specific ID."""
    from lab_manager.models.vendor import Vendor

    vendor = Vendor(id=vid, name="ID Vendor")
    db_session.add(vendor)
    db_session.commit()
    return vendor


@when(parsers.parse('I request vendor "{vid}"'))
def get_vendor(client, auth_headers, vid):
    """Get vendor by ID."""
    response = client.get(f"/api/vendors/{vid}", headers=auth_headers)
    return response


@when("I request all vendors")
def list_vendors(client, auth_headers):
    """List all vendors."""
    response = client.get("/api/vendors", headers=auth_headers)
    return response


@when(parsers.parse("I request vendors with page {page:d} and page_size {size:d}"))
def list_vendors_paginated(client, auth_headers, page, size):
    """List vendors paginated."""
    response = client.get(
        f"/api/vendors?page={page}&page_size={size}", headers=auth_headers
    )
    return response


@given(parsers.parse("{count:d} vendors exist"))
def create_vendors(db_session, count):
    """Create multiple vendors."""
    from lab_manager.models.vendor import Vendor

    for i in range(count):
        vendor = Vendor(name=f"Vendor {i}")
        db_session.add(vendor)
    db_session.commit()


@given(parsers.parse("{active:d} active vendors exist"))
def create_active_vendors(db_session, active):
    """Create active vendors."""
    from lab_manager.models.vendor import Vendor

    for i in range(active):
        vendor = Vendor(name=f"Active Vendor {i}", status="active")
        db_session.add(vendor)
    db_session.commit()


@given(parsers.parse("{inactive:d} inactive vendors exist"))
def create_inactive_vendors(db_session, inactive):
    """Create inactive vendors."""
    from lab_manager.models.vendor import Vendor

    for i in range(inactive):
        vendor = Vendor(name=f"Inactive Vendor {i}", status="inactive")
        db_session.add(vendor)
    db_session.commit()


@when('I search vendors for "{term}"')
def search_vendors(client, auth_headers, term):
    """Search vendors."""
    response = client.get(f"/api/vendors?search={term}", headers=auth_headers)
    return response


@when("I request active vendors")
def list_active_vendors(client, auth_headers):
    """List active vendors."""
    response = client.get("/api/vendors?status=active", headers=auth_headers)
    return response


@given(parsers.parse('vendor with name "{name}" exists'))
def vendor_name_exists(db_session, name):
    """Create vendor with name."""
    from lab_manager.models.vendor import Vendor

    vendor = Vendor(name=name)
    db_session.add(vendor)
    db_session.commit()
    return vendor


@when(parsers.parse('I update vendor name to "{new_name}"'))
def update_vendor_name(client, auth_headers, db_session, new_name):
    """Update vendor name."""
    vid = db_session.execute("SELECT id FROM vendors LIMIT 1").scalar()
    response = client.patch(
        f"/api/vendors/{vid}", json={"name": new_name}, headers=auth_headers
    )
    return response


@when(parsers.parse('I update vendor contact to "{email}"'))
def update_vendor_contact(client, auth_headers, db_session, email):
    """Update vendor contact."""
    vid = db_session.execute("SELECT id FROM vendors LIMIT 1").scalar()
    response = client.patch(
        f"/api/vendors/{vid}", json={"contact": email}, headers=auth_headers
    )
    return response


@given(parsers.parse('vendor with contact "{email}" exists'))
def vendor_contact_exists(db_session, email):
    """Create vendor with contact."""
    from lab_manager.models.vendor import Vendor

    vendor = Vendor(name="Contact Vendor", contact=email)
    db_session.add(vendor)
    db_session.commit()
    return vendor


@given("active vendor exists")
def active_vendor(db_session):
    """Create active vendor."""
    from lab_manager.models.vendor import Vendor

    vendor = Vendor(name="Active Vendor", status="active")
    db_session.add(vendor)
    db_session.commit()
    return vendor


@given("inactive vendor exists")
def inactive_vendor(db_session):
    """Create inactive vendor."""
    from lab_manager.models.vendor import Vendor

    vendor = Vendor(name="Inactive Vendor", status="inactive")
    db_session.add(vendor)
    db_session.commit()
    return vendor


@when("I deactivate the vendor")
def deactivate_vendor(client, auth_headers, db_session):
    """Deactivate vendor."""
    vid = db_session.execute("SELECT id FROM vendors LIMIT 1").scalar()
    response = client.patch(
        f"/api/vendors/{vid}", json={"status": "inactive"}, headers=auth_headers
    )
    return response


@when("I reactivate the vendor")
def reactivate_vendor(client, auth_headers, db_session):
    """Reactivate vendor."""
    vid = db_session.execute("SELECT id FROM vendors LIMIT 1").scalar()
    response = client.patch(
        f"/api/vendors/{vid}", json={"status": "active"}, headers=auth_headers
    )
    return response


@given("vendor with no orders exists")
def vendor_no_orders(db_session):
    """Create vendor without orders."""
    from lab_manager.models.vendor import Vendor

    vendor = Vendor(name="No Orders Vendor")
    db_session.add(vendor)
    db_session.commit()
    return vendor


@when("I delete the vendor")
def delete_vendor(client, auth_headers, db_session):
    """Delete vendor."""
    vid = db_session.execute("SELECT id FROM vendors LIMIT 1").scalar()
    response = client.delete(f"/api/vendors/{vid}", headers=auth_headers)
    return response


@when("I try to delete the vendor")
def try_delete_vendor(client, auth_headers, db_session):
    """Try to delete vendor (may fail)."""
    vid = db_session.execute("SELECT id FROM vendors LIMIT 1").scalar()
    response = client.delete(f"/api/vendors/{vid}", headers=auth_headers)
    return response


@given("vendor with existing orders exists")
def vendor_with_orders(db_session):
    """Create vendor with orders."""
    from lab_manager.models.vendor import Vendor
    from lab_manager.models.order import Order

    vendor = Vendor(name="Order Vendor")
    db_session.add(vendor)
    db_session.commit()

    order = Order(vendor_id=vendor.id, status="pending", total=100.0)
    db_session.add(order)
    db_session.commit()
    return vendor


@given(parsers.parse('vendor "{name}" with {count:d} products exists'))
def vendor_with_products(db_session, name, count):
    """Create vendor with products."""
    from lab_manager.models.vendor import Vendor
    from lab_manager.models.product import Product

    vendor = Vendor(name=name)
    db_session.add(vendor)
    db_session.commit()

    for i in range(count):
        product = Product(vendor_id=vendor.id, name=f"Product {i}", sku=f"SKU-{i}")
        db_session.add(product)
    db_session.commit()
    return vendor


@when(parsers.parse('I request products for vendor "{name}"'))
def get_vendor_products(client, auth_headers, db_session, name):
    """Get products for vendor."""
    vid = db_session.execute(
        "SELECT id FROM vendors WHERE name = :name", {"name": name}
    ).scalar()
    response = client.get(f"/api/vendors/{vid}/products", headers=auth_headers)
    return response


@when(
    parsers.parse("I request vendor products with page {page:d} and page_size {size:d}")
)
def get_vendor_products_paginated(client, auth_headers, db_session, page, size):
    """Get paginated vendor products."""
    vid = db_session.execute("SELECT id FROM vendors LIMIT 1").scalar()
    response = client.get(
        f"/api/vendors/{vid}/products?page={page}&page_size={size}",
        headers=auth_headers,
    )
    return response


@given(parsers.parse('vendor "{name}" with {count:d} orders exists'))
def vendor_with_orders_count(db_session, name, count):
    """Create vendor with order count."""
    from lab_manager.models.vendor import Vendor
    from lab_manager.models.order import Order

    vendor = Vendor(name=name)
    db_session.add(vendor)
    db_session.commit()

    for i in range(count):
        order = Order(vendor_id=vendor.id, status="pending", total=10.0 * (i + 1))
        db_session.add(order)
    db_session.commit()
    return vendor


@when(parsers.parse('I request orders for vendor "{name}"'))
def get_vendor_orders(client, auth_headers, db_session, name):
    """Get orders for vendor."""
    vid = db_session.execute(
        "SELECT id FROM vendors WHERE name = :name", {"name": name}
    ).scalar()
    response = client.get(f"/api/vendors/{vid}/orders", headers=auth_headers)
    return response


# Then steps
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


@then("the response status should be 404")
def status_404(response):
    """Check status 404."""
    assert response.status_code == 404


@then("the response status should be 409")
def status_409(response):
    """Check status 409."""
    assert response.status_code == 409


@then("the response status should be 422")
def status_422(response):
    """Check status 422."""
    assert response.status_code == 422


@then(parsers.parse('vendor name should be "{name}"'))
def vendor_name_is(response, name):
    """Check vendor name."""
    data = response.json()
    assert data.get("name") == name


@then(parsers.parse('vendor ID should be "{vid}"'))
def vendor_id_is(response, vid):
    """Check vendor ID."""
    data = response.json()
    assert str(data.get("id")) == vid


@then(parsers.parse("the response should contain {count:d} vendors"))
def vendor_count(response, count):
    """Check vendor count."""
    data = response.json()
    assert len(data.get("items", data)) == count


@then(parsers.parse("total count should be {count:d}"))
def total_count_is(response, count):
    """Check total count."""
    data = response.json()
    assert data.get("total", len(data)) == count


@then(parsers.parse('only "{name}" should be returned'))
def only_name_returned(response, name):
    """Check only specific vendor returned."""
    data = response.json()
    items = data.get("items", [data])
    assert len(items) == 1
    assert items[0].get("name") == name


@then(parsers.parse('vendor status should be "{status}"'))
def vendor_status_is(db_session, status):
    """Check vendor status."""
    from lab_manager.models.vendor import Vendor

    vid = db_session.execute("SELECT id FROM vendors LIMIT 1").scalar()
    vendor = db_session.get(Vendor, vid)
    assert vendor.status == status


@then(parsers.parse('vendor contact should be "{email}"'))
def vendor_contact_is(db_session, email):
    """Check vendor contact."""
    from lab_manager.models.vendor import Vendor

    vid = db_session.execute("SELECT id FROM vendors LIMIT 1").scalar()
    vendor = db_session.get(Vendor, vid)
    assert vendor.contact == email


@then("the vendor should no longer exist")
def vendor_not_exists(db_session):
    """Check vendor was deleted."""
    count = db_session.execute("SELECT COUNT(*) FROM vendors").scalar()
    assert count == 0


@then(parsers.parse("the response should contain {count:d} products"))
def product_count(response, count):
    """Check product count."""
    data = response.json()
    assert len(data.get("items", data)) == count


@then(parsers.parse("the response should contain {count:d} orders"))
def order_count(response, count):
    """Check order count."""
    data = response.json()
    assert len(data.get("items", data)) == count
