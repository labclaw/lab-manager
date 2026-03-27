"""Test unified Decision Queue endpoint."""

from lab_manager.models.alert import Alert
from lab_manager.models.document import Document
from lab_manager.models.order_request import OrderRequest


def _seed_order_request(db, **overrides):
    defaults = {
        "requested_by": 1,
        "description": "Test reagent",
        "quantity": 5,
        "status": "pending",
    }
    defaults.update(overrides)
    req = OrderRequest(**defaults)
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def _seed_document(db, **overrides):
    defaults = {
        "file_path": "/tmp/test.pdf",
        "file_name": "test.pdf",
        "status": "needs_review",
    }
    defaults.update(overrides)
    doc = Document(**defaults)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _seed_alert(db, **overrides):
    defaults = {
        "alert_type": "expired",
        "severity": "critical",
        "message": "Item expired",
        "entity_type": "inventory",
        "entity_id": 1,
    }
    defaults.update(overrides)
    alert = Alert(**defaults)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


# ---------------------------------------------------------------------------
# API route tests
# ---------------------------------------------------------------------------


def test_queue_returns_combined_items(client, db_session):
    """Queue combines order requests, documents, and alerts."""
    _seed_order_request(db_session)
    _seed_document(db_session)
    _seed_alert(db_session)

    r = client.get("/api/v1/queue/")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert data["counts"]["order_requests"] == 1
    assert data["counts"]["documents"] == 1
    assert data["counts"]["alerts"] == 1


def test_queue_returns_empty_when_no_items(client, db_session):
    """Queue returns empty list when nothing needs attention."""
    r = client.get("/api/v1/queue/")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_queue_priority_ordering(client, db_session):
    """Items are ordered by priority: HIGH > MEDIUM > LOW."""
    # LOW priority (document)
    _seed_document(db_session, file_name="low.pdf", file_path="/tmp/low.pdf")
    # HIGH priority (critical alert)
    _seed_alert(db_session, alert_type="expired", severity="critical", message="high")
    # MEDIUM priority (pending request)
    _seed_order_request(db_session, description="medium")

    r = client.get("/api/v1/queue/")
    data = r.json()
    assert data["total"] == 3
    priorities = [item["priority"] for item in data["items"]]
    # HIGH should come first, then MEDIUM, then LOW
    assert priorities[0] == "HIGH"
    assert priorities[1] == "MEDIUM"
    assert priorities[2] == "LOW"


def test_queue_filter_by_type(client, db_session):
    """Filtering by item_type returns only that type."""
    _seed_order_request(db_session)
    _seed_document(db_session)
    _seed_alert(db_session)

    r = client.get("/api/v1/queue/?item_type=alert")
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["type"] == "alert"

    r = client.get("/api/v1/queue/?item_type=order_request")
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["type"] == "order_request"

    r = client.get("/api/v1/queue/?item_type=document")
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["type"] == "document"


def test_queue_filter_by_priority(client, db_session):
    """Filtering by priority returns only that priority."""
    _seed_alert(db_session, severity="critical", message="high alert")
    _seed_document(db_session, file_name="low.pdf", file_path="/tmp/low.pdf")

    r = client.get("/api/v1/queue/?priority=HIGH")
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["priority"] == "HIGH"

    r = client.get("/api/v1/queue/?priority=LOW")
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["priority"] == "LOW"


def test_queue_excludes_non_pending_requests(client, db_session):
    """Only pending order requests appear in the queue."""
    _seed_order_request(db_session, status="pending")
    _seed_order_request(db_session, description="approved", status="approved")
    _seed_order_request(db_session, description="rejected", status="rejected")

    r = client.get("/api/v1/queue/")
    data = r.json()
    assert data["counts"]["order_requests"] == 1


def test_queue_excludes_non_needs_review_documents(client, db_session):
    """Only documents with status=needs_review appear in the queue."""
    _seed_document(db_session, status="needs_review")
    _seed_document(
        db_session,
        file_name="approved.pdf",
        file_path="/tmp/approved.pdf",
        status="approved",
    )

    r = client.get("/api/v1/queue/")
    data = r.json()
    assert data["counts"]["documents"] == 1


def test_queue_excludes_resolved_alerts(client, db_session):
    """Only unresolved alerts appear in the queue."""
    _seed_alert(db_session, message="unresolved")
    _seed_alert(db_session, message="resolved", is_resolved=True)

    r = client.get("/api/v1/queue/")
    data = r.json()
    assert data["counts"]["alerts"] == 1


def test_queue_item_schema(client, db_session):
    """Each queue item has the expected fields."""
    _seed_alert(db_session)

    r = client.get("/api/v1/queue/")
    data = r.json()
    item = data["items"][0]
    assert "id" in item
    assert "type" in item
    assert "priority" in item
    assert "title" in item
    assert "description" in item
    assert "created_at" in item
    assert "action_url" in item


def test_queue_alert_severity_mapping(client, db_session):
    """Critical alerts and expired/out_of_stock alerts are HIGH priority."""
    _seed_alert(
        db_session,
        alert_type="expired",
        severity="critical",
        message="expired critical",
    )
    _seed_alert(
        db_session,
        alert_type="out_of_stock",
        severity="warning",
        message="out of stock warning",
    )
    _seed_alert(
        db_session,
        alert_type="low_stock",
        severity="info",
        message="low stock info",
    )

    r = client.get("/api/v1/queue/")
    data = r.json()
    assert data["total"] == 3

    # expired + critical = HIGH, out_of_stock = HIGH, low_stock info = MEDIUM
    high_items = [i for i in data["items"] if i["priority"] == "HIGH"]
    medium_items = [i for i in data["items"] if i["priority"] == "MEDIUM"]
    assert len(high_items) == 2
    assert len(medium_items) == 1
