"""Test automatic audit trail via SQLAlchemy event listeners."""

from lab_manager.models.audit import AuditLog
from lab_manager.models.vendor import Vendor
from lab_manager.services.audit import set_current_user


def test_audit_create(db_session):
    """Creating a record should produce an audit log entry with action='create'."""
    set_current_user("test-user")
    v = Vendor(name="Sigma-Aldrich", aliases=["Merck"])
    db_session.add(v)
    db_session.commit()
    set_current_user(None)

    logs = db_session.query(AuditLog).filter(AuditLog.table_name == "vendors").all()
    assert len(logs) == 1
    entry = logs[0]
    assert entry.action == "create"
    assert entry.changed_by == "test-user"
    assert entry.record_id == v.id
    assert entry.changes["name"] == "Sigma-Aldrich"


def test_audit_update(db_session):
    """Updating a record should produce an audit log entry with action='update'."""
    v = Vendor(name="Sigma")
    db_session.add(v)
    db_session.commit()

    set_current_user("editor")
    v.name = "Sigma-Aldrich"
    db_session.commit()
    set_current_user(None)

    logs = db_session.query(AuditLog).filter(AuditLog.table_name == "vendors", AuditLog.action == "update").all()
    assert len(logs) == 1
    entry = logs[0]
    assert entry.changed_by == "editor"
    assert entry.changes["name"]["old"] == "Sigma"
    assert entry.changes["name"]["new"] == "Sigma-Aldrich"


def test_audit_delete(db_session):
    """Deleting a record should produce an audit log entry with action='delete'."""
    v = Vendor(name="ToDelete")
    db_session.add(v)
    db_session.commit()
    vid = v.id

    set_current_user("admin")
    db_session.delete(v)
    db_session.commit()
    set_current_user(None)

    logs = db_session.query(AuditLog).filter(AuditLog.table_name == "vendors", AuditLog.action == "delete").all()
    assert len(logs) == 1
    entry = logs[0]
    assert entry.record_id == vid
    assert entry.changed_by == "admin"
    assert entry.changes["name"] == "ToDelete"


def test_audit_not_logged_for_audit_log(db_session):
    """AuditLog entries themselves should not trigger further audit entries."""
    v = Vendor(name="Test")
    db_session.add(v)
    db_session.commit()

    # We should have exactly 1 audit log (for the vendor create), not 2.
    count = db_session.query(AuditLog).count()
    assert count == 1


def test_audit_api_list(client):
    """GET /api/audit should return paginated audit logs."""
    # Create a vendor to generate an audit entry
    client.post("/api/vendors/", json={"name": "AuditVendor"})

    resp = client.get("/api/audit/")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 1


def test_audit_api_record_history(client):
    """GET /api/audit/{table}/{record_id} returns history for a specific record."""
    resp = client.post("/api/vendors/", json={"name": "HistoryVendor"})
    vendor_id = resp.json()["id"]

    # Update it
    client.patch(f"/api/vendors/{vendor_id}", json={"name": "HistoryVendor Updated"})

    resp = client.get(f"/api/audit/vendors/{vendor_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2  # create + update


def test_audit_api_filter_by_action(client):
    """GET /api/audit?action=create should filter correctly."""
    client.post("/api/vendors/", json={"name": "FilterVendor"})
    resp = client.get("/api/audit/", params={"action": "create"})
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["action"] == "create"


def test_audit_middleware_xuser(client):
    """X-User header should be captured as changed_by in audit logs."""
    resp = client.post(
        "/api/vendors/",
        json={"name": "HeaderVendor"},
        headers={"X-User": "jane.doe"},
    )
    assert resp.status_code == 201
    vendor_id = resp.json()["id"]

    resp = client.get(f"/api/audit/vendors/{vendor_id}")
    data = resp.json()
    assert data["total"] >= 1
    assert data["items"][0]["changed_by"] == "jane.doe"
