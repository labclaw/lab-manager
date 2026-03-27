"""Unit tests for orders service — find_duplicate_po and build_duplicate_warning."""

from sqlmodel import Session

from lab_manager.models.order import Order
from lab_manager.models.vendor import Vendor
from lab_manager.services.orders import build_duplicate_warning, find_duplicate_po


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_vendor(db: Session, name: str = "TestVendor") -> Vendor:
    v = Vendor(name=name)
    db.add(v)
    db.flush()
    return v


def _create_order(
    db: Session,
    *,
    po_number: str | None = "PO-001",
    vendor_id: int | None = None,
    status: str = "pending",
) -> Order:
    o = Order(po_number=po_number, vendor_id=vendor_id, status=status)
    db.add(o)
    db.flush()
    return o


# ===================================================================
# find_duplicate_po
# ===================================================================


class TestFindDuplicatePoEmptyDb:
    """Behaviour when no orders exist in the database."""

    def test_returns_empty_list_when_no_orders(self, db_session: Session):
        result = find_duplicate_po("PO-001", vendor_id=None, db=db_session)
        assert result == []

    def test_empty_po_returns_empty(self, db_session: Session):
        result = find_duplicate_po("", vendor_id=None, db=db_session)
        assert result == []

    def test_whitespace_only_po_returns_empty(self, db_session: Session):
        result = find_duplicate_po("   ", vendor_id=None, db=db_session)
        assert result == []


class TestFindDuplicatePoMatching:
    """Behaviour when matching orders exist."""

    def test_finds_duplicate_by_po_number_only(self, db_session: Session):
        _create_order(db_session, po_number="PO-100")
        result = find_duplicate_po("PO-100", vendor_id=None, db=db_session)
        assert len(result) == 1
        assert result[0].po_number == "PO-100"

    def test_finds_duplicate_with_vendor_id(self, db_session: Session):
        v = _create_vendor(db_session)
        _create_order(db_session, po_number="PO-200", vendor_id=v.id)
        result = find_duplicate_po("PO-200", vendor_id=v.id, db=db_session)
        assert len(result) == 1

    def test_no_duplicate_different_vendor(self, db_session: Session):
        v1 = _create_vendor(db_session, name="V1")
        v2 = _create_vendor(db_session, name="V2")
        _create_order(db_session, po_number="PO-300", vendor_id=v1.id)
        result = find_duplicate_po("PO-300", vendor_id=v2.id, db=db_session)
        assert result == []

    def test_vendor_none_matches_any_vendor(self, db_session: Session):
        v = _create_vendor(db_session)
        _create_order(db_session, po_number="PO-400", vendor_id=v.id)
        result = find_duplicate_po("PO-400", vendor_id=None, db=db_session)
        assert len(result) == 1

    def test_multiple_duplicates_found(self, db_session: Session):
        v = _create_vendor(db_session)
        _create_order(db_session, po_number="PO-500", vendor_id=v.id)
        _create_order(db_session, po_number="PO-500", vendor_id=None)
        result = find_duplicate_po("PO-500", vendor_id=None, db=db_session)
        assert len(result) == 2

    def test_po_number_trimmed(self, db_session: Session):
        _create_order(db_session, po_number="PO-600")
        result = find_duplicate_po("  PO-600  ", vendor_id=None, db=db_session)
        assert len(result) == 1

    def test_case_sensitive_matching(self, db_session: Session):
        _create_order(db_session, po_number="po-700")
        result = find_duplicate_po("PO-700", vendor_id=None, db=db_session)
        assert result == []


class TestFindDuplicatePoExcludedStatuses:
    """Cancelled and deleted orders are excluded from duplicate checks."""

    def test_cancelled_order_excluded(self, db_session: Session):
        _create_order(db_session, po_number="PO-CX", status="cancelled")
        result = find_duplicate_po("PO-CX", vendor_id=None, db=db_session)
        assert result == []

    def test_deleted_order_excluded(self, db_session: Session):
        _create_order(db_session, po_number="PO-DX", status="deleted")
        result = find_duplicate_po("PO-DX", vendor_id=None, db=db_session)
        assert result == []

    def test_pending_order_included(self, db_session: Session):
        _create_order(db_session, po_number="PO-PX", status="pending")
        result = find_duplicate_po("PO-PX", vendor_id=None, db=db_session)
        assert len(result) == 1

    def test_shipped_order_included(self, db_session: Session):
        _create_order(db_session, po_number="PO-SX", status="shipped")
        result = find_duplicate_po("PO-SX", vendor_id=None, db=db_session)
        assert len(result) == 1

    def test_received_order_included(self, db_session: Session):
        _create_order(db_session, po_number="PO-RX", status="received")
        result = find_duplicate_po("PO-RX", vendor_id=None, db=db_session)
        assert len(result) == 1


class TestFindDuplicatePoExcludeOrderId:
    """exclude_order_id lets callers skip a specific order (used in PATCH)."""

    def test_excludes_specified_order(self, db_session: Session):
        order = _create_order(db_session, po_number="PO-EX")
        result = find_duplicate_po(
            "PO-EX", vendor_id=None, db=db_session, exclude_order_id=order.id
        )
        assert result == []

    def test_does_not_exclude_other_orders(self, db_session: Session):
        o1 = _create_order(db_session, po_number="PO-EX2")
        o2 = _create_order(db_session, po_number="PO-EX2")
        result = find_duplicate_po(
            "PO-EX2", vendor_id=None, db=db_session, exclude_order_id=o1.id
        )
        assert len(result) == 1
        assert result[0].id == o2.id

    def test_exclude_nonexistent_id_still_returns_matches(self, db_session: Session):
        _create_order(db_session, po_number="PO-EX3")
        result = find_duplicate_po(
            "PO-EX3", vendor_id=None, db=db_session, exclude_order_id=99999
        )
        assert len(result) == 1


# ===================================================================
# build_duplicate_warning
# ===================================================================


class TestBuildDuplicateWarning:
    """build_duplicate_warning returns a structured dict."""

    def test_single_duplicate(self, db_session: Session):
        order = _create_order(db_session, po_number="PO-W1")
        result = build_duplicate_warning([order])
        assert result["warning"] == "duplicate_po_number"
        assert "1 order(s)" in result["message"]
        assert result["duplicate_order_ids"] == [order.id]

    def test_multiple_duplicates(self, db_session: Session):
        o1 = _create_order(db_session, po_number="PO-W2")
        o2 = _create_order(db_session, po_number="PO-W2")
        result = build_duplicate_warning([o1, o2])
        assert "2 order(s)" in result["message"]
        assert result["duplicate_order_ids"] == [o1.id, o2.id]

    def test_empty_list(self):
        result = build_duplicate_warning([])
        assert result["warning"] == "duplicate_po_number"
        assert "0 order(s)" in result["message"]
        assert result["duplicate_order_ids"] == []

    def test_returns_dict_with_expected_keys(self, db_session: Session):
        order = _create_order(db_session, po_number="PO-W4")
        result = build_duplicate_warning([order])
        assert set(result.keys()) == {"warning", "message", "duplicate_order_ids"}

    def test_message_mentions_ocr_rescan(self, db_session: Session):
        order = _create_order(db_session, po_number="PO-W5")
        result = build_duplicate_warning([order])
        assert "OCR re-scan" in result["message"]
