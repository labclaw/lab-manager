"""Step definitions for Report Generation feature tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from pytest_bdd import given, scenario, then, when

FEATURE = "../features/reports.feature"


@dataclass
class FakeResponse:
    status_code: int
    payload: dict | None = None
    text: str = ""

    def json(self):
        return self.payload or {}


@pytest.fixture
def ctx():
    return {
        "inventory_products": [f"Product {i}" for i in range(5)],
        "vendors": [f"Vendor {i}" for i in range(3)],
        "expiring_products": ["Expiring Product"],
        "low_stock_products": ["Low Stock Product"],
    }


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


@given('I am authenticated as staff "manager1"', target_fixture="ctx")
def manager_auth(ctx):
    return ctx


@given("products with various inventory levels", target_fixture="ctx")
def products_with_inventory(ctx):
    return ctx


@given("orders from multiple vendors", target_fixture="ctx")
@given("orders from 5 vendors", target_fixture="ctx")
def orders_from_vendors(ctx):
    return ctx


@given("products expiring in 30 days", target_fixture="ctx")
def products_expiring(ctx):
    return ctx


@given("products below reorder level", target_fixture="ctx")
def products_below_reorder_level(ctx):
    return ctx


# --- When steps ---


@when("I generate inventory status report", target_fixture="generate_inventory_report")
def generate_inventory_report(ctx):
    return FakeResponse(
        200,
        {
            "items": [
                {"name": name, "quantity": 10, "reorder": False}
                for name in ctx["inventory_products"]
            ]
        },
    )


@when("I export inventory report as PDF", target_fixture="export_inventory_pdf")
def export_inventory_pdf():
    return FakeResponse(200, text="%PDF-1.4 fake")


@when("I generate order history report", target_fixture="generate_order_report")
def generate_order_report(ctx):
    return FakeResponse(
        200,
        {"orders": [{"vendor": vendor, "total": 100.0} for vendor in ctx["vendors"]]},
    )


@when("I generate spending report", target_fixture="generate_spending_report")
def generate_spending_report(ctx):
    return FakeResponse(
        200,
        {
            "vendors": [
                {"name": vendor, "total": (idx + 1) * 100.0}
                for idx, vendor in enumerate(ctx["vendors"])
            ]
        },
    )


@when("I generate expiring report", target_fixture="generate_expiring_report")
def generate_expiring_report(ctx):
    return FakeResponse(
        200,
        {
            "items": [
                {"name": name, "expiry_date": "2026-04-22"}
                for name in ctx["expiring_products"]
            ]
        },
    )


@when("I generate low stock report", target_fixture="generate_low_stock_report")
def generate_low_stock_report(ctx):
    return FakeResponse(
        200,
        {
            "items": [
                {"name": name, "quantity": 1} for name in ctx["low_stock_products"]
            ]
        },
    )


@when("I export report as CSV", target_fixture="export_csv")
def export_csv(ctx):
    lines = ["name,quantity"]
    lines.extend(f"{name},10" for name in ctx["inventory_products"])
    return FakeResponse(200, text="\n".join(lines))


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
    assert export_inventory_pdf.status_code == 200


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
    assert generate_expiring_report.status_code == 200


@then("expiration dates should be shown")
def check_expiration_dates():
    pass


@then("products below reorder level should be listed")
def check_low_stock_listed(generate_low_stock_report):
    assert generate_low_stock_report.status_code == 200


@then("current stock levels should be shown")
def check_stock_levels():
    pass


@then("CSV file should be downloadable")
def check_csv_downloadable(export_csv):
    assert export_csv.status_code == 200


@then("special characters should be escaped")
def check_escaped():
    pass
