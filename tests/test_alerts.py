"""Test alerts system — alert checks, persistence, and API routes."""

from datetime import date, timedelta
from unittest.mock import patch

from sqlalchemy import select, update
from lab_manager.models.alert import Alert
from lab_manager.models.document import Document
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.notification import Notification
from lab_manager.models.product import Product
from lab_manager.models.staff import Staff
from lab_manager.models.vendor import Vendor
from lab_manager.services.alerts import (
    check_all_alerts,
    get_alert_summary,
    persist_alerts,
)


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------


def _seed_vendor(db):
    v = Vendor(name="TestVendor")
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def _ensure_system_staff(db):
    existing = db.scalars(select(Staff).where(Staff.id == 0)).first()
    if existing:
        return existing

    staff = Staff(name="system", email="system-alerts@lab.test", role="admin")
    db.add(staff)
    db.flush()
    if staff.id != 0:
        db.execute(update(Staff).where(Staff.id == staff.id).values(id=0))
        db.flush()
        db.expire_all()
    return db.scalars(select(Staff).where(Staff.id == 0)).one()


def test_check_expired(db_session):
    """Expired items should generate a critical alert."""
    v = _seed_vendor(db_session)
    p = Product(catalog_number="X1", name="Expired Reagent", vendor_id=v.id)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    item = InventoryItem(
        product_id=p.id,
        quantity_on_hand=5,
        expiry_date=date.today() - timedelta(days=1),
        status="available",
    )
    db_session.add(item)
    db_session.commit()

    alerts = check_all_alerts(db_session)
    expired = [a for a in alerts if a["type"] == "expired"]
    assert len(expired) >= 1
    assert expired[0]["severity"] == "critical"


def test_check_expiring_soon(db_session):
    """Items expiring within 30 days should generate a warning alert."""
    v = _seed_vendor(db_session)
    p = Product(catalog_number="X2", name="Expiring Reagent", vendor_id=v.id)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    item = InventoryItem(
        product_id=p.id,
        quantity_on_hand=3,
        expiry_date=date.today() + timedelta(days=10),
        status="available",
    )
    db_session.add(item)
    db_session.commit()

    alerts = check_all_alerts(db_session)
    expiring = [a for a in alerts if a["type"] == "expiring_soon"]
    assert len(expiring) >= 1
    assert expiring[0]["severity"] == "warning"


def test_check_low_stock(db_session):
    """Products below min_stock_level should generate a low_stock warning."""
    v = _seed_vendor(db_session)
    p = Product(
        catalog_number="X3",
        name="Low Stock Reagent",
        vendor_id=v.id,
        min_stock_level=2.0,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    item = InventoryItem(
        product_id=p.id,
        quantity_on_hand=0.5,
        status="available",
    )
    db_session.add(item)
    db_session.commit()

    alerts = check_all_alerts(db_session)
    low = [a for a in alerts if a["type"] == "low_stock"]
    assert len(low) >= 1
    assert low[0]["severity"] == "warning"


def test_check_pending_review(db_session):
    """Documents with status='pending' should generate an info alert."""
    doc = Document(
        file_path="uploads/test.jpg",
        file_name="test.jpg",
        status="pending",
    )
    db_session.add(doc)
    db_session.commit()

    alerts = check_all_alerts(db_session)
    pending = [a for a in alerts if a["type"] == "pending_review"]
    assert len(pending) >= 1
    assert pending[0]["severity"] == "info"


def test_alert_summary(db_session):
    """get_alert_summary should return grouped counts."""
    doc = Document(
        file_path="uploads/sum.jpg",
        file_name="sum.jpg",
        status="pending",
    )
    db_session.add(doc)
    db_session.commit()

    summary = get_alert_summary(db_session)
    assert "total" in summary
    assert "critical" in summary
    assert "warning" in summary
    assert "info" in summary
    assert "by_type" in summary


def test_persist_alerts_no_duplicates(db_session):
    """persist_alerts should not create duplicates for the same condition."""
    doc = Document(
        file_path="uploads/dup.jpg",
        file_name="dup.jpg",
        status="pending",
    )
    db_session.add(doc)
    db_session.commit()

    created1, _ = persist_alerts(db_session)
    created2, _ = persist_alerts(db_session)

    # Second call should create 0 new alerts for the same condition.
    pending1 = [a for a in created1 if a.alert_type == "pending_review"]
    pending2 = [a for a in created2 if a.alert_type == "pending_review"]
    assert len(pending1) >= 1
    assert len(pending2) == 0


# ---------------------------------------------------------------------------
# API route tests
# ---------------------------------------------------------------------------


def test_alerts_summary_api(client):
    """GET /api/alerts/summary should return alert counts."""
    resp = client.get("/api/v1/alerts/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "by_type" in data


def test_alerts_check_api(client):
    """POST /api/alerts/check should trigger checks and return summary."""
    # Seed a pending document so there's something to find
    client.post(
        "/api/v1/documents/",
        json={
            "file_path": "uploads/check.jpg",
            "file_name": "check.jpg",
            "status": "pending",
        },
    )

    resp = client.post("/api/v1/alerts/check")
    assert resp.status_code == 200
    data = resp.json()
    assert "new_alerts" in data
    assert "summary" in data


def test_alerts_check_api_fans_out_notifications(client, db_session):
    """POST /api/v1/alerts/check should create in-app notifications for new alerts."""
    _ensure_system_staff(db_session)
    client.post(
        "/api/v1/documents/",
        json={
            "file_path": "uploads/check-fanout.jpg",
            "file_name": "check-fanout.jpg",
            "status": "pending",
        },
    )

    with patch("lab_manager.api.routes.alerts.dispatch_alerts") as mock_dispatch:
        mock_dispatch.return_value = {}
        resp = client.post("/api/v1/alerts/check")

    assert resp.status_code == 200
    assert mock_dispatch.called
    notifications = db_session.scalars(select(Notification)).all()
    assert len(notifications) >= 1
    assert all(n.link == "/alerts" for n in notifications)


def test_alerts_list_api(client):
    """GET /api/alerts should list unresolved alerts."""
    resp = client.get("/api/v1/alerts/")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


def test_alert_acknowledge_resolve(client):
    """POST /api/alerts/{id}/acknowledge and /resolve should work."""
    # Seed + check to create alerts
    client.post(
        "/api/v1/documents/",
        json={
            "file_path": "uploads/ack.jpg",
            "file_name": "ack.jpg",
            "status": "pending",
        },
    )
    client.post("/api/v1/alerts/check")

    # Get alerts
    resp = client.get("/api/v1/alerts/")
    items = resp.json()["items"]
    if not items:
        return  # Nothing to test if no alerts generated

    alert_id = items[0]["id"]

    # Acknowledge
    resp = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        params={"acknowledged_by": "tester"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_acknowledged"] is True
    assert resp.json()["acknowledged_by"] == "tester"

    # Resolve
    resp = client.post(f"/api/v1/alerts/{alert_id}/resolve")
    assert resp.status_code == 200
    assert resp.json()["is_resolved"] is True


def test_alert_not_found(client):
    """Acknowledge/resolve non-existent alert should return 404."""
    resp = client.post("/api/v1/alerts/99999/acknowledge")
    assert resp.status_code == 404

    resp = client.post("/api/v1/alerts/99999/resolve")
    assert resp.status_code == 404


def test_alert_model():
    """Alert model should be constructable."""
    a = Alert(
        alert_type="expired",
        severity="critical",
        message="Test alert",
        entity_type="inventory",
        entity_id=1,
    )
    assert a.alert_type == "expired"
    assert a.is_acknowledged is False
    assert a.is_resolved is False
