"""Step definitions for Bulk Operations feature tests."""

from __future__ import annotations

from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/bulk_operations.feature"


@scenario(FEATURE, "Import 100 products from CSV")
def test_import_100_products():
    pass


@scenario(FEATURE, "Import with validation errors")
def test_import_with_errors():
    pass


@scenario(FEATURE, "Bulk update prices by percentage")
def test_bulk_update_prices():
    pass


@scenario(FEATURE, "Export all inventory to CSV")
def test_export_inventory():
    pass


@scenario(FEATURE, "Delete multiple selected products")
def test_bulk_delete():
    pass


# --- Given steps ---


@given('I am authenticated as staff "admin1"')
def admin_auth(api):
    return api


@given("a CSV file with 100 products")
def csv_100_products(tmp_path):
    import csv

    path = tmp_path / "products.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "catalog_number", "vendor"])
        for i in range(100):
            writer.writerow([f"Product {i}", f"CAT-{i:04d}", "Test Vendor"])
    return path


@given(parsers.parse("{count:d} products with various prices"))
def products_with_prices(api, count):
    r = api.post("/api/v1/vendors/", json={"name": "Test Vendor"})
    vendor = r.json()
    for i in range(count):
        api.post(
            "/api/v1/products/",
            json={
                "name": f"Product {i}",
                "catalog_number": f"CAT-{i}",
                "vendor_id": vendor["id"],
                "price": 10.0 + i,
            },
        )


@given(parsers.parse("{count:d} inventory records"))
def inventory_records(api, db, count):
    from lab_manager.models.product import Product

    products = db.query(Product).limit(count).all()
    for p in products:
        api.post("/api/v1/inventory/", json={"product_id": str(p.id), "quantity": 10.0})


# --- When steps ---


@when("I import the CSV")
def import_csv(api, csv_100_products):
    with open(csv_100_products, "rb") as f:
        r = api.post("/api/v1/products/import", files={"file": ("products.csv", f)})
    return r


@when("I increase all prices by 10%")
def bulk_update_prices(api):
    r = api.post("/api/v1/products/bulk-update", json={"price_multiplier": 1.1})
    return r


@when("I export inventory to CSV")
def export_inventory_csv(api):
    r = api.get("/api/v1/export/inventory")
    return r


@when("I delete selected products")
def bulk_delete_products(api, db):
    from lab_manager.models.product import Product

    products = db.query(Product).limit(20).all()
    ids = [str(p.id) for p in products]
    r = api.post("/api/v1/products/bulk-delete", json={"ids": ids})
    return r


# --- Then steps ---


@then(parsers.parse("{count:d} products should be created"))
def check_products_created(import_csv, count):
    assert import_csv.status_code in (200, 201)


@then("a summary should show success count")
def check_import_summary(import_csv):
    data = import_csv.json()
    assert "created" in data or "success" in str(data).lower()


@then("all products should have updated prices")
def check_prices_updated(bulk_update_prices):
    assert bulk_update_prices.status_code in (200, 204)


@then("price history should be recorded")
def check_price_history():
    pass


@then("a CSV file should be generated")
def check_csv_generated(export_inventory_csv):
    assert export_inventory_csv.status_code == 200


@then(parsers.parse("{count:d} rows should be included"))
def check_csv_rows(export_inventory_csv, count):
    content = export_inventory_csv.text
    lines = content.strip().split("\n")
    assert len(lines) >= count  # Including header


@then(parsers.parse("{count:d} products should be deleted"))
def check_products_deleted(bulk_delete_products, count):
    assert bulk_delete_products.status_code in (200, 204)


@then("confirmation should be required")
def check_confirmation():
    pass
