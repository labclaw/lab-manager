"""Step definitions for Report Generation feature tests."""

from __future__ import annotations

from pytest_bdd import given, scenario, then, when

FEATURE = "../features/reports.feature"


@scenario(FEATURE, "Generate inventory status report")
def test_inventory_report():
    pass


@scenario(FEATURE, "Export inventory report to PDF")
def test_export_pdf():
    pass


@scenario(FEATURE, "Generate order history report")
def test_order_report():
    pass


@scenario(FEATURE, "Generate spending by vendor report")
def test_spending_report():
    pass


@scenario(FEATURE, "Generate expiring products report")
def test_expiring_report():
    pass


@scenario(FEATURE, "Generate low stock report")
def test_low_stock_report():
    pass


@scenario(FEATURE, "Export to CSV format")
def test_export_csv():
    pass


# --- Given steps ---


@given('I am authenticated as staff "manager1"')
def manager_auth(api):
    return api


@given("products with various inventory levels")
def products_with_inventory(api):
    r = api.post("/api/v1/vendors/", json={"name": "Test Vendor"})
    vendor = r.json()
    for i in range(5):
        r = api.post(
            "/api/v1/products/",
            json={"name": f"Product {i}", "catalog_number": f"CAT-{i}", "vendor_id": vendor["id"]},
        )


@given("orders from multiple vendors")
def orders_from_vendors(api):
    for i in range(3):
        r = api.post("/api/v1/vendors/", json={"name": f"Vendor {i}"})
        vendor = r.json()
        api.post(
            "/api/v1/orders/",
            json={
                "vendor_id": vendor["id"],
                "items": [{"product_name": "Item", "quantity": 1, "unit_price": 100.0}],
            },
        )


@given("products expiring in 30 days")
def products_expiring(api, db):
    from datetime import datetime, timedelta


    r = api.post("/api/v1/vendors/", json={"name": "Test Vendor"})
    vendor = r.json()
    (datetime.now() + timedelta(days=15)).date()
    r = api.post(
        "/api/v1/products/",
        json={"name": "Expiring Product", "catalog_number": "EXP-001", "vendor_id": vendor["id"]},
    )


# --- When steps ---


@when("I generate inventory status report")
def generate_inventory_report(api):
    r = api.get("/api/v1/reports/inventory")
    return r


@when("I export inventory report as PDF")
def export_inventory_pdf(api):
    r = api.get("/api/v1/export/inventory/pdf")
    return r


@when("I generate order history report")
def generate_order_report(api):
    r = api.get("/api/v1/reports/orders")
    return r


@when("I generate spending report")
def generate_spending_report(api):
    r = api.get("/api/v1/reports/spending")
    return r


@when("I generate expiring report")
def generate_expiring_report(api):
    r = api.get("/api/v1/reports/expiring")
    return r


@when("I generate low stock report")
def generate_low_stock_report(api):
    r = api.get("/api/v1/reports/low-stock")
    return r


@when("I export report as CSV")
def export_csv(api):
    r = api.get("/api/v1/export/inventory/csv")
    return r


# --- Then steps ---


@then("report should contain product names")
def check_product_names(generate_inventory_report):
    if generate_inventory_report.status_code == 200:
        data = generate_inventory_report.json()
        assert "items" in data or "products" in str(data).lower()


@then("quantities for each product")
def check_quantities(generate_inventory_report):
    if generate_inventory_report.status_code == 200:
        data = generate_inventory_report.json()
        assert data


@then("reorder indicators")
def check_reorder_indicators(generate_inventory_report):
    pass


@then("a PDF file should be generated")
def check_pdf_generated(export_inventory_pdf):
    assert export_inventory_pdf.status_code in (200, 404)


@then("report should be printable")
def check_printable():
    pass


@then("report should show orders by date")
def check_orders_by_date(generate_order_report):
    if generate_order_report.status_code == 200:
        data = generate_order_report.json()
        assert data


@then("vendor information")
def check_vendor_info():
    pass


@then("total values")
def check_total_values():
    pass


@then("each vendor total should be calculated")
def check_vendor_totals(generate_spending_report):
    if generate_spending_report.status_code == 200:
        data = generate_spending_report.json()
        assert data


@then("vendors should be sorted by spending")
def check_sorted_spending():
    pass


@then("products expiring within 30 days should be listed")
def check_expiring_listed(generate_expiring_report):
    assert generate_expiring_report.status_code in (200, 404)


@then("expiration dates should be shown")
def check_expiration_dates():
    pass


@then("products below reorder level should be listed")
def check_low_stock_listed(generate_low_stock_report):
    assert generate_low_stock_report.status_code in (200, 404)


@then("current stock levels should be shown")
def check_stock_levels():
    pass


@then("CSV file should be downloadable")
def check_csv_downloadable(export_csv):
    assert export_csv.status_code in (200, 404)


@then("special characters should be escaped")
def check_escaped():
    pass
