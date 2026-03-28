"""Step definitions for analytics and dashboard BDD scenarios."""

import itertools

import pytest
from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/analytics.feature"

_seq = itertools.count(1)


# --- Scenarios ---


@scenario(FEATURE, "Dashboard returns summary statistics")
def test_dashboard():
    pass


@scenario(FEATURE, "Dashboard on empty database")
def test_dashboard_empty():
    pass


@scenario(FEATURE, "Spending by vendor")
def test_spending_by_vendor():
    pass


@scenario(FEATURE, "Spending by month")
def test_spending_by_month():
    pass


@scenario(FEATURE, "Inventory value")
def test_inventory_value():
    pass


@scenario(FEATURE, "Top products")
def test_top_products():
    pass


@scenario(FEATURE, "Order history")
def test_order_history():
    pass


@scenario(FEATURE, "Staff activity")
def test_staff_activity():
    pass


@scenario(FEATURE, "Vendor summary")
def test_vendor_summary():
    pass


@scenario(FEATURE, "Vendor summary for non-existent vendor returns 404")
def test_vendor_summary_404():
    pass


@scenario(FEATURE, "Document processing stats")
def test_doc_processing_stats():
    pass


# --- Shared state ---


@pytest.fixture
def ctx():
    return {}


# --- Given steps ---


@given("some baseline data exists for analytics", target_fixture="analytics_vendor")
def create_baseline_data(api):
    r = api.post("/api/v1/vendors/", json={"name": "Analytics Vendor"})
    assert r.status_code == 201, r.text
    vendor = r.json()

    r = api.post(
        "/api/v1/products/",
        json={
            "name": "Analytics Product",
            "catalog_number": f"ANAL-{next(_seq):05d}",
            "vendor_id": vendor["id"],
        },
    )
    assert r.status_code == 201, r.text

    r = api.post(
        "/api/v1/orders/",
        json={
            "vendor_id": vendor["id"],
            "po_number": f"PO-ANAL-{next(_seq):05d}",
            "status": "pending",
        },
    )
    assert r.status_code == 201, r.text

    product = api.post(
        "/api/v1/products/",
        json={
            "name": "Analytics Inv Product",
            "catalog_number": f"ANAL-INV-{next(_seq):05d}",
            "vendor_id": vendor["id"],
        },
    )
    assert product.status_code == 201, product.text
    prod_id = product.json()["id"]

    r = api.post(
        "/api/v1/inventory/",
        json={
            "product_id": prod_id,
            "quantity_on_hand": 10,
            "unit": "bottle",
            "lot_number": "LOT-ANAL",
        },
    )
    assert r.status_code == 201, r.text

    return vendor


@given(
    parsers.parse('a vendor "{name}" with orders and priced items exists'),
    target_fixture="spend_vendor",
)
def create_vendor_with_priced_items(api, name):
    r = api.post("/api/v1/vendors/", json={"name": name})
    assert r.status_code == 201, r.text
    vendor = r.json()

    r = api.post(
        "/api/v1/orders/",
        json={
            "vendor_id": vendor["id"],
            "po_number": f"PO-SPEND-{next(_seq):05d}",
            "status": "pending",
            "order_date": "2026-01-15",
        },
    )
    assert r.status_code == 201, r.text
    order = r.json()["order"]

    r = api.post(
        f"/api/v1/orders/{order['id']}/items",
        json={
            "catalog_number": f"SPEND-{next(_seq):05d}",
            "description": "Priced Item",
            "quantity": 5,
            "unit": "EA",
            "unit_price": 25.50,
        },
    )
    assert r.status_code == 201, r.text

    return vendor


@given(
    parsers.parse('a vendor "{name}" with ordered products exists'),
    target_fixture="top_vendor",
)
def create_vendor_with_ordered_products(api, name):
    r = api.post("/api/v1/vendors/", json={"name": name})
    assert r.status_code == 201, r.text
    vendor = r.json()

    r = api.post(
        "/api/v1/orders/",
        json={
            "vendor_id": vendor["id"],
            "po_number": f"PO-TOP-{next(_seq):05d}",
            "status": "pending",
        },
    )
    assert r.status_code == 201, r.text
    order = r.json()["order"]

    for i in range(3):
        r = api.post(
            f"/api/v1/orders/{order['id']}/items",
            json={
                "catalog_number": f"TOP-{next(_seq):05d}",
                "description": f"Top Product {i + 1}",
                "quantity": 10,
                "unit": "EA",
            },
        )
        assert r.status_code == 201, r.text

    return vendor


@given(
    parsers.parse('a vendor "{name}" with {n:d} orders exists'),
    target_fixture="hist_vendor",
)
def create_vendor_with_n_orders(api, name, n):
    r = api.post("/api/v1/vendors/", json={"name": name})
    assert r.status_code == 201, r.text
    vendor = r.json()

    for i in range(n):
        r = api.post(
            "/api/v1/orders/",
            json={
                "vendor_id": vendor["id"],
                "po_number": f"PO-HIST-{next(_seq):05d}",
                "status": "pending",
            },
        )
        assert r.status_code == 201, r.text

    return vendor


@given(
    parsers.parse('a vendor "{name}" with products and orders exists'),
    target_fixture="summary_vendor",
)
def create_vendor_with_products_and_orders(api, name):
    r = api.post("/api/v1/vendors/", json={"name": name})
    assert r.status_code == 201, r.text
    vendor = r.json()

    r = api.post(
        "/api/v1/products/",
        json={
            "name": "Summary Product",
            "catalog_number": f"SUM-{next(_seq):05d}",
            "vendor_id": vendor["id"],
        },
    )
    assert r.status_code == 201, r.text

    r = api.post(
        "/api/v1/orders/",
        json={
            "vendor_id": vendor["id"],
            "po_number": f"PO-SUM-{next(_seq):05d}",
            "status": "pending",
        },
    )
    assert r.status_code == 201, r.text

    return vendor


@given(parsers.parse("{n:d} documents exist for analytics"))
def create_docs_for_analytics(api, n):
    for i in range(n):
        r = api.post(
            "/api/v1/documents/",
            json={
                "file_name": f"analytics_doc_{i}.jpg",
                "file_path": f"uploads/analytics_doc_{i}.jpg",
                "status": "approved",
            },
        )
        assert r.status_code == 201, r.text


# --- When steps ---


@when("I request the dashboard", target_fixture="dashboard_response")
def request_dashboard(api):
    r = api.get("/api/v1/analytics/dashboard")
    assert r.status_code == 200, r.text
    return r.json()


@when("I request spending by vendor", target_fixture="spending_response")
def request_spending_by_vendor(api):
    r = api.get("/api/v1/analytics/spending/by-vendor")
    assert r.status_code == 200, r.text
    return r.json()


@when("I request spending by month", target_fixture="spending_month_response")
def request_spending_by_month(api):
    r = api.get("/api/v1/analytics/spending/by-month")
    assert r.status_code == 200, r.text
    return r.json()


@when("I request inventory value", target_fixture="inv_value_response")
def request_inventory_value(api):
    r = api.get("/api/v1/analytics/inventory/value")
    assert r.status_code == 200, r.text
    return r.json()


@when("I request top products", target_fixture="top_products_response")
def request_top_products(api):
    r = api.get("/api/v1/analytics/products/top")
    assert r.status_code == 200, r.text
    return r.json()


@when("I request order history", target_fixture="order_history_response")
def request_order_history(api):
    r = api.get("/api/v1/analytics/orders/history")
    assert r.status_code == 200, r.text
    return r.json()


@when("I request staff activity", target_fixture="staff_response")
def request_staff_activity(api):
    r = api.get("/api/v1/analytics/staff/activity")
    assert r.status_code == 200, r.text
    return r.json()


@when("I request the vendor summary", target_fixture="vendor_summary_response")
def request_vendor_summary(api, summary_vendor):
    r = api.get(f"/api/v1/analytics/vendors/{summary_vendor['id']}/summary")
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse("I request vendor summary for id {vid:d}"),
    target_fixture="vendor_summary_raw",
)
def request_vendor_summary_404(api, vid):
    return api.get(f"/api/v1/analytics/vendors/{vid}/summary")


@when(
    "I request document processing stats via analytics",
    target_fixture="doc_stats_response",
)
def request_doc_stats(api):
    r = api.get("/api/v1/analytics/documents/stats")
    assert r.status_code == 200, r.text
    return r.json()


# --- Then steps ---


@then("the dashboard should include total counts")
def check_dashboard_totals(dashboard_response):
    for key in (
        "total_products",
        "total_vendors",
        "total_orders",
        "total_inventory_items",
    ):
        assert key in dashboard_response, f"Missing key: {key}"


@then("the dashboard should include orders_by_status")
def check_dashboard_orders_status(dashboard_response):
    assert "orders_by_status" in dashboard_response


@then("the dashboard should include inventory_by_status")
def check_dashboard_inv_status(dashboard_response):
    assert "inventory_by_status" in dashboard_response


@then(parsers.parse("the dashboard total_products should be {n:d}"))
def check_dashboard_products(dashboard_response, n):
    assert dashboard_response["total_products"] == n


@then(parsers.parse("the dashboard total_vendors should be {n:d}"))
def check_dashboard_vendors(dashboard_response, n):
    assert dashboard_response["total_vendors"] == n


@then(parsers.parse("the dashboard total_orders should be {n:d}"))
def check_dashboard_orders(dashboard_response, n):
    assert dashboard_response["total_orders"] == n


@then("the spending list should not be empty")
def check_spending_not_empty(spending_response):
    assert len(spending_response) > 0


@then("the first vendor should have order_count and total_spend")
def check_spending_fields(spending_response):
    first = spending_response[0]
    assert "order_count" in first
    assert "total_spend" in first


@then("the spending by month response should be a list")
def check_spending_month_list(spending_month_response):
    assert isinstance(spending_month_response, list)


@then("the response should include total_value and item_count")
def check_inv_value(inv_value_response):
    assert "total_value" in inv_value_response
    assert "item_count" in inv_value_response


@then("the top products list should not be empty")
def check_top_products(top_products_response):
    assert len(top_products_response) > 0


@then(parsers.parse("the order history should contain at least {n:d} entries"))
def check_order_history(order_history_response, n):
    assert len(order_history_response) >= n


@then("the staff activity response should be a list")
def check_staff_activity(staff_response):
    assert isinstance(staff_response, list)


@then("the summary should include products_supplied and order_count")
def check_vendor_summary_fields(vendor_summary_response):
    assert "products_supplied" in vendor_summary_response
    assert "order_count" in vendor_summary_response


@then(parsers.parse("the vendor summary response status should be {code:d}"))
def check_vendor_summary_status(vendor_summary_raw, code):
    assert vendor_summary_raw.status_code == code


@then("the analytics doc stats should include total_documents")
def check_doc_stats(doc_stats_response):
    assert "total_documents" in doc_stats_response
    assert doc_stats_response["total_documents"] >= 5
