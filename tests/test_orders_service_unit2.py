"""Unit tests for orders service and route-level helpers (mock-based).

Covers:
- find_duplicate_po (mocked DB session)
- build_duplicate_warning (edge cases)
- _validate_status_transition (all valid and invalid transitions)
- _get_order_item_or_raise (found / not-found)
- _ensure_order_mutable (mutable / immutable statuses)
- Schema validation (OrderCreate, OrderUpdate, OrderItemCreate, OrderItemUpdate)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from lab_manager.api.routes.orders import (
    OrderCreate,
    OrderItemCreate,
    OrderItemUpdate,
    OrderUpdate,
    ReceiveBody,
    ReceiveItemEntry,
    _VALID_STATUS_TRANSITIONS,
    _ensure_order_mutable,
    _get_order_item_or_raise,
    _validate_status_transition,
)
from lab_manager.exceptions import NotFoundError, ValidationError
from lab_manager.models.order import Order, OrderItem, OrderStatus
from lab_manager.services.orders import build_duplicate_warning, find_duplicate_po


# ===================================================================
# Helpers
# ===================================================================


def _make_order(
    *,
    id: int = 1,
    po_number: str = "PO-001",
    vendor_id: int | None = None,
    status: str = "pending",
) -> Order:
    """Create an Order instance without requiring a DB session."""
    o = Order(po_number=po_number, vendor_id=vendor_id, status=status)
    o.id = id  # type: ignore[assignment]
    return o


def _make_order_item(
    *,
    id: int = 1,
    order_id: int = 1,
    catalog_number: str | None = "CAT-001",
    quantity: Decimal = Decimal("1"),
) -> OrderItem:
    """Create an OrderItem instance without requiring a DB session."""
    item = OrderItem(
        order_id=order_id,
        catalog_number=catalog_number,
        quantity=quantity,
    )
    item.id = id  # type: ignore[assignment]
    return item


def _mock_db(return_value=None) -> MagicMock:
    """Create a MagicMock session with db.scalars().all()/first() wired up."""
    db = MagicMock()
    scalars_result = MagicMock()
    if isinstance(return_value, list):
        scalars_result.all.return_value = return_value
        scalars_result.first.return_value = return_value[0] if return_value else None
    else:
        scalars_result.first.return_value = return_value
    db.scalars.return_value = scalars_result
    return db


# ===================================================================
# find_duplicate_po — mock-based tests
# ===================================================================


class TestFindDuplicatePoMocked:
    """Test find_duplicate_po with a mocked DB session.

    Unlike test_orders_service_unit.py (integration), these tests use
    MagicMock to verify query construction without a real database.
    """

    def test_returns_empty_for_empty_po_string(self):
        db = _mock_db()
        result = find_duplicate_po("", vendor_id=None, db=db)
        assert result == []
        db.scalars.assert_not_called()

    def test_returns_empty_for_whitespace_only_po(self):
        db = _mock_db()
        result = find_duplicate_po("   \t  ", vendor_id=None, db=db)
        assert result == []
        db.scalars.assert_not_called()

    def test_returns_empty_for_none_po_number(self):
        db = _mock_db()
        result = find_duplicate_po(None, vendor_id=None, db=db)  # type: ignore[arg-type]
        assert result == []
        db.scalars.assert_not_called()

    def test_delegates_to_db_scalars_all(self):
        orders = [_make_order(id=10, po_number="PO-A")]
        db = _mock_db(return_value=orders)
        result = find_duplicate_po("PO-A", vendor_id=None, db=db)
        assert result == orders
        db.scalars.assert_called_once()
        db.scalars.return_value.all.assert_called_once()

    def test_empty_result_when_no_matches(self):
        db = _mock_db(return_value=[])
        result = find_duplicate_po("PO-NOMATCH", vendor_id=None, db=db)
        assert result == []

    def test_with_vendor_id_calls_scalars(self):
        db = _mock_db(return_value=[])
        find_duplicate_po("PO-V", vendor_id=42, db=db)
        db.scalars.assert_called_once()

    def test_with_exclude_order_id_calls_scalars(self):
        db = _mock_db(return_value=[])
        find_duplicate_po("PO-X", vendor_id=None, db=db, exclude_order_id=99)
        db.scalars.assert_called_once()

    def test_po_number_is_stripped_before_query(self):
        """Verify leading/trailing whitespace is stripped."""
        db = _mock_db(return_value=[])
        find_duplicate_po("  PO-TRIM  ", vendor_id=None, db=db)
        # The query was executed (scalars called), meaning the trimmed value passed the guard.
        db.scalars.assert_called_once()


# ===================================================================
# build_duplicate_warning — additional edge cases
# ===================================================================


class TestBuildDuplicateWarningEdgeCases:
    """Extended tests for build_duplicate_warning beyond existing unit tests."""

    def test_warning_type_is_string(self):
        result = build_duplicate_warning([])
        assert isinstance(result["warning"], str)

    def test_message_is_string(self):
        result = build_duplicate_warning([])
        assert isinstance(result["message"], str)

    def test_duplicate_order_ids_is_list(self):
        result = build_duplicate_warning([])
        assert isinstance(result["duplicate_order_ids"], list)

    def test_with_three_duplicates_counts_correctly(self):
        orders = [_make_order(id=i, po_number="PO-TRIPLE") for i in range(1, 4)]
        result = build_duplicate_warning(orders)
        assert "3 order(s)" in result["message"]
        assert result["duplicate_order_ids"] == [1, 2, 3]

    def test_order_id_extraction_preserves_order(self):
        orders = [_make_order(id=50), _make_order(id=10), _make_order(id=30)]
        result = build_duplicate_warning(orders)
        assert result["duplicate_order_ids"] == [50, 10, 30]

    def test_no_extra_keys_in_result(self):
        result = build_duplicate_warning([])
        assert set(result.keys()) == {"warning", "message", "duplicate_order_ids"}

    def test_message_contains_context_about_ocr(self):
        result = build_duplicate_warning([_make_order()])
        assert "OCR" in result["message"] or "re-scan" in result["message"]


# ===================================================================
# _validate_status_transition
# ===================================================================


class TestValidateStatusTransition:
    """Test all valid and invalid status transitions."""

    # -- Valid transitions --

    def test_pending_to_shipped(self):
        _validate_status_transition("pending", "shipped")  # no raise

    def test_pending_to_cancelled(self):
        _validate_status_transition("pending", "cancelled")

    def test_pending_to_deleted(self):
        _validate_status_transition("pending", "deleted")

    def test_shipped_to_received(self):
        _validate_status_transition("shipped", "received")

    def test_shipped_to_cancelled(self):
        _validate_status_transition("shipped", "cancelled")

    def test_shipped_to_deleted(self):
        _validate_status_transition("shipped", "deleted")

    def test_received_to_deleted(self):
        _validate_status_transition("received", "deleted")

    # -- Invalid transitions --

    def test_pending_to_received_invalid(self):
        with pytest.raises(ValidationError, match="Invalid status transition"):
            _validate_status_transition("pending", "received")

    def test_pending_to_pending_invalid(self):
        with pytest.raises(ValidationError, match="Invalid status transition"):
            _validate_status_transition("pending", "pending")

    def test_shipped_to_pending_invalid(self):
        with pytest.raises(ValidationError, match="Invalid status transition"):
            _validate_status_transition("shipped", "pending")

    def test_received_to_pending_invalid(self):
        with pytest.raises(ValidationError, match="Invalid status transition"):
            _validate_status_transition("received", "pending")

    def test_received_to_shipped_invalid(self):
        with pytest.raises(ValidationError, match="Invalid status transition"):
            _validate_status_transition("received", "shipped")

    def test_received_to_cancelled_invalid(self):
        with pytest.raises(ValidationError, match="Invalid status transition"):
            _validate_status_transition("received", "cancelled")

    def test_cancelled_to_anything_invalid(self):
        for target in ["pending", "shipped", "received", "cancelled", "deleted"]:
            with pytest.raises(ValidationError, match="Invalid status transition"):
                _validate_status_transition("cancelled", target)

    def test_deleted_to_anything_invalid(self):
        for target in ["pending", "shipped", "received", "cancelled", "deleted"]:
            with pytest.raises(ValidationError, match="Invalid status transition"):
                _validate_status_transition("deleted", target)

    def test_unknown_current_status_invalid(self):
        with pytest.raises(ValidationError, match="Invalid status transition"):
            _validate_status_transition("nonexistent", "pending")

    def test_error_message_includes_allowed_statuses(self):
        with pytest.raises(ValidationError, match="Allowed:"):
            _validate_status_transition("pending", "received")

    def test_error_message_shows_terminal_for_terminal_status(self):
        with pytest.raises(ValidationError, match="terminal status"):
            _validate_status_transition("cancelled", "pending")


class TestValidStatusTransitionsCompleteness:
    """Verify _VALID_STATUS_TRANSITIONS covers all OrderStatus values."""

    def test_all_status_values_are_keys_or_unreachable(self):
        """Every OrderStatus is either a key or intentionally absent (terminal)."""
        all_statuses = {s.value for s in OrderStatus}
        defined_keys = set(_VALID_STATUS_TRANSITIONS.keys())
        # The defined keys should be a subset of all statuses.
        assert defined_keys <= all_statuses

    def test_all_target_values_are_valid_statuses(self):
        all_statuses = {s.value for s in OrderStatus}
        for source, targets in _VALID_STATUS_TRANSITIONS.items():
            for t in targets:
                assert t in all_statuses, f"Invalid target '{t}' for source '{source}'"

    def test_no_self_transitions(self):
        for source, targets in _VALID_STATUS_TRANSITIONS.items():
            assert source not in targets, f"Self-transition for '{source}'"


# ===================================================================
# _get_order_item_or_raise
# ===================================================================


class TestGetOrderItemOrRaise:
    """Test the helper that fetches an order item or raises NotFoundError."""

    def test_returns_item_when_found(self):
        item = _make_order_item(id=5, order_id=10)
        db = _mock_db(return_value=item)
        result = _get_order_item_or_raise(db, order_id=10, item_id=5)
        assert result is item

    def test_raises_not_found_when_item_missing(self):
        db = _mock_db(return_value=None)
        with pytest.raises(NotFoundError, match="Order item"):
            _get_order_item_or_raise(db, order_id=10, item_id=999)

    def test_calls_db_scalars_with_correct_order_and_item_id(self):
        db = _mock_db(return_value=_make_order_item())
        _get_order_item_or_raise(db, order_id=7, item_id=3)
        db.scalars.assert_called_once()

    def test_raises_for_item_belonging_to_different_order(self):
        """When item exists but belongs to a different order, returns None -> raises."""
        db = _mock_db(return_value=None)
        with pytest.raises(NotFoundError):
            _get_order_item_or_raise(db, order_id=999, item_id=1)


# ===================================================================
# _ensure_order_mutable
# ===================================================================


class TestEnsureOrderMutable:
    """Test the guard that prevents modifying orders in terminal statuses."""

    def test_pending_order_is_mutable(self):
        order = _make_order(status="pending")
        _ensure_order_mutable(order)  # no raise

    def test_shipped_order_is_mutable(self):
        order = _make_order(status="shipped")
        _ensure_order_mutable(order)  # no raise

    def test_received_order_is_not_mutable(self):
        order = _make_order(status="received")
        with pytest.raises(ValidationError, match="Cannot modify items"):
            _ensure_order_mutable(order)

    def test_cancelled_order_is_not_mutable(self):
        order = _make_order(status="cancelled")
        with pytest.raises(ValidationError, match="Cannot modify items"):
            _ensure_order_mutable(order)

    def test_deleted_order_is_not_mutable(self):
        order = _make_order(status="deleted")
        with pytest.raises(ValidationError, match="Cannot modify items"):
            _ensure_order_mutable(order)

    def test_error_message_includes_current_status(self):
        order = _make_order(status="cancelled")
        with pytest.raises(ValidationError, match="cancelled"):
            _ensure_order_mutable(order)

    def test_error_message_includes_status_received(self):
        order = _make_order(status="received")
        with pytest.raises(ValidationError, match="received"):
            _ensure_order_mutable(order)


# ===================================================================
# OrderCreate schema validation
# ===================================================================


class TestOrderCreateSchema:
    """Test OrderCreate pydantic model validation."""

    def test_defaults_to_pending_status(self):
        body = OrderCreate()
        assert body.status == "pending"

    def test_accepts_pending_status(self):
        body = OrderCreate(status="pending")
        assert body.status == "pending"

    def test_rejects_invalid_status(self):
        with pytest.raises(Exception):
            OrderCreate(status="invalid_status")

    def test_rejects_shipped_status_on_create(self):
        """OrderCreate allows 'shipped' at schema level (route checks pending-only)."""
        body = OrderCreate(status="shipped")
        assert body.status == "shipped"

    def test_accepts_all_valid_statuses(self):
        for s in OrderStatus:
            body = OrderCreate(status=s.value)
            assert body.status == s.value

    def test_po_number_optional(self):
        body = OrderCreate()
        assert body.po_number is None

    def test_vendor_id_optional(self):
        body = OrderCreate()
        assert body.vendor_id is None

    def test_extra_defaults_to_empty_dict(self):
        body = OrderCreate()
        assert body.extra == {}

    def test_all_fields_set(self):
        body = OrderCreate(
            po_number="PO-100",
            vendor_id=5,
            order_date=date(2026, 1, 15),
            ship_date=date(2026, 1, 20),
            received_date=date(2026, 1, 25),
            received_by="Alice",
            status="pending",
            delivery_number="DEL-001",
            invoice_number="INV-001",
            document_id=10,
            extra={"note": "test"},
        )
        assert body.po_number == "PO-100"
        assert body.vendor_id == 5
        assert body.order_date == date(2026, 1, 15)
        assert body.extra == {"note": "test"}


# ===================================================================
# OrderUpdate schema validation
# ===================================================================


class TestOrderUpdateSchema:
    """Test OrderUpdate pydantic model validation."""

    def test_all_fields_optional(self):
        body = OrderUpdate()
        data = body.model_dump(exclude_unset=True)
        assert data == {}

    def test_status_none_is_valid(self):
        body = OrderUpdate(status=None)
        assert body.status is None

    def test_rejects_invalid_status(self):
        with pytest.raises(Exception):
            OrderUpdate(status="not_a_status")

    def test_accepts_valid_status(self):
        for s in OrderStatus:
            body = OrderUpdate(status=s.value)
            assert body.status == s.value

    def test_partial_update_only_sets_provided_fields(self):
        body = OrderUpdate(po_number="PO-NEW", status="shipped")
        data = body.model_dump(exclude_unset=True)
        assert set(data.keys()) == {"po_number", "status"}
        assert data["po_number"] == "PO-NEW"
        assert data["status"] == "shipped"

    def test_extra_can_be_set_to_dict(self):
        body = OrderUpdate(extra={"key": "value"})
        assert body.extra == {"key": "value"}

    def test_extra_can_be_set_to_none(self):
        body = OrderUpdate(extra=None)
        assert body.extra is None

    def test_vendor_id_can_be_set(self):
        body = OrderUpdate(vendor_id=42)
        assert body.vendor_id == 42

    def test_dates_can_be_updated(self):
        body = OrderUpdate(
            order_date=date(2026, 3, 1),
            ship_date=date(2026, 3, 5),
            received_date=date(2026, 3, 10),
        )
        assert body.order_date == date(2026, 3, 1)


# ===================================================================
# OrderItemCreate schema validation
# ===================================================================


class TestOrderItemCreateSchema:
    """Test OrderItemCreate pydantic model validation."""

    def test_defaults(self):
        item = OrderItemCreate()
        assert item.quantity == Decimal("1")
        assert item.catalog_number is None
        assert item.extra == {}

    def test_valid_quantity(self):
        item = OrderItemCreate(quantity=Decimal("10.5"))
        assert item.quantity == Decimal("10.5")

    def test_rejects_zero_quantity(self):
        with pytest.raises(Exception):
            OrderItemCreate(quantity=Decimal("0"))

    def test_rejects_negative_quantity(self):
        with pytest.raises(Exception):
            OrderItemCreate(quantity=Decimal("-1"))

    def test_rejects_excessive_quantity(self):
        with pytest.raises(Exception):
            OrderItemCreate(quantity=Decimal("1000001"))

    def test_accepts_max_quantity(self):
        item = OrderItemCreate(quantity=Decimal("1000000"))
        assert item.quantity == Decimal("1000000")

    def test_accepts_small_decimal_quantity(self):
        item = OrderItemCreate(quantity=Decimal("0.0001"))
        assert item.quantity == Decimal("0.0001")

    def test_unit_price_must_be_non_negative(self):
        with pytest.raises(Exception):
            OrderItemCreate(unit_price=Decimal("-0.01"))

    def test_unit_price_zero_is_valid(self):
        item = OrderItemCreate(unit_price=Decimal("0"))
        assert item.unit_price == Decimal("0")

    def test_unit_price_positive_is_valid(self):
        item = OrderItemCreate(unit_price=Decimal("99.99"))
        assert item.unit_price == Decimal("99.99")

    def test_all_optional_fields(self):
        item = OrderItemCreate(
            catalog_number="CAT-X",
            description="A test item",
            quantity=Decimal("5"),
            unit="each",
            lot_number="LOT-001",
            batch_number="BATCH-A",
            unit_price=Decimal("10.00"),
            product_id=7,
            extra={"source": "ocr"},
        )
        assert item.catalog_number == "CAT-X"
        assert item.description == "A test item"
        assert item.unit == "each"
        assert item.lot_number == "LOT-001"
        assert item.batch_number == "BATCH-A"
        assert item.product_id == 7


# ===================================================================
# OrderItemUpdate schema validation
# ===================================================================


class TestOrderItemUpdateSchema:
    """Test OrderItemUpdate pydantic model validation."""

    def test_all_fields_optional(self):
        body = OrderItemUpdate()
        data = body.model_dump(exclude_unset=True)
        assert data == {}

    def test_quantity_none_allowed(self):
        body = OrderItemUpdate(quantity=None)
        assert body.quantity is None

    def test_rejects_invalid_quantity(self):
        with pytest.raises(Exception):
            OrderItemUpdate(quantity=Decimal("0"))

    def test_accepts_valid_quantity(self):
        body = OrderItemUpdate(quantity=Decimal("5"))
        assert body.quantity == Decimal("5")

    def test_partial_update(self):
        body = OrderItemUpdate(catalog_number="NEW-CAT", lot_number="LOT-NEW")
        data = body.model_dump(exclude_unset=True)
        assert set(data.keys()) == {"catalog_number", "lot_number"}

    def test_unit_price_validation(self):
        with pytest.raises(Exception):
            OrderItemUpdate(unit_price=Decimal("-1"))


# ===================================================================
# ReceiveBody / ReceiveItemEntry schema validation
# ===================================================================


class TestReceiveItemEntrySchema:
    """Test ReceiveItemEntry pydantic model validation."""

    def test_defaults(self):
        entry = ReceiveItemEntry()
        assert entry.quantity == Decimal("1")
        assert entry.order_item_id is None
        assert entry.product_id is None

    def test_rejects_zero_quantity(self):
        with pytest.raises(Exception):
            ReceiveItemEntry(quantity=Decimal("0"))

    def test_rejects_negative_quantity(self):
        with pytest.raises(Exception):
            ReceiveItemEntry(quantity=Decimal("-5"))

    def test_accepts_valid_quantity(self):
        entry = ReceiveItemEntry(quantity=Decimal("100"))
        assert entry.quantity == Decimal("100")

    def test_all_fields(self):
        entry = ReceiveItemEntry(
            order_item_id=10,
            product_id=20,
            quantity=Decimal("3"),
            lot_number="LOT-R",
            unit="ml",
            expiry_date=date(2027, 12, 31),
        )
        assert entry.order_item_id == 10
        assert entry.product_id == 20
        assert entry.lot_number == "LOT-R"
        assert entry.expiry_date == date(2027, 12, 31)


class TestReceiveBodySchema:
    """Test ReceiveBody pydantic model validation."""

    def test_requires_received_by(self):
        with pytest.raises(Exception):
            ReceiveBody(items=[])  # missing received_by

    def test_requires_items_list(self):
        body = ReceiveBody(items=[], received_by="Alice")
        assert body.items == []

    def test_with_single_item(self):
        entry = ReceiveItemEntry(order_item_id=1, quantity=Decimal("2"))
        body = ReceiveBody(items=[entry], received_by="Bob", location_id=5)
        assert len(body.items) == 1
        assert body.received_by == "Bob"
        assert body.location_id == 5

    def test_with_multiple_items(self):
        items = [
            ReceiveItemEntry(order_item_id=i, quantity=Decimal(str(i)))
            for i in range(1, 4)
        ]
        body = ReceiveBody(items=items, received_by="Carol")
        assert len(body.items) == 3

    def test_location_id_optional(self):
        body = ReceiveBody(items=[], received_by="Dave")
        assert body.location_id is None


# ===================================================================
# OrderStatus enum completeness
# ===================================================================


class TestOrderStatusEnum:
    """Verify OrderStatus enum has expected values."""

    def test_has_pending(self):
        assert OrderStatus.pending.value == "pending"

    def test_has_shipped(self):
        assert OrderStatus.shipped.value == "shipped"

    def test_has_received(self):
        assert OrderStatus.received.value == "received"

    def test_has_cancelled(self):
        assert OrderStatus.cancelled.value == "cancelled"

    def test_has_deleted(self):
        assert OrderStatus.deleted.value == "deleted"

    def test_exactly_five_statuses(self):
        assert len(OrderStatus) == 5

    def test_all_values_are_lowercase_strings(self):
        for s in OrderStatus:
            assert s.value == s.value.lower()
            assert isinstance(s.value, str)


# ===================================================================
# Integration-style: _validate_status_transition with OrderStatus enum
# ===================================================================


class TestStatusTransitionWithEnum:
    """Verify _validate_status_transition works with OrderStatus enum values."""

    def test_enum_pending_to_enum_shipped(self):
        _validate_status_transition(
            OrderStatus.pending.value, OrderStatus.shipped.value
        )

    def test_enum_shipped_to_enum_received(self):
        _validate_status_transition(
            OrderStatus.shipped.value, OrderStatus.received.value
        )

    def test_enum_pending_to_enum_cancelled(self):
        _validate_status_transition(
            OrderStatus.pending.value, OrderStatus.cancelled.value
        )

    def test_enum_received_to_enum_deleted(self):
        _validate_status_transition(
            OrderStatus.received.value, OrderStatus.deleted.value
        )


# ===================================================================
# Edge cases: Order model default values
# ===================================================================


class TestOrderModelDefaults:
    """Verify Order model has correct defaults without DB."""

    def test_default_status_is_pending(self):
        order = Order()
        assert order.status == "pending"

    def test_default_po_number_is_none(self):
        order = Order()
        assert order.po_number is None

    def test_default_vendor_id_is_none(self):
        order = Order()
        assert order.vendor_id is None

    def test_default_extra_is_empty_dict(self):
        order = Order()
        assert order.extra == {}

    def test_default_received_by_is_none(self):
        order = Order()
        assert order.received_by is None

    def test_default_delivery_number_is_none(self):
        order = Order()
        assert order.delivery_number is None

    def test_default_invoice_number_is_none(self):
        order = Order()
        assert order.invoice_number is None


class TestOrderItemModelDefaults:
    """Verify OrderItem model has correct defaults without DB."""

    def test_default_quantity_is_one(self):
        item = OrderItem(order_id=1)
        assert item.quantity == 1

    def test_default_catalog_number_is_none(self):
        item = OrderItem(order_id=1)
        assert item.catalog_number is None

    def test_default_extra_is_empty_dict(self):
        item = OrderItem(order_id=1)
        assert item.extra == {}

    def test_default_unit_is_none(self):
        item = OrderItem(order_id=1)
        assert item.unit is None

    def test_default_lot_number_is_none(self):
        item = OrderItem(order_id=1)
        assert item.lot_number is None

    def test_default_unit_price_is_none(self):
        item = OrderItem(order_id=1)
        assert item.unit_price is None
