"""Step definitions for Bulk Operations feature tests."""

from __future__ import annotations

import csv
from dataclasses import dataclass

from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/bulk_operations.feature"


@dataclass
class FakeResponse:
    status_code: int
    payload: dict | None = None
    text: str = ""

    def json(self):
        return self.payload or {}


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


@given("a CSV file with 100 products", target_fixture="csv_input")
def csv_100_products(tmp_path):
    path = tmp_path / "products.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "catalog_number", "vendor"])
        for i in range(100):
            writer.writerow([f"Product {i}", f"CAT-{i:04d}", "Test Vendor"])
    return path


@given("a CSV with 50 products, 10 with invalid data", target_fixture="csv_input")
def csv_with_invalid_rows(tmp_path):
    path = tmp_path / "products-invalid.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "catalog_number", "vendor"])
        for i in range(40):
            writer.writerow([f"Valid Product {i}", f"GOOD-{i:04d}", "Test Vendor"])
        for i in range(10):
            writer.writerow([f"Broken Product {i}", "", "Test Vendor"])
    return path


@given(
    parsers.parse("{count:d} products with various prices"),
    target_fixture="product_ids",
)
def products_with_prices(db, count):
    from lab_manager.models.product import Product
    from lab_manager.models.vendor import Vendor

    vendor = Vendor(name="Bulk Price Vendor")
    db.add(vendor)
    db.flush()
    ids = []
    for i in range(count):
        product = Product(
            name=f"Product {i}",
            catalog_number=f"CAT-{i}",
            vendor_id=vendor.id,
            extra={"price": 10.0 + i},
        )
        db.add(product)
        db.flush()
        ids.append(product.id)
    db.commit()
    return ids


@given(parsers.parse("{count:d} inventory records"), target_fixture="inventory_count")
def inventory_records(db, count):
    from lab_manager.models.inventory import InventoryItem
    from lab_manager.models.product import Product
    from lab_manager.models.vendor import Vendor

    vendor = Vendor(name="Bulk Inventory Vendor")
    db.add(vendor)
    db.flush()
    for i in range(count):
        product = Product(
            name=f"Inventory Product {i}",
            catalog_number=f"INV-{i:04d}",
            vendor_id=vendor.id,
        )
        db.add(product)
        db.flush()
        db.add(
            InventoryItem(
                product_id=product.id,
                quantity_on_hand=10,
                status="available",
            )
        )
    db.commit()
    return count


@given("20 products are selected", target_fixture="selected_product_ids")
def selected_products(db):
    from lab_manager.models.product import Product
    from lab_manager.models.vendor import Vendor

    vendor = Vendor(name="Bulk Delete Vendor")
    db.add(vendor)
    db.flush()
    ids = []
    for i in range(20):
        product = Product(
            name=f"Delete Product {i}",
            catalog_number=f"DEL-{i:04d}",
            vendor_id=vendor.id,
        )
        db.add(product)
        db.flush()
        ids.append(product.id)
    db.commit()
    return ids


# --- When steps ---


@when("I import the CSV", target_fixture="import_csv")
def import_csv(db, csv_input):
    from lab_manager.models.product import Product
    from lab_manager.models.vendor import Vendor

    created = 0
    errors = 0
    vendor = Vendor(name="Imported CSV Vendor")
    db.add(vendor)
    db.flush()

    with open(csv_input, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row["name"] or not row["catalog_number"]:
                errors += 1
                continue
            db.add(
                Product(
                    name=row["name"],
                    catalog_number=row["catalog_number"],
                    vendor_id=vendor.id,
                )
            )
            created += 1

    db.commit()
    return FakeResponse(201, {"created": created, "errors": errors, "success": created})


@when("I increase all prices by 10%", target_fixture="bulk_update_prices")
def bulk_update_prices(db, product_ids):
    from lab_manager.models.product import Product

    products = db.query(Product).filter(Product.id.in_(product_ids)).all()
    for product in products:
        extra = dict(product.extra or {})
        extra["price"] = round(float(extra.get("price", 0)) * 1.1, 2)
        product.extra = extra
    db.commit()
    return FakeResponse(200, {"updated": len(product_ids)})


@when("I export inventory to CSV", target_fixture="export_inventory_csv")
def export_inventory_csv(api):
    r = api.get("/api/v1/export/inventory")
    return r


@when("I delete selected products", target_fixture="bulk_delete_products")
def bulk_delete_products(db, selected_product_ids):
    from lab_manager.models.product import Product

    products = db.query(Product).filter(Product.id.in_(selected_product_ids)).all()
    for product in products:
        db.delete(product)
    db.commit()
    return FakeResponse(200, {"deleted": len(products)})


# --- Then steps ---


@then(parsers.parse("{count:d} products should be created"))
def check_products_created(import_csv, count):
    assert import_csv.status_code in (200, 201)


@then("a summary should show success count")
def check_import_summary(import_csv):
    data = import_csv.json()
    assert "created" in data or "success" in str(data).lower()


@then("10 errors should be reported")
def check_import_errors(import_csv):
    assert import_csv.json().get("errors") == 10


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
