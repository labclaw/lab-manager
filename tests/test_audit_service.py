"""Tests for audit service — user context, auditing helpers, and audit log creation."""

from sqlmodel import select

from lab_manager.models.audit import AuditLog, log_change
from lab_manager.models.vendor import Vendor
from lab_manager.services.audit import (
    _is_auditable,
    _snapshot,
    _get_table_name,
    _get_record_id,
    set_current_user,
    get_current_user,
)


class TestCurrentUserContext:
    def test_default_is_none(self):
        set_current_user(None)
        assert get_current_user() is None

    def test_set_and_get(self):
        set_current_user("alice")
        assert get_current_user() == "alice"

    def test_overwrite(self):
        set_current_user("alice")
        set_current_user("bob")
        assert get_current_user() == "bob"

    def test_reset_to_none(self):
        set_current_user("alice")
        set_current_user(None)
        assert get_current_user() is None


class TestIsAuditable:
    def test_vendor_is_auditable(self):
        v = Vendor(name="Test")
        assert _is_auditable(v) is True

    def test_audit_log_not_auditable(self):
        al = AuditLog(table_name="test", record_id=1, action="create")
        assert _is_auditable(al) is False

    def test_plain_object_not_auditable(self):
        assert _is_auditable(object()) is False

    def test_string_not_auditable(self):
        assert _is_auditable("hello") is False

    def test_dict_not_auditable(self):
        assert _is_auditable({}) is False


class TestGetTableName:
    def test_vendor_table_name(self):
        v = Vendor(name="Test")
        assert _get_table_name(v) == "vendors"

    def test_audit_log_table_name(self):
        al = AuditLog(table_name="x", record_id=1, action="create")
        assert _get_table_name(al) == "audit_log"


class TestGetRecordId:
    def test_none_before_flush(self, db_session):
        """Before flushing, Vendor has no PK assigned."""
        v = Vendor(name="Test")
        # Not added to session, so no PK yet
        result = _get_record_id(v)
        assert result is None

    def test_has_id_after_flush(self, db_session):
        v = Vendor(name="Test")
        db_session.add(v)
        db_session.flush()
        assert _get_record_id(v) is not None
        assert isinstance(_get_record_id(v), int)


class TestSnapshot:
    def test_vendor_snapshot(self, db_session):
        v = Vendor(name="TestVendor", website="https://example.com")
        db_session.add(v)
        db_session.flush()

        snap = _snapshot(v)
        assert snap["name"] == "TestVendor"
        assert snap["website"] == "https://example.com"
        # created_at/updated_at/password_hash should be skipped
        assert "created_at" not in snap
        assert "updated_at" not in snap
        assert "password_hash" not in snap


class TestLogChange:
    def test_log_change_creates_entry(self, db_session):
        log_change(
            db_session,
            table_name="vendors",
            record_id=42,
            action="create",
            changed_by="alice",
            changes={"name": {"old": None, "new": "Sigma"}},
        )
        db_session.flush()

        entries = db_session.exec(select(AuditLog)).all()
        assert len(entries) == 1
        entry = entries[0]
        assert entry.table_name == "vendors"
        assert entry.record_id == 42
        assert entry.action == "create"
        assert entry.changed_by == "alice"
        assert entry.changes == {"name": {"old": None, "new": "Sigma"}}

    def test_log_change_default_empty_changes(self, db_session):
        log_change(db_session, "products", 1, "delete", changed_by="bob")
        db_session.flush()

        entries = db_session.exec(select(AuditLog)).all()
        assert len(entries) == 1
        assert entries[0].changes == {}

    def test_log_change_no_user(self, db_session):
        log_change(db_session, "orders", 5, "update")
        db_session.flush()

        entries = db_session.exec(select(AuditLog)).all()
        assert len(entries) == 1
        assert entries[0].changed_by is None


class TestAuditOnCreate:
    """Test that creating a Vendor through a session triggers an audit log entry."""

    def test_create_produces_audit_log(self, db_session):
        set_current_user("test-user")
        v = Vendor(name="AuditTestVendor")
        db_session.add(v)
        db_session.flush()

        # The after_flush event should have created an AuditLog entry
        logs = db_session.exec(select(AuditLog)).all()
        assert len(logs) >= 1

        create_log = next((log for log in logs if log.action == "create"), None)
        assert create_log is not None
        assert create_log.table_name == "vendors"
        assert create_log.changed_by == "test-user"
        assert create_log.changes.get("name") == "AuditTestVendor"
        set_current_user(None)


class TestAuditOnUpdate:
    def test_update_produces_audit_log(self, db_session):
        set_current_user("updater")
        v = Vendor(name="Original")
        db_session.add(v)
        db_session.flush()

        # Clear pending creates
        db_session.expire_all()

        v = db_session.exec(select(Vendor)).first()
        v.name = "Updated"
        db_session.add(v)
        db_session.flush()

        logs = db_session.exec(
            select(AuditLog).where(AuditLog.action == "update")
        ).all()
        assert len(logs) >= 1
        update_log = logs[0]
        assert update_log.changed_by == "updater"
        assert "name" in update_log.changes
        set_current_user(None)


class TestAuditOnDelete:
    def test_delete_produces_audit_log(self, db_session):
        set_current_user("deleter")
        v = Vendor(name="ToDelete")
        db_session.add(v)
        db_session.flush()

        db_session.expire_all()
        v = db_session.exec(select(Vendor)).first()
        db_session.delete(v)
        db_session.flush()

        logs = db_session.exec(
            select(AuditLog).where(AuditLog.action == "delete")
        ).all()
        assert len(logs) >= 1
        assert logs[0].changed_by == "deleter"
        assert logs[0].changes.get("name") == "ToDelete"
        set_current_user(None)
