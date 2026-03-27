"""Test weekly report service and API endpoints."""

from datetime import date, datetime, timedelta, timezone

from lab_manager.models.alert import Alert
from lab_manager.models.consumption import ConsumptionLog
from lab_manager.models.document import Document
from lab_manager.models.equipment import Equipment
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.order import Order, OrderItem
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor
from lab_manager.services.weekly_report import generate_weekly_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WEEK_START = date(2026, 3, 23)  # a Monday
_WEEK_END = date(2026, 3, 30)


def _seed_vendor(db, name="Thermo Fisher"):
    v = Vendor(name=name)
    db.add(v)
    db.flush()
    return v


def _seed_product(db, vendor_id, catalog="A123", name="Antibody X"):
    p = Product(catalog_number=catalog, name=name, vendor_id=vendor_id)
    db.add(p)
    db.flush()
    return p


def _seed_order(db, vendor_id, order_date=None, created_at=None, status="pending"):
    kwargs = {"vendor_id": vendor_id, "status": status}
    if order_date:
        kwargs["order_date"] = order_date
    o = Order(**kwargs)
    if created_at:
        o.created_at = created_at
    db.add(o)
    db.flush()
    return o


def _seed_order_item(db, order_id, qty=1, price=10.0, product_id=None):
    kwargs = {
        "order_id": order_id,
        "catalog_number": "A123",
        "description": "Test item",
        "quantity": qty,
        "unit_price": price,
    }
    if product_id:
        kwargs["product_id"] = product_id
    oi = OrderItem(**kwargs)
    db.add(oi)
    db.flush()
    return oi


def _seed_inventory(db, product_id, qty=10.0, unit="mL"):
    inv = InventoryItem(
        product_id=product_id,
        quantity_on_hand=qty,
        unit=unit,
        status="available",
    )
    db.add(inv)
    db.flush()
    return inv


def _seed_consumption(db, inventory_id, product_id, qty, created_at=None):
    c = ConsumptionLog(
        inventory_id=inventory_id,
        product_id=product_id,
        quantity_used=qty,
        quantity_remaining=0,
        consumed_by="Alice",
        action="consume",
    )
    if created_at:
        c.created_at = created_at
    db.add(c)
    db.flush()
    return c


def _seed_document(db, status="approved", created_at=None):
    now = datetime.now(timezone.utc)
    d = Document(
        file_path=f"uploads/doc_{now.timestamp()}.jpg",
        file_name=f"doc_{now.timestamp()}.jpg",
        status=status,
    )
    if created_at:
        d.created_at = created_at
    db.add(d)
    db.flush()
    return d


def _seed_alert(db, severity="warning", alert_type="low_stock", created_at=None):
    a = Alert(
        alert_type=alert_type,
        severity=severity,
        message="Test alert",
        entity_type="inventory",
        entity_id=1,
    )
    if created_at:
        a.created_at = created_at
    db.add(a)
    db.flush()
    return a


def _seed_equipment(db, name="Centrifuge", status="active", updated_at=None):
    e = Equipment(name=name, status=status)
    if updated_at:
        e.updated_at = updated_at
    db.add(e)
    db.flush()
    return e


def _dt(d: date) -> datetime:
    """Convert a date to a UTC datetime at noon."""
    return datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Tests — service layer (empty database)
# ---------------------------------------------------------------------------


class TestEmptyDatabase:
    """Weekly report on empty database returns zeros."""

    def test_empty_orders(self, db_session):
        report = generate_weekly_report(db_session, week_start=_WEEK_START)
        assert report["new_orders"]["count"] == 0
        assert report["new_orders"]["total_value"] == 0.0
        assert report["new_orders"]["orders"] == []

    def test_empty_consumption(self, db_session):
        report = generate_weekly_report(db_session, week_start=_WEEK_START)
        assert report["inventory_consumed"]["total_consumed"] == 0.0
        assert report["inventory_consumed"]["top_products"] == []

    def test_empty_documents(self, db_session):
        report = generate_weekly_report(db_session, week_start=_WEEK_START)
        docs = report["documents_processed"]
        assert docs["total"] == 0
        assert docs["approved"] == 0
        assert docs["rejected"] == 0
        assert docs["pending"] == 0

    def test_empty_spending(self, db_session):
        report = generate_weekly_report(db_session, week_start=_WEEK_START)
        assert report["spending_by_vendor"]["total_spend"] == 0.0
        assert report["spending_by_vendor"]["vendors"] == []

    def test_empty_alerts(self, db_session):
        report = generate_weekly_report(db_session, week_start=_WEEK_START)
        alerts = report["alerts_triggered"]
        assert alerts["total"] == 0
        assert alerts["unacknowledged"] == 0

    def test_empty_equipment(self, db_session):
        report = generate_weekly_report(db_session, week_start=_WEEK_START)
        eq = report["equipment_status_changes"]
        assert eq["total_changed"] == 0
        assert eq["changes"] == []


# ---------------------------------------------------------------------------
# Tests — service layer (with sample data)
# ---------------------------------------------------------------------------


class TestWithData:
    """Weekly report with data in the reporting window."""

    def test_new_orders_counted(self, db_session):
        v = _seed_vendor(db_session)
        p = _seed_product(db_session, v.id)
        o1 = _seed_order(
            db_session,
            v.id,
            created_at=_dt(_WEEK_START),
            status="pending",
        )
        _seed_order_item(db_session, o1.id, qty=5, price=20.0, product_id=p.id)
        o2 = _seed_order(
            db_session,
            v.id,
            created_at=_dt(_WEEK_START + timedelta(days=2)),
            status="received",
        )
        _seed_order_item(db_session, o2.id, qty=3, price=15.0, product_id=p.id)
        db_session.commit()

        report = generate_weekly_report(db_session, week_start=_WEEK_START)
        assert report["new_orders"]["count"] == 2
        # 5*20 + 3*15 = 145
        assert report["new_orders"]["total_value"] == 145.0

    def test_orders_outside_window_excluded(self, db_session):
        v = _seed_vendor(db_session)
        # Order before the week
        o_before = _seed_order(
            db_session,
            v.id,
            created_at=_dt(_WEEK_START - timedelta(days=1)),
        )
        _seed_order_item(db_session, o_before.id, qty=1, price=100.0)
        # Order after the week
        o_after = _seed_order(
            db_session,
            v.id,
            created_at=_dt(_WEEK_END),
        )
        _seed_order_item(db_session, o_after.id, qty=1, price=200.0)
        db_session.commit()

        report = generate_weekly_report(db_session, week_start=_WEEK_START)
        assert report["new_orders"]["count"] == 0
        assert report["new_orders"]["total_value"] == 0.0

    def test_deleted_orders_excluded(self, db_session):
        v = _seed_vendor(db_session)
        o = _seed_order(
            db_session,
            v.id,
            created_at=_dt(_WEEK_START),
            status="deleted",
        )
        _seed_order_item(db_session, o.id, qty=1, price=50.0)
        db_session.commit()

        report = generate_weekly_report(db_session, week_start=_WEEK_START)
        assert report["new_orders"]["count"] == 0

    def test_consumption_top_products(self, db_session):
        v = _seed_vendor(db_session)
        p1 = _seed_product(db_session, v.id, catalog="P1", name="Product A")
        p2 = _seed_product(db_session, v.id, catalog="P2", name="Product B")
        inv1 = _seed_inventory(db_session, p1.id, qty=100.0)
        inv2 = _seed_inventory(db_session, p2.id, qty=200.0)
        _seed_consumption(
            db_session,
            inv1.id,
            p1.id,
            30.0,
            created_at=_dt(_WEEK_START + timedelta(days=1)),
        )
        _seed_consumption(
            db_session,
            inv1.id,
            p1.id,
            20.0,
            created_at=_dt(_WEEK_START + timedelta(days=2)),
        )
        _seed_consumption(
            db_session,
            inv2.id,
            p2.id,
            10.0,
            created_at=_dt(_WEEK_START + timedelta(days=3)),
        )
        db_session.commit()

        report = generate_weekly_report(db_session, week_start=_WEEK_START)
        consumed = report["inventory_consumed"]
        assert consumed["total_consumed"] == 60.0
        assert len(consumed["top_products"]) == 2
        assert consumed["top_products"][0]["product_name"] == "Product A"
        assert consumed["top_products"][0]["quantity_consumed"] == 50.0

    def test_documents_by_status(self, db_session):
        _seed_document(db_session, status="approved", created_at=_dt(_WEEK_START))
        _seed_document(
            db_session,
            status="approved",
            created_at=_dt(_WEEK_START + timedelta(days=1)),
        )
        _seed_document(
            db_session,
            status="rejected",
            created_at=_dt(_WEEK_START + timedelta(days=2)),
        )
        _seed_document(
            db_session,
            status="pending",
            created_at=_dt(_WEEK_START + timedelta(days=3)),
        )
        _seed_document(
            db_session,
            status="needs_review",
            created_at=_dt(_WEEK_START + timedelta(days=4)),
        )
        db_session.commit()

        report = generate_weekly_report(db_session, week_start=_WEEK_START)
        docs = report["documents_processed"]
        assert docs["total"] == 5
        assert docs["approved"] == 2
        assert docs["rejected"] == 1
        # pending + needs_review = 2
        assert docs["pending"] == 2

    def test_spending_by_vendor(self, db_session):
        v1 = _seed_vendor(db_session, "Vendor A")
        v2 = _seed_vendor(db_session, "Vendor B")
        o1 = _seed_order(db_session, v1.id, created_at=_dt(_WEEK_START))
        _seed_order_item(db_session, o1.id, qty=10, price=5.0)
        o2 = _seed_order(
            db_session, v2.id, created_at=_dt(_WEEK_START + timedelta(days=1))
        )
        _seed_order_item(db_session, o2.id, qty=2, price=50.0)
        db_session.commit()

        report = generate_weekly_report(db_session, week_start=_WEEK_START)
        spending = report["spending_by_vendor"]
        assert spending["total_spend"] == 150.0
        assert len(spending["vendors"]) == 2
        # Vendor B should be first (higher spend: 2*50=100 > 10*5=50)
        assert spending["vendors"][0]["vendor_name"] == "Vendor B"

    def test_alerts_triggered(self, db_session):
        _seed_alert(
            db_session,
            severity="critical",
            alert_type="expired",
            created_at=_dt(_WEEK_START),
        )
        _seed_alert(
            db_session,
            severity="warning",
            alert_type="low_stock",
            created_at=_dt(_WEEK_START + timedelta(days=2)),
        )
        db_session.commit()

        report = generate_weekly_report(db_session, week_start=_WEEK_START)
        alerts = report["alerts_triggered"]
        assert alerts["total"] == 2
        assert alerts["by_severity"]["critical"] == 1
        assert alerts["by_severity"]["warning"] == 1
        assert alerts["by_type"]["expired"] == 1
        assert alerts["by_type"]["low_stock"] == 1
        assert alerts["unacknowledged"] == 2

    def test_alerts_acknowledged_excluded_from_unacknowledged(self, db_session):
        a = _seed_alert(
            db_session,
            severity="info",
            alert_type="pending_review",
            created_at=_dt(_WEEK_START),
        )
        a.is_acknowledged = True
        db_session.commit()

        report = generate_weekly_report(db_session, week_start=_WEEK_START)
        alerts = report["alerts_triggered"]
        assert alerts["total"] == 1
        assert alerts["unacknowledged"] == 0

    def test_equipment_status_changes(self, db_session):
        _seed_equipment(
            db_session,
            name="Centrifuge",
            status="maintenance",
            updated_at=_dt(_WEEK_START + timedelta(days=1)),
        )
        _seed_equipment(
            db_session,
            name="PCR Machine",
            status="active",
            updated_at=_dt(_WEEK_START + timedelta(days=3)),
        )
        db_session.commit()

        report = generate_weekly_report(db_session, week_start=_WEEK_START)
        eq = report["equipment_status_changes"]
        assert eq["total_changed"] == 2
        assert eq["by_status"]["maintenance"] == 1
        assert eq["by_status"]["active"] == 1

    def test_report_period_structure(self, db_session):
        report = generate_weekly_report(db_session, week_start=_WEEK_START)
        assert report["report_period"]["week_start"] == "2026-03-23"
        assert report["report_period"]["week_end"] == "2026-03-30"
        assert "generated_at" in report

    def test_default_week_start(self, db_session):
        report = generate_weekly_report(db_session)
        start = date.fromisoformat(report["report_period"]["week_start"])
        end = date.fromisoformat(report["report_period"]["week_end"])
        assert (end - start).days == 7
        # Should be a Monday
        assert start.weekday() == 0


# ---------------------------------------------------------------------------
# Tests — API endpoints
# ---------------------------------------------------------------------------


class TestWeeklyReportAPI:
    """Test the /api/v1/reports/weekly endpoint."""

    def test_weekly_report_endpoint(self, client):
        resp = client.get("/api/v1/reports/weekly")
        assert resp.status_code == 200
        data = resp.json()
        assert "new_orders" in data
        assert "inventory_consumed" in data
        assert "documents_processed" in data
        assert "spending_by_vendor" in data
        assert "alerts_triggered" in data
        assert "equipment_status_changes" in data
        assert "report_period" in data

    def test_weekly_report_with_date(self, client):
        resp = client.get(
            "/api/v1/reports/weekly",
            params={"week_start": "2026-03-23"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_period"]["week_start"] == "2026-03-23"
        assert data["report_period"]["week_end"] == "2026-03-30"

    def test_weekly_report_pdf_endpoint(self, client):
        resp = client.get(
            "/api/v1/reports/weekly/pdf",
            params={"week_start": "2026-03-23"},
        )
        assert resp.status_code == 200
        assert "attachment" in resp.headers.get("content-disposition", "")
        data = resp.json()
        assert "new_orders" in data

    def test_weekly_report_empty_database(self, client):
        resp = client.get("/api/v1/reports/weekly")
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_orders"]["count"] == 0
        assert data["documents_processed"]["total"] == 0
        assert data["alerts_triggered"]["total"] == 0

    def test_weekly_report_with_data(self, client, db_session):
        v = _seed_vendor(db_session, "BioRad")
        p = _seed_product(db_session, v.id, catalog="B1", name="Buffer")
        o = _seed_order(
            db_session,
            v.id,
            order_date=date(2026, 3, 24),
            created_at=_dt(_WEEK_START + timedelta(days=1)),
            status="received",
        )
        _seed_order_item(db_session, o.id, qty=3, price=25.0, product_id=p.id)
        db_session.commit()

        resp = client.get(
            "/api/v1/reports/weekly",
            params={"week_start": "2026-03-23"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_orders"]["count"] == 1
        assert data["new_orders"]["total_value"] == 75.0
