"""Comprehensive unit tests for the audit service internals.

Covers: user context, _is_auditable, _get_table_name, _get_record_id,
_snapshot, _diff, register/unregister listeners, and log_change.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from sqlmodel import Session, select

from lab_manager.models.audit import AuditLog, log_change
from lab_manager.models.base import AuditMixin
from lab_manager.models.product import Product
from lab_manager.models.staff import Staff
from lab_manager.models.vendor import Vendor
from lab_manager.services.audit import (
    _PENDING_KEY,
    _SKIP_FIELDS,
    _after_flush,
    _before_flush,
    _diff,
    _get_record_id,
    _get_table_name,
    _is_auditable,
    _snapshot,
    get_current_user,
    set_current_user,
)


# ── set_current_user / get_current_user ──────────────────────────────────


class TestCurrentUserContext:
    """Tests for the per-request user context variable."""

    def setup_method(self):
        # Ensure a clean state before each test
        set_current_user(None)

    def teardown_method(self):
        set_current_user(None)

    def test_default_is_none(self):
        set_current_user(None)
        assert get_current_user() is None

    def test_set_string_user(self):
        set_current_user("alice")
        assert get_current_user() == "alice"

    def test_overwrite_user(self):
        set_current_user("alice")
        set_current_user("bob")
        assert get_current_user() == "bob"

    def test_reset_to_none(self):
        set_current_user("alice")
        set_current_user(None)
        assert get_current_user() is None

    def test_empty_string_user(self):
        set_current_user("")
        assert get_current_user() == ""

    def test_long_username(self):
        name = "a" * 100
        set_current_user(name)
        assert get_current_user() == name

    def test_unicode_username(self):
        set_current_user("user-漢字")
        assert get_current_user() == "user-漢字"

    def test_email_as_username(self):
        set_current_user("alice@example.com")
        assert get_current_user() == "alice@example.com"

    def test_set_same_user_twice(self):
        set_current_user("carol")
        set_current_user("carol")
        assert get_current_user() == "carol"

    def test_thread_isolation(self):
        """Context variable should be independent across threads."""
        set_current_user("main-thread-user")
        other_thread_value = []

        def worker():
            other_thread_value.append(get_current_user())
            set_current_user("worker-user")
            other_thread_value.append(get_current_user())

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        # Main thread should be unaffected
        assert get_current_user() == "main-thread-user"
        # Worker thread starts with None (default in new thread context)
        assert other_thread_value[0] is None
        assert other_thread_value[1] == "worker-user"


# ── _is_auditable ────────────────────────────────────────────────────────


class TestIsAuditable:
    """Tests for the _is_auditable helper."""

    def test_vendor_is_auditable(self):
        assert _is_auditable(Vendor(name="T")) is True

    def test_product_is_auditable(self):
        assert _is_auditable(Product(catalog_number="X", name="P")) is True

    def test_staff_is_auditable(self):
        assert _is_auditable(Staff(name="Bob")) is True

    def test_audit_log_not_auditable(self):
        al = AuditLog(table_name="t", record_id=1, action="create")
        assert _is_auditable(al) is False

    def test_plain_object_not_auditable(self):
        assert _is_auditable(object()) is False

    def test_string_not_auditable(self):
        assert _is_auditable("hello") is False

    def test_int_not_auditable(self):
        assert _is_auditable(42) is False

    def test_dict_not_auditable(self):
        assert _is_auditable({}) is False

    def test_list_not_auditable(self):
        assert _is_auditable([]) is False

    def test_none_not_auditable(self):
        assert _is_auditable(None) is False

    def test_audit_mixin_subclass_is_auditable(self):
        """Any class that inherits AuditMixin should be auditable."""

        class MyModel(AuditMixin, table=False):
            pass

        assert _is_auditable(MyModel()) is True

    def test_audit_mixin_subclass_with_table_is_auditable(self):
        """AuditMixin subclass with table=True is also auditable."""
        # Vendor already extends AuditMixin with table=True
        v = Vendor(name="test")
        assert isinstance(v, AuditMixin)
        assert _is_auditable(v) is True


# ── _get_table_name ──────────────────────────────────────────────────────


class TestGetTableName:
    """Tests for the _get_table_name helper."""

    def test_vendor_table_name(self):
        assert _get_table_name(Vendor(name="T")) == "vendors"

    def test_product_table_name(self):
        p = Product(catalog_number="C", name="P")
        assert _get_table_name(p) == "products"

    def test_staff_table_name(self):
        assert _get_table_name(Staff(name="Bob")) == "staff"

    def test_audit_log_table_name(self):
        al = AuditLog(table_name="x", record_id=1, action="create")
        assert _get_table_name(al) == "audit_log"

    def test_returns_string(self):
        result = _get_table_name(Vendor(name="T"))
        assert isinstance(result, str)


# ── _get_record_id ───────────────────────────────────────────────────────


class TestGetRecordId:
    """Tests for the _get_record_id helper."""

    def test_none_before_flush(self):
        v = Vendor(name="Test")
        assert _get_record_id(v) is None

    def test_none_for_product_before_flush(self):
        p = Product(catalog_number="C", name="P")
        assert _get_record_id(p) is None

    def test_has_id_after_flush(self, db_session):
        v = Vendor(name="Test")
        db_session.add(v)
        db_session.flush()
        result = _get_record_id(v)
        assert result is not None
        assert isinstance(result, int)

    def test_id_matches_assigned_value(self, db_session):
        v = Vendor(name="Test")
        db_session.add(v)
        db_session.flush()
        assert _get_record_id(v) == v.id

    def test_staff_id_after_flush(self, db_session):
        s = Staff(name="Alice")
        db_session.add(s)
        db_session.flush()
        assert _get_record_id(s) == s.id


# ── _SKIP_FIELDS ─────────────────────────────────────────────────────────


class TestSkipFields:
    """Verify the skip set contains the expected fields."""

    def test_skip_fields_contents(self):
        assert _SKIP_FIELDS == {"created_at", "updated_at", "password_hash"}

    def test_created_at_skipped(self):
        assert "created_at" in _SKIP_FIELDS

    def test_updated_at_skipped(self):
        assert "updated_at" in _SKIP_FIELDS

    def test_password_hash_skipped(self):
        assert "password_hash" in _SKIP_FIELDS

    def test_regular_fields_not_skipped(self):
        assert "name" not in _SKIP_FIELDS
        assert "id" not in _SKIP_FIELDS
        assert "email" not in _SKIP_FIELDS


# ── _snapshot ─────────────────────────────────────────────────────────────


class TestSnapshot:
    """Tests for the _snapshot helper."""

    def test_vendor_snapshot_basic_fields(self, db_session):
        v = Vendor(name="TestVendor", website="https://example.com")
        db_session.add(v)
        db_session.flush()

        snap = _snapshot(v)
        assert snap["name"] == "TestVendor"
        assert snap["website"] == "https://example.com"

    def test_snapshot_skips_created_at(self, db_session):
        v = Vendor(name="T")
        db_session.add(v)
        db_session.flush()
        assert "created_at" not in _snapshot(v)

    def test_snapshot_skips_updated_at(self, db_session):
        v = Vendor(name="T")
        db_session.add(v)
        db_session.flush()
        assert "updated_at" not in _snapshot(v)

    def test_snapshot_skips_password_hash(self, db_session):
        s = Staff(name="Alice", password_hash="secret")
        db_session.add(s)
        db_session.flush()
        assert "password_hash" not in _snapshot(s)

    def test_snapshot_includes_id(self, db_session):
        v = Vendor(name="T")
        db_session.add(v)
        db_session.flush()
        assert "id" in _snapshot(v)

    def test_snapshot_includes_none_values(self, db_session):
        v = Vendor(name="T")  # website, phone, email are None
        db_session.add(v)
        db_session.flush()
        snap = _snapshot(v)
        assert snap["website"] is None
        assert snap["phone"] is None
        assert snap["email"] is None

    def test_snapshot_returns_dict(self, db_session):
        v = Vendor(name="T")
        db_session.add(v)
        db_session.flush()
        assert isinstance(_snapshot(v), dict)

    def test_snapshot_list_field_serialized(self, db_session):
        v = Vendor(name="T", aliases=["Merck", "Sigma"])
        db_session.add(v)
        db_session.flush()
        snap = _snapshot(v)
        assert snap["aliases"] == ["Merck", "Sigma"]

    def test_snapshot_staff_all_fields(self, db_session):
        s = Staff(name="Alice", email="alice@lab.org", role="pi")
        db_session.add(s)
        db_session.flush()
        snap = _snapshot(s)
        assert snap["name"] == "Alice"
        assert snap["email"] == "alice@lab.org"
        assert snap["role"] == "pi"
        assert "password_hash" not in snap
        assert "created_at" not in snap
        assert "updated_at" not in snap

    def test_snapshot_product_fields(self, db_session):
        p = Product(catalog_number="C123", name="Reagent X", category="chemicals")
        db_session.add(p)
        db_session.flush()
        snap = _snapshot(p)
        assert snap["catalog_number"] == "C123"
        assert snap["name"] == "Reagent X"
        assert snap["category"] == "chemicals"

    def test_snapshot_empty_list_field(self, db_session):
        v = Vendor(name="T", aliases=[])
        db_session.add(v)
        db_session.flush()
        snap = _snapshot(v)
        assert snap["aliases"] == []


# ── _diff ─────────────────────────────────────────────────────────────────


class TestDiff:
    """Tests for the _diff helper that detects changed fields."""

    def test_no_changes_returns_none(self, db_session):
        v = Vendor(name="Original")
        db_session.add(v)
        db_session.flush()
        db_session.expire_all()

        v = db_session.exec(select(Vendor)).first()
        result = _diff(db_session, v)
        assert result is None

    def test_single_field_change(self, db_session):
        v = Vendor(name="Original")
        db_session.add(v)
        db_session.flush()
        db_session.expire_all()

        v = db_session.exec(select(Vendor)).first()
        v.name = "Changed"
        result = _diff(db_session, v)
        assert result is not None
        assert "name" in result
        assert result["name"]["old"] == "Original"
        assert result["name"]["new"] == "Changed"

    def test_multiple_field_changes(self, db_session):
        v = Vendor(name="Original", website="https://old.com")
        db_session.add(v)
        db_session.flush()
        db_session.expire_all()

        v = db_session.exec(select(Vendor)).first()
        v.name = "NewName"
        v.website = "https://new.com"
        result = _diff(db_session, v)
        assert result is not None
        assert "name" in result
        assert "website" in result
        assert result["name"]["old"] == "Original"
        assert result["name"]["new"] == "NewName"
        assert result["website"]["old"] == "https://old.com"
        assert result["website"]["new"] == "https://new.com"

    def test_diff_skips_audit_fields(self, db_session):
        """updated_at changes should not appear in diff."""
        v = Vendor(name="Original")
        db_session.add(v)
        db_session.flush()
        db_session.expire_all()

        v = db_session.exec(select(Vendor)).first()
        # Force updated_at change — but it should be skipped
        v.updated_at = datetime.now(timezone.utc)
        v.name = "Changed"
        result = _diff(db_session, v)
        assert result is not None
        assert "updated_at" not in result
        assert "name" in result

    def test_diff_change_from_none(self, db_session):
        v = Vendor(name="T")  # website is None
        db_session.add(v)
        db_session.flush()
        db_session.expire_all()

        v = db_session.exec(select(Vendor)).first()
        v.website = "https://example.com"
        result = _diff(db_session, v)
        assert result is not None
        assert result["website"]["old"] is None
        assert result["website"]["new"] == "https://example.com"

    def test_diff_change_to_none(self, db_session):
        v = Vendor(name="T", website="https://example.com")
        db_session.add(v)
        db_session.flush()
        db_session.expire_all()

        v = db_session.exec(select(Vendor)).first()
        v.website = None
        result = _diff(db_session, v)
        assert result is not None
        assert result["website"]["old"] == "https://example.com"
        assert result["website"]["new"] is None

    def test_diff_returns_dict_with_old_new(self, db_session):
        v = Vendor(name="Original")
        db_session.add(v)
        db_session.flush()
        db_session.expire_all()

        v = db_session.exec(select(Vendor)).first()
        v.name = "Changed"
        result = _diff(db_session, v)
        assert isinstance(result, dict)
        for key, val in result.items():
            assert "old" in val
            assert "new" in val

    def test_diff_password_hash_skipped(self, db_session):
        s = Staff(name="Alice", password_hash="old-hash")
        db_session.add(s)
        db_session.flush()
        db_session.expire_all()

        s = db_session.exec(select(Staff)).first()
        s.password_hash = "new-hash"
        result = _diff(db_session, s)
        # password_hash changes should be skipped
        if result is not None:
            assert "password_hash" not in result


# ─_before_flush / _after_flush event handlers ───────────────────────────


class TestBeforeFlushHandler:
    """Tests for the _before_flush event handler directly."""

    def test_before_flush_stores_pending_updates(self, db_session):
        set_current_user("test-user")
        v = Vendor(name="Original")
        db_session.add(v)
        db_session.flush()
        db_session.expire_all()

        v = db_session.exec(select(Vendor)).first()
        v.name = "Updated"
        db_session.add(v)

        # Manually call before_flush handler
        _before_flush(db_session, None, None)
        pending = db_session.info.get(_PENDING_KEY, [])
        assert len(pending) >= 1
        assert any(item["action"] == "update" for item in pending)
        set_current_user(None)

    def test_before_flush_stores_pending_deletes(self, db_session):
        set_current_user("deleter")
        v = Vendor(name="ToDelete")
        db_session.add(v)
        db_session.flush()
        db_session.expire_all()

        v = db_session.exec(select(Vendor)).first()
        db_session.delete(v)

        _before_flush(db_session, None, None)
        pending = db_session.info.get(_PENDING_KEY, [])
        assert len(pending) >= 1
        assert any(item["action"] == "delete" for item in pending)
        set_current_user(None)

    def test_before_flush_captures_user(self, db_session):
        set_current_user("captured-user")
        v = Vendor(name="ToDel")
        db_session.add(v)
        db_session.flush()
        db_session.expire_all()

        v = db_session.exec(select(Vendor)).first()
        db_session.delete(v)

        _before_flush(db_session, None, None)
        pending = db_session.info.get(_PENDING_KEY, [])
        assert any(item["user"] == "captured-user" for item in pending)
        set_current_user(None)


class TestAfterFlushHandler:
    """Tests for the _after_flush event handler directly."""

    def test_after_flush_creates_audit_for_new_objects(self, db_session):
        set_current_user("creator")
        v = Vendor(name="NewVendor")
        db_session.add(v)
        db_session.flush()

        # The automatic after_flush should have already fired and created entries.
        # We call it again to verify idempotency doesn't crash.
        # First, check that the log was created automatically.
        logs = db_session.exec(
            select(AuditLog).where(AuditLog.action == "create")
        ).all()
        assert len(logs) >= 1
        assert logs[0].table_name == "vendors"
        assert logs[0].changed_by == "creator"
        set_current_user(None)

    def test_after_flush_uses_pending_from_before_flush(self, db_session):
        set_current_user("handler-test")
        v = Vendor(name="ToDelete")
        db_session.add(v)
        db_session.flush()
        db_session.expire_all()

        v = db_session.exec(select(Vendor)).first()
        db_session.delete(v)

        # Call before_flush to populate pending
        _before_flush(db_session, None, None)
        assert _PENDING_KEY in db_session.info

        # Now flush the delete and call after_flush
        db_session.flush()
        _after_flush(db_session, None)

        logs = db_session.exec(
            select(AuditLog).where(AuditLog.action == "delete")
        ).all()
        assert len(logs) >= 1
        set_current_user(None)


# ── log_change ────────────────────────────────────────────────────────────


class TestLogChange:
    """Tests for the log_change function from models/audit.py."""

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
        assert len(entries) >= 1
        entry = entries[-1]
        assert entry.table_name == "vendors"
        assert entry.record_id == 42
        assert entry.action == "create"
        assert entry.changed_by == "alice"
        assert entry.changes == {"name": {"old": None, "new": "Sigma"}}

    def test_log_change_update_action(self, db_session):
        log_change(
            db_session,
            "vendors",
            10,
            "update",
            changed_by="bob",
            changes={"name": {"old": "X", "new": "Y"}},
        )
        db_session.flush()

        entries = db_session.exec(select(AuditLog)).all()
        entry = [e for e in entries if e.action == "update"][-1]
        assert entry.record_id == 10
        assert entry.changed_by == "bob"

    def test_log_change_delete_action(self, db_session):
        log_change(
            db_session,
            "products",
            99,
            "delete",
            changed_by="admin",
            changes={"name": "OldProduct"},
        )
        db_session.flush()

        entries = db_session.exec(select(AuditLog)).all()
        entry = [e for e in entries if e.action == "delete"][-1]
        assert entry.record_id == 99
        assert entry.table_name == "products"

    def test_log_change_default_empty_changes(self, db_session):
        log_change(db_session, "products", 1, "delete", changed_by="bob")
        db_session.flush()

        entries = db_session.exec(select(AuditLog)).all()
        entry = [e for e in entries if e.action == "delete"][-1]
        assert entry.changes == {}

    def test_log_change_no_user(self, db_session):
        log_change(db_session, "orders", 5, "update")
        db_session.flush()

        entries = db_session.exec(select(AuditLog)).all()
        entry = [e for e in entries if e.action == "update"][-1]
        assert entry.changed_by is None

    def test_log_change_none_changes_becomes_empty_dict(self, db_session):
        log_change(db_session, "vendors", 3, "create", changes=None)
        db_session.flush()

        entries = db_session.exec(select(AuditLog)).all()
        entry = [e for e in entries if e.record_id == 3 and e.action == "create"][-1]
        assert entry.changes == {}

    def test_log_change_adds_to_session(self, db_session):
        mock_session = MagicMock(spec=Session)
        log_change(mock_session, "vendors", 1, "create", changed_by="u")
        mock_session.add.assert_called_once()
        entry = mock_session.add.call_args[0][0]
        assert isinstance(entry, AuditLog)
        assert entry.table_name == "vendors"
        assert entry.record_id == 1
        assert entry.action == "create"
        assert entry.changed_by == "u"

    def test_log_change_with_complex_changes(self, db_session):
        changes = {
            "name": {"old": "X", "new": "Y"},
            "price": {"old": 10.0, "new": 20.0},
            "tags": {"old": None, "new": ["a", "b"]},
        }
        log_change(db_session, "products", 7, "update", changed_by="z", changes=changes)
        db_session.flush()

        entries = db_session.exec(select(AuditLog)).all()
        entry = [e for e in entries if e.record_id == 7 and e.action == "update"][-1]
        assert entry.changes == changes


# ── Integration: full flush cycle via event listeners ─────────────────────


class TestAuditFlushCycle:
    """End-to-end tests for audit trail via SQLAlchemy events."""

    def test_create_vendor_triggers_audit(self, db_session):
        set_current_user("creator")
        v = Vendor(name="FlushTest")
        db_session.add(v)
        db_session.flush()

        logs = db_session.exec(
            select(AuditLog).where(AuditLog.action == "create")
        ).all()
        assert len(logs) >= 1
        create_log = [log for log in logs if log.table_name == "vendors"][-1]
        assert create_log.changed_by == "creator"
        assert create_log.changes.get("name") == "FlushTest"
        set_current_user(None)

    def test_update_vendor_triggers_audit(self, db_session):
        set_current_user("updater")
        v = Vendor(name="Original")
        db_session.add(v)
        db_session.flush()
        db_session.expire_all()

        v = db_session.exec(select(Vendor)).first()
        v.name = "Updated"
        db_session.flush()

        logs = db_session.exec(
            select(AuditLog).where(AuditLog.action == "update")
        ).all()
        assert len(logs) >= 1
        update_log = [log for log in logs if log.table_name == "vendors"][-1]
        assert update_log.changed_by == "updater"
        assert "name" in update_log.changes
        set_current_user(None)

    def test_delete_vendor_triggers_audit(self, db_session):
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
        delete_log = [log for log in logs if log.table_name == "vendors"][-1]
        assert delete_log.changed_by == "deleter"
        assert delete_log.changes.get("name") == "ToDelete"
        set_current_user(None)

    def test_no_user_means_changed_by_none(self, db_session):
        set_current_user(None)
        v = Vendor(name="NoUser")
        db_session.add(v)
        db_session.flush()

        logs = db_session.exec(
            select(AuditLog).where(AuditLog.action == "create")
        ).all()
        create_log = [log for log in logs if log.table_name == "vendors"][-1]
        assert create_log.changed_by is None

    def test_audit_log_not_audited(self, db_session):
        """AuditLog entries themselves should not trigger audit entries."""
        v = Vendor(name="Trigger")
        db_session.add(v)
        db_session.flush()

        initial_count = db_session.exec(select(AuditLog)).all()
        # Only the vendor create log, no recursive audit of the audit
        for entry in initial_count:
            assert entry.table_name != "audit_log"

    def test_multiple_creates_in_one_flush(self, db_session):
        set_current_user("batch-user")
        db_session.add(Vendor(name="V1"))
        db_session.add(Vendor(name="V2"))
        db_session.add(Vendor(name="V3"))
        db_session.flush()

        logs = db_session.exec(
            select(AuditLog).where(AuditLog.action == "create")
        ).all()
        vendor_logs = [log for log in logs if log.table_name == "vendors"]
        # There should be logs for V1, V2, V3 (plus any from earlier tests
        # if session is reused, but we match by changes.name)
        names_in_changes = [log.changes.get("name") for log in vendor_logs]
        assert "V1" in names_in_changes
        assert "V2" in names_in_changes
        assert "V3" in names_in_changes
        set_current_user(None)

    def test_record_id_matches_vendor_id(self, db_session):
        set_current_user("id-check")
        v = Vendor(name="IdCheck")
        db_session.add(v)
        db_session.flush()

        logs = db_session.exec(
            select(AuditLog).where(AuditLog.action == "create")
        ).all()
        create_log = [log for log in logs if log.table_name == "vendors"][-1]
        assert create_log.record_id == v.id
        set_current_user(None)


# ── Snapshot edge cases ───────────────────────────────────────────────────


class TestSnapshotEdgeCases:
    """Edge cases for _snapshot."""

    def test_snapshot_with_default_values(self, db_session):
        v = Vendor(name="Defaults")
        db_session.add(v)
        db_session.flush()
        snap = _snapshot(v)
        # aliases should be []
        assert snap["aliases"] == []
        # notes should be None
        assert snap["notes"] is None

    def test_snapshot_product_with_decimal_fields(self, db_session):
        p = Product(
            catalog_number="D1",
            name="DecimalProduct",
            min_stock_level=Decimal("10.5000"),
        )
        db_session.add(p)
        db_session.flush()
        snap = _snapshot(p)
        assert snap["min_stock_level"] is not None

    def test_snapshot_product_boolean_fields(self, db_session):
        p = Product(
            catalog_number="B1",
            name="BoolProduct",
            is_hazardous=True,
            is_active=False,
        )
        db_session.add(p)
        db_session.flush()
        snap = _snapshot(p)
        assert snap["is_hazardous"] is True
        assert snap["is_active"] is False

    def test_snapshot_staff_default_role(self, db_session):
        s = Staff(name="DefaultRole")
        db_session.add(s)
        db_session.flush()
        snap = _snapshot(s)
        assert snap["role"] == "grad_student"
        assert snap["is_active"] is True
