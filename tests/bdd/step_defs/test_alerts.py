"""Step definitions for alerts and monitoring BDD scenarios."""

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


# --- Scenarios ---


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


# --- Shared state ---


@pytest.fixture
def ctx():
    """Shared context dict for passing data between steps."""
    return {}


# --- Helpers ---


def _create_vendor(db):
    """Create a vendor with a unique name directly in the DB."""
    vendor = Vendor(name=f"Test Vendor {next(_vendor_seq)}")
    db.add(vendor)
    db.flush()
    return vendor


def _create_product(db, vendor_id, catalog_number, min_stock_level=None):
    """Create a product directly in the DB."""
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
    """Create an inventory item directly in the DB."""
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
    """Create an alert directly in the DB."""
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


# --- Given steps ---


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


# --- When steps ---


@when("I run the alert check", target_fixture="check_response")
def run_alert_check(api):
    r = api.post("/api/alerts/check")
    assert r.status_code == 200, r.text
    return r.json()


@when("I list active alerts", target_fixture="list_response")
def list_active_alerts(api):
    r = api.get("/api/alerts/", params={"resolved": False})
    assert r.status_code == 200, r.text
    return r.json()


@when("I acknowledge the alert", target_fixture="ack_response")
def acknowledge_alert(api, active_alert):
    r = api.post(f"/api/alerts/{active_alert.id}/acknowledge")
    assert r.status_code == 200, r.text
    return r.json()


@when("I resolve the alert", target_fixture="resolve_response")
def resolve_alert(api, active_alert):
    r = api.post(f"/api/alerts/{active_alert.id}/resolve")
    assert r.status_code == 200, r.text
    return r.json()


@when("I request the alert summary", target_fixture="summary_response")
def request_alert_summary(api):
    r = api.get("/api/alerts/summary")
    assert r.status_code == 200, r.text
    return r.json()


# --- Then steps ---


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
