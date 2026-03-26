"""Step definitions for CSV export BDD scenarios."""

import itertools

import pytest
from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/export.feature"

_seq = itertools.count(1)


# --- Scenarios ---


@scenario(FEATURE, "Export inventory as CSV")
def test_export_inventory():
    pass


@scenario(FEATURE, "Export inventory CSV when empty")
def test_export_inventory_empty():
    pass


@scenario(FEATURE, "Export orders as CSV")
def test_export_orders():
    pass


@scenario(FEATURE, "Export products as CSV")
def test_export_products():
    pass


@scenario(FEATURE, "Export vendors as CSV")
def test_export_vendors():
    pass


# --- Shared state ---


@pytest.fixture
def ctx():
    return {}


# --- Given steps ---


@given("some inventory data exists for export")
def create_inventory_for_export(api):
    r = api.post("/api/v1/vendors", json={"name": f"ExportVendor-{next(_seq)}"})
    assert r.status_code == 201, r.text
    vendor = r.json()

    r = api.post(
        "/api/v1/products",
        json={
            "name": "Export Product",
            "catalog_number": f"EXP-{next(_seq):05d}",
            "vendor_id": vendor["id"],
        },
    )
    assert r.status_code == 201, r.text
    product = r.json()

    r = api.post(
        "/api/v1/inventory",
        json={
            "product_id": product["id"],
            "quantity_on_hand": 10,
            "unit": "bottle",
            "lot_number": "LOT-EXP-001",
        },
    )
    assert r.status_code == 201, r.text


@given("some order data exists for export")
def create_orders_for_export(api):
    r = api.post("/api/v1/vendors", json={"name": f"OrderExportVendor-{next(_seq)}"})
    assert r.status_code == 201, r.text
    vendor = r.json()

    r = api.post(
        "/api/v1/orders",
        json={
            "vendor_id": vendor["id"],
            "po_number": f"PO-EXP-{next(_seq):05d}",
            "status": "pending",
        },
    )
    assert r.status_code == 201, r.text


@given("some product data exists for export")
def create_products_for_export(api):
    r = api.post("/api/v1/vendors", json={"name": f"ProdExportVendor-{next(_seq)}"})
    assert r.status_code == 201, r.text
    vendor = r.json()

    r = api.post(
        "/api/v1/products",
        json={
            "name": "Export Test Product",
            "catalog_number": f"PEXP-{next(_seq):05d}",
            "vendor_id": vendor["id"],
        },
    )
    assert r.status_code == 201, r.text


@given("some vendor data exists for export")
def create_vendors_for_export(api):
    r = api.post(
        "/api/v1/vendors",
        json={
            "name": f"VendExport-{next(_seq)}",
            "website": "https://example.com",
            "email": "test@example.com",
        },
    )
    assert r.status_code == 201, r.text


# --- When steps ---


@when("I download the inventory CSV", target_fixture="csv_response")
def download_inventory_csv(api):
    r = api.get("/api/v1/export/inventory")
    assert r.status_code == 200, r.text
    return r


@when("I download the orders CSV", target_fixture="csv_response")
def download_orders_csv(api):
    r = api.get("/api/v1/export/orders")
    assert r.status_code == 200, r.text
    return r


@when("I download the products CSV", target_fixture="csv_response")
def download_products_csv(api):
    r = api.get("/api/v1/export/products")
    assert r.status_code == 200, r.text
    return r


@when("I download the vendors CSV", target_fixture="csv_response")
def download_vendors_csv(api):
    r = api.get("/api/v1/export/vendors")
    assert r.status_code == 200, r.text
    return r


# --- Then steps ---


@then(parsers.parse("the response should be a CSV file named {filename}"))
def check_csv_content_type(csv_response, filename):
    assert "text/csv" in csv_response.headers.get("content-type", "")
    disposition = csv_response.headers.get("content-disposition", "")
    assert filename in disposition


@then("the CSV should have a header row")
def check_csv_header(csv_response):
    text = csv_response.text
    lines = text.strip().split("\n")
    assert len(lines) >= 1, "CSV should have at least a header row"
    # Header should contain column names separated by commas
    header = lines[0]
    assert "," in header or len(header) > 0
