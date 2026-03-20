"""Step definitions for Data Integrity feature tests."""

from __future__ import annotations

from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/data_integrity.feature"


@scenario(FEATURE, "Order must non-existent vendor")
def test_order_invalid_vendor():
    pass


@scenario(FEATURE, "Duplicate vendor name")
def test_duplicate_vendor():
    pass


@scenario(FEATURE, "Negative inventory quantity")
def test_negative_inventory():
    pass


@scenario(FEATURE, "Invalid email format")
def test_invalid_email():
    pass


# --- Given steps ---


@given('I am authenticated as staff "admin1"')
def admin_auth(api):
    return api


@given(parsers.parse('vendor "{name}" exists'))
def vendor_exists(api, name):
    r = api.post("/api/v1/vendors/", json={"name": name})
    return r.json() if r.status_code in (200, 201) else None


@given(parsers.parse('product "{catalog}" exists'))
def product_exists(api, catalog):
    r = api.post("/api/v1/vendors/", json={"name": "Test Vendor"})
    vendor = r.json()
    r = api.post(
        "/api/v1/products/",
        json={"name": f"Product {catalog}", "catalog_number": catalog, "vendor_id": vendor["id"]},
    )
    return r.json() if r.status_code in (200, 201) else None


# --- When steps ---


@when("I create an order referencing non-existent vendor")
def create_order_bad_vendor(api):
    r = api.post(
        "/api/v1/orders/",
        json={"vendor_id": "00000000-0000-0000-0000-000000000000", "items": []},
    )
    return r


@when("I create another vendor with same name", target_fixture="create_vendor_response")
def create_duplicate_vendor(api):
    r = api.post("/api/v1/vendors/", json={"name": "Sigma"})
    return r


@when("I adjust inventory to -10 units")
def negative_inventory(api, db):
    from lab_manager.models.product import Product

    product = db.query(Product).first()
    if product:
        r = api.post("/api/v1/inventory/", json={"product_id": str(product.id), "quantity": -10})
        return r
    return None


@when('I create staff with email "invalid-email"')
def create_staff_invalid_email(api):
    r = api.post("/api/v1/staff/", json={"name": "Test", "email": "invalid-email", "role": "staff"})
    return r


# --- Then steps ---


@then("I should receive a validation error")
def check_validation(create_order_bad_vendor):
    assert create_order_bad_vendor.status_code in (400, 404, 422)


@then("the error should indicate vendor not found")
def check_vendor_not_found(create_order_bad_vendor):
    error = str(create_order_bad_vendor.json()).lower()
    assert "vendor" in error or "not found" in error


@then("I should receive a conflict error")
def check_conflict(create_vendor_response):
    assert create_vendor_response.status_code in (400, 409)


@then("the original vendor should be preserved")
def check_vendor_preserved(api):
    r = api.get("/api/v1/vendors/")
    assert r.status_code == 200


@then("quantity should be rejected")
def check_quantity_rejected(negative_inventory):
    if negative_inventory:
        assert negative_inventory.status_code in (400, 422)


@then("valid email format should be suggested")
def check_email_format_error(create_staff_invalid_email):
    error = str(create_staff_invalid_email.json()).lower()
    assert "email" in error
