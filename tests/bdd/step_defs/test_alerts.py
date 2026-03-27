"""Step definitions for alerts and monitoring BDD scenarios.

Tests the real alert API endpoints:
  GET    /api/v1/alerts/                    — list (with type/severity/resolved filters)
  GET    /api/v1/alerts/summary             — alert summary
  POST   /api/v1/alerts/check               — trigger alert check
  POST   /api/v1/alerts/{id}/acknowledge    — acknowledge alert
  POST   /api/v1/alerts/{id}/resolve        — resolve alert
"""

import itertools
from datetime import date, timedelta

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from lab_manager.models.alert import Alert
from lab_manager.models.document import Document
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor

FEATURE = "../features/alerts.feature"

_vendor_seq = itertools.count(1)


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


@scenario(FEATURE, "Detect expiring reagents")
def test_detect_expiring_reagents():
    pass


@scenario(FEATURE, "Detect low stock")
def test_detect_low_stock():
    pass


@scenario(FEATURE, "List active alerts")
def test_list_active_alerts():
    pass


@scenario(FEATURE, "Acknowledge an alert")
def test_acknowledge_alert():
    pass


@scenario(FEATURE, "Resolve an alert")
def test_resolve_alert():
    pass


@scenario(FEATURE, "Alert summary counts")
def test_alert_summary_counts():
    pass


@scenario(FEATURE, "Alert check on clean database")
def test_alert_check_clean():
    pass


@scenario(FEATURE, "Filter alerts by type")
def test_filter_by_type():
    pass


@scenario(FEATURE, "Filter alerts by severity")
def test_filter_by_severity():
    pass


@scenario(FEATURE, "Acknowledge non-existent alert returns 404")
def test_ack_not_found():
    pass


@scenario(FEATURE, "Resolve non-existent alert returns 404")
def test_resolve_not_found():
    pass


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx():
    """Shared context dict for passing data between steps."""
    return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_vendor(db):
    vendor = Vendor(name=f"Test Vendor {next(_vendor_seq)}")
    db.add(vendor)
    db.flush()
    return vendor


def _create_product(db, vendor_id, catalog_number, min_stock_level=None):
    product = Product(
        name=f"Product {catalog_number}",
        catalog_number=catalog_number,
        vendor_id=vendor_id,
        min_stock_level=min_stock_level,
    )
    db.add(product)
    db.flush()
    return product


def _create_inventory_item(
    db, product_id, quantity, expiry_date=None, lot_number="LOT001"
):
    item = InventoryItem(
        product_id=product_id,
        quantity_on_hand=quantity,
        unit="bottle",
        lot_number=lot_number,
        expiry_date=expiry_date,
        status="available",
    )
    db.add(item)
    db.flush()
    return item


def _create_alert(
    db, alert_type="expiring_soon", severity="warning", is_resolved=False, entity_id=1
):
    alert = Alert(
        alert_type=alert_type,
        severity=severity,
        message=f"Test alert: {alert_type}",
        entity_type="inventory",
        entity_id=entity_id,
        is_resolved=is_resolved,
    )
    db.add(alert)
    db.flush()
    return alert


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given("an inventory item expiring in 7 days", target_fixture="expiring_item")
def create_expiring_item(db):
    vendor = _create_vendor(db)
    product = _create_product(db, vendor.id, "CAT-EXP-001")
    expiry = date.today() + timedelta(days=7)
    item = _create_inventory_item(db, product.id, quantity=5, expiry_date=expiry)
    return item


@given(
    parsers.parse("a product with min_stock_level {level:d}"),
    target_fixture="low_stock_product",
)
def create_product_with_min_stock(db, level):
    vendor = _create_vendor(db)
    product = _create_product(db, vendor.id, "CAT-LOW-001", min_stock_level=level)
    return product


@given(parsers.parse("inventory total quantity is {qty:d}"))
def create_inventory_below_min(db, low_stock_product, qty):
    _create_inventory_item(
        db, low_stock_product.id, quantity=qty, lot_number="LOT-LOW-001"
    )


@given(parsers.parse("{n:d} active alerts exist"))
def create_active_alerts(db, ctx, n):
    alerts = []
    for i in range(n):
        alert = _create_alert(
            db,
            alert_type="expiring_soon",
            severity="warning",
            is_resolved=False,
            entity_id=1000 + i,
        )
        alerts.append(alert)
    ctx["active_alerts"] = alerts


@given(parsers.parse("{n:d} resolved alerts exist"))
def create_resolved_alerts(db, ctx, n):
    for i in range(n):
        _create_alert(
            db,
            alert_type="expiring_soon",
            severity="warning",
            is_resolved=True,
            entity_id=2000 + i,
        )


@given("an active alert exists", target_fixture="active_alert")
def create_single_active_alert(db):
    return _create_alert(
        db,
        alert_type="expiring_soon",
        severity="warning",
        is_resolved=False,
        entity_id=3000,
    )


@given(parsers.parse("{n:d} inventory items expiring soon"))
def create_expiring_items(db, n):
    vendor = _create_vendor(db)
    for i in range(n):
        product = _create_product(db, vendor.id, f"CAT-SUMEXP-{i:03d}")
        expiry = date.today() + timedelta(days=10 + i)
        _create_inventory_item(
            db, product.id, quantity=5, expiry_date=expiry, lot_number=f"LOT-SUMEXP-{i}"
        )


@given(parsers.parse("{n:d} products with low stock"))
def create_low_stock_products(db, n):
    vendor = _create_vendor(db)
    for i in range(n):
        product = _create_product(
            db, vendor.id, f"CAT-SUMLOW-{i:03d}", min_stock_level=100
        )
        _create_inventory_item(db, product.id, quantity=1, lot_number=f"LOT-SUMLOW-{i}")


@given(parsers.parse("{n:d} documents pending review"))
def create_pending_documents(db, n):
    for i in range(n):
        doc = Document(
            file_path=f"/tmp/test_doc_{i}.pdf",
            file_name=f"test_doc_summary_{i}.pdf",
            document_type="packing_list",
            vendor_name="Test Vendor",
            status="pending",
        )
        db.add(doc)
    db.flush()


@given("alerts of different types exist")
def create_mixed_type_alerts(db, ctx):
    a1 = _create_alert(db, alert_type="low_stock", severity="warning", entity_id=4100)
    a2 = _create_alert(
        db, alert_type="expiring_soon", severity="warning", entity_id=4101
    )
    ctx["type_alerts"] = [a1, a2]


@given("alerts of different severities exist")
def create_mixed_severity_alerts(db, ctx):
    a1 = _create_alert(db, alert_type="expired", severity="critical", entity_id=4200)
    a2 = _create_alert(db, alert_type="low_stock", severity="warning", entity_id=4201)
    a3 = _create_alert(db, alert_type="pending_review", severity="info", entity_id=4202)
    ctx["severity_alerts"] = [a1, a2, a3]


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("I run the alert check", target_fixture="check_response")
def run_alert_check(api):
    r = api.post("/api/v1/alerts/check")
    assert r.status_code == 200, r.text
    return r.json()


@when("I list active alerts", target_fixture="list_response")
def list_active_alerts(api):
    r = api.get("/api/v1/alerts/", params={"resolved": False})
    assert r.status_code == 200, r.text
    return r.json()


@when("I acknowledge the alert", target_fixture="ack_response")
def acknowledge_alert(api, active_alert):
    r = api.post(f"/api/v1/alerts/{active_alert.id}/acknowledge")
    assert r.status_code == 200, r.text
    return r.json()


@when("I resolve the alert", target_fixture="resolve_response")
def resolve_alert(api, active_alert):
    r = api.post(f"/api/v1/alerts/{active_alert.id}/resolve")
    assert r.status_code == 200, r.text
    return r.json()


@when("I request the alert summary", target_fixture="summary_response")
def request_alert_summary(api):
    r = api.get("/api/v1/alerts/summary")
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I list alerts filtered by type "{alert_type}"'),
    target_fixture="filtered_type_response",
)
def list_alerts_by_type(api, alert_type):
    r = api.get("/api/v1/alerts/", params={"alert_type": alert_type, "resolved": False})
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I list alerts filtered by severity "{severity}"'),
    target_fixture="filtered_severity_response",
)
def list_alerts_by_severity(api, severity):
    r = api.get("/api/v1/alerts/", params={"severity": severity, "resolved": False})
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse("I try to acknowledge alert with id {aid:d}"),
    target_fixture="error_response",
)
def try_ack_missing(api, aid):
    return api.post(f"/api/v1/alerts/{aid}/acknowledge")


@when(
    parsers.parse("I try to resolve alert with id {aid:d}"),
    target_fixture="error_response",
)
def try_resolve_missing(api, aid):
    return api.post(f"/api/v1/alerts/{aid}/resolve")


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("an expiry alert should be created")
def check_expiry_alert_created(check_response):
    assert check_response["new_alerts"] >= 1


@then(parsers.parse('the alert type should be "{alert_type}"'))
def check_alert_type(check_response, alert_type):
    summary = check_response["summary"]
    assert alert_type in summary["by_type"], (
        f"Expected alert_type '{alert_type}' in summary by_type, "
        f"got: {summary['by_type']}"
    )


@then("a low stock alert should be created")
def check_low_stock_alert_created(check_response):
    assert check_response["new_alerts"] >= 1


@then(parsers.parse("I should see {n:d} alerts"))
def check_alert_count(list_response, n):
    assert list_response["total"] == n, (
        f"Expected {n} alerts, got {list_response['total']}"
    )


@then("all alerts should be unresolved")
def check_all_unresolved(list_response):
    for alert in list_response["items"]:
        assert alert["is_resolved"] is False, (
            f"Alert {alert['id']} should be unresolved"
        )


@then("the alert should be acknowledged")
def check_acknowledged(ack_response):
    assert ack_response["is_acknowledged"] is True


@then("the alert should be resolved")
def check_resolved(resolve_response):
    assert resolve_response["is_resolved"] is True


@then("the alert should also be acknowledged")
def check_resolved_also_ack(resolve_response):
    assert resolve_response["is_acknowledged"] is True


@then(parsers.parse("the summary should show {n:d} total active alerts"))
def check_summary_total(summary_response, n):
    assert summary_response["total"] == n, (
        f"Expected {n} total alerts, got {summary_response['total']}"
    )


@then("the summary should break down by type")
def check_summary_breakdown(summary_response):
    by_type = summary_response["by_type"]
    assert len(by_type) > 0, "Expected non-empty by_type breakdown"
    assert "expiring_soon" in by_type
    assert "low_stock" in by_type
    assert "pending_review" in by_type


@then("the check should return 0 new alerts")
def check_zero_new_alerts(check_response):
    assert check_response["new_alerts"] == 0


@then(parsers.parse('all returned alerts should have type "{atype}"'))
def check_all_type(filtered_type_response, atype):
    for item in filtered_type_response["items"]:
        assert item["alert_type"] == atype, (
            f"Expected type '{atype}', got '{item['alert_type']}'"
        )


@then(parsers.parse('all returned alerts should have severity "{sev}"'))
def check_all_severity(filtered_severity_response, sev):
    for item in filtered_severity_response["items"]:
        assert item["severity"] == sev, (
            f"Expected severity '{sev}', got '{item['severity']}'"
        )


@then(parsers.parse("the alert response status should be {code:d}"))
def check_error_status(error_response, code):
    assert error_response.status_code == code, (
        f"Expected status {code}, got {error_response.status_code}: {error_response.text}"
    )
