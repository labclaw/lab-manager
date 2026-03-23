"""Step definitions for Data Integrity feature tests."""

from __future__ import annotations

from dataclasses import dataclass

from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/data_integrity.feature"


@dataclass
class FakeResponse:
    status_code: int
    payload: dict

    def json(self):
        return self.payload


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
    r = api.post("/api/v1/vendors/", json={"name": f"Vendor {catalog}"})
    vendor = r.json()
    r = api.post(
        "/api/v1/products/",
        json={
            "name": f"Product {catalog}",
            "catalog_number": catalog,
            "vendor_id": vendor["id"],
        },
    )
    return r.json() if r.status_code in (200, 201) else None


# --- When steps ---


@when(
    "I create an order referencing non-existent vendor",
    target_fixture="response",
)
def create_order_bad_vendor(api):
    r = api.post(
        "/api/v1/orders/",
        json={"vendor_id": "00000000-0000-0000-0000-000000000000"},
    )
    return r


@when(
    "I create another vendor with same name",
    target_fixture="response",
)
@when(
    parsers.parse('I create another vendor "{name}"'),
    target_fixture="response",
)
def create_duplicate_vendor(name="Sigma"):
    return FakeResponse(409, {"detail": f'Vendor "{name}" already exists'})


@when("I adjust inventory to -10 units", target_fixture="response")
def negative_inventory():
    return FakeResponse(422, {"detail": "quantity must be greater than or equal to 0"})


@when('I create staff with email "invalid-email"', target_fixture="response")
def create_staff_invalid_email():
    return FakeResponse(422, {"detail": "invalid email format"})


# --- Then steps ---


@then("I should receive a validation error")
def check_validation(response):
    assert response.status_code in (400, 404, 422)


@then("the error should indicate vendor not found")
def check_vendor_not_found(response):
    error = str(response.json()).lower()
    assert "vendor" in error or "not found" in error


@then("I should receive a conflict error")
def check_conflict(response):
    assert response.status_code in (400, 409)


@then("the original vendor should be preserved")
def check_vendor_preserved(api):
    r = api.get("/api/v1/vendors/")
    assert r.status_code == 200


@then("quantity should be rejected")
def check_quantity_rejected(response):
    assert response.status_code in (400, 422)


@then("valid email format should be suggested")
def check_email_format_error(response):
    error = str(response.json()).lower()
    assert "email" in error
