"""Unit tests for orders route -- CRUD, status transitions, items, edge cases.

Uses direct function calls with MagicMock DB sessions to isolate route logic.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from lab_manager.api.routes.orders import (
    OrderCreate,
    OrderItemCreate,
    OrderItemUpdate,
    OrderUpdate,
    ReceiveBody,
    ReceiveItemEntry,
    _IMMUTABLE_ORDER_STATUSES,
    _ORDER_SORTABLE,
    _VALID_ORDER_STATUSES,
    _validate_status_transition,
    _get_order_item_or_raise,
    _ensure_order_mutable,
)
from lab_manager.exceptions import NotFoundError, ValidationError
from lab_manager.models.order import OrderStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_order(
    id: int = 1,
    po_number: str | None = "PO-001",
    vendor_id: int | None = None,
    status: str = "pending",
    order_date: date | None = None,
    ship_date: date | None = None,
    received_date: date | None = None,
    received_by: str | None = None,
    delivery_number: str | None = None,
    invoice_number: str | None = None,
    document_id: int | None = None,
    extra: dict | None = None,
):
    """Create a mock Order object."""
    order = MagicMock()
    order.id = id
    order.po_number = po_number
    order.vendor_id = vendor_id
    order.status = status
    order.order_date = order_date
    order.ship_date = ship_date
    order.received_date = received_date
    order.received_by = received_by
    order.delivery_number = delivery_number
    order.invoice_number = invoice_number
    order.document_id = document_id
    order.extra = extra or {}
    order.created_at = "2026-01-01T00:00:00Z"
    order.updated_at = "2026-01-01T00:00:00Z"
    return order


def _make_order_item(
    id: int = 1,
    order_id: int = 1,
    catalog_number: str | None = "CAT-001",
    description: str | None = "Test item",
    quantity: Decimal = Decimal("1"),
    unit: str | None = "ea",
    lot_number: str | None = None,
    batch_number: str | None = None,
    unit_price: Decimal | None = None,
    product_id: int | None = None,
    extra: dict | None = None,
):
    """Create a mock OrderItem object."""
    item = MagicMock()
    item.id = id
    item.order_id = order_id
    item.catalog_number = catalog_number
    item.description = description
    item.quantity = quantity
    item.unit = unit
    item.lot_number = lot_number
    item.batch_number = batch_number
    item.unit_price = unit_price
    item.product_id = product_id
    item.extra = extra or {}
    return item


def _make_db():
    """Create a mock DB session."""
    db = MagicMock()
    db.get.return_value = None
    db.add.return_value = None
    db.flush.return_value = None
    db.refresh.return_value = None
    db.delete.return_value = None
    # db.scalars() for item lookup
    scalars_result = MagicMock()
    scalars_result.first.return_value = None
    scalars_result.all.return_value = []
    db.scalars.return_value = scalars_result
    # db.execute() for count queries
    execute_result = MagicMock()
    execute_result.scalar.return_value = 0
    db.execute.return_value = execute_result
    return db


def _make_paginate_result(items, total=None, page=1, page_size=50):
    """Build the dict that paginate() returns."""
    total = total if total is not None else len(items)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
    }


# ---------------------------------------------------------------------------
# Schema validation -- OrderCreate
# ---------------------------------------------------------------------------


class TestOrderCreateValidation:
    """Test Pydantic model validation for OrderCreate."""

    def test_valid_minimal(self):
        body = OrderCreate()
        assert body.status == "pending"
        assert body.po_number is None
        assert body.vendor_id is None
        assert body.order_date is None
        assert body.extra == {}

    def test_valid_all_fields(self):
        body = OrderCreate(
            po_number="PO-123",
            vendor_id=5,
            order_date=date(2026, 1, 15),
            ship_date=date(2026, 1, 20),
            received_date=date(2026, 1, 25),
            received_by="Alice",
            status="pending",
            delivery_number="DN-001",
            invoice_number="INV-001",
            document_id=10,
            extra={"note": "test"},
        )
        assert body.po_number == "PO-123"
        assert body.vendor_id == 5
        assert body.order_date == date(2026, 1, 15)
        assert body.extra == {"note": "test"}

    def test_invalid_status_rejected(self):
        with pytest.raises(Exception):
            OrderCreate(status="nonexistent_status")

    def test_all_valid_statuses(self):
        for status_val in _VALID_ORDER_STATUSES:
            body = OrderCreate(status=status_val)
            assert body.status == status_val

    def test_po_number_max_length(self):
        body = OrderCreate(po_number="A" * 100)
        assert len(body.po_number) == 100

    def test_po_number_exceeds_max_length(self):
        with pytest.raises(Exception):
            OrderCreate(po_number="A" * 101)

    def test_received_by_max_length(self):
        body = OrderCreate(received_by="A" * 200)
        assert len(body.received_by) == 200

    def test_received_by_exceeds_max_length(self):
        with pytest.raises(Exception):
            OrderCreate(received_by="A" * 201)

    def test_delivery_number_max_length(self):
        body = OrderCreate(delivery_number="A" * 100)
        assert len(body.delivery_number) == 100

    def test_delivery_number_exceeds_max_length(self):
        with pytest.raises(Exception):
            OrderCreate(delivery_number="A" * 101)

    def test_invoice_number_max_length(self):
        body = OrderCreate(invoice_number="A" * 100)
        assert len(body.invoice_number) == 100

    def test_invoice_number_exceeds_max_length(self):
        with pytest.raises(Exception):
            OrderCreate(invoice_number="A" * 101)


# ---------------------------------------------------------------------------
# Schema validation -- OrderUpdate
# ---------------------------------------------------------------------------


class TestOrderUpdateValidation:
    """Test Pydantic model validation for OrderUpdate."""

    def test_all_none(self):
        body = OrderUpdate()
        assert body.po_number is None
        assert body.status is None
        assert body.vendor_id is None

    def test_partial_update(self):
        body = OrderUpdate(po_number="PO-NEW")
        assert body.po_number == "PO-NEW"
        assert body.status is None

    def test_valid_status(self):
        for status_val in _VALID_ORDER_STATUSES:
            body = OrderUpdate(status=status_val)
            assert body.status == status_val

    def test_invalid_status_rejected(self):
        with pytest.raises(Exception):
            OrderUpdate(status="invalid_status")

    def test_none_status_is_valid(self):
        body = OrderUpdate(status=None)
        assert body.status is None

    def test_exclude_unset_behavior(self):
        body = OrderUpdate(po_number="PO-NEW")
        dumped = body.model_dump(exclude_unset=True)
        assert "po_number" in dumped
        assert "status" not in dumped
        assert "vendor_id" not in dumped


# ---------------------------------------------------------------------------
# Schema validation -- OrderItemCreate
# ---------------------------------------------------------------------------


class TestOrderItemCreateValidation:
    """Test Pydantic model validation for OrderItemCreate."""

    def test_valid_minimal(self):
        body = OrderItemCreate()
        assert body.quantity == Decimal("1")
        assert body.catalog_number is None
        assert body.extra == {}

    def test_valid_all_fields(self):
        body = OrderItemCreate(
            catalog_number="CAT-001",
            description="Test reagent",
            quantity=Decimal("10.5"),
            unit="ml",
            lot_number="LOT-123",
            batch_number="BATCH-456",
            unit_price=Decimal("29.99"),
            product_id=7,
            extra={"color": "blue"},
        )
        assert body.catalog_number == "CAT-001"
        assert body.quantity == Decimal("10.5")
        assert body.unit_price == Decimal("29.99")

    def test_quantity_zero_rejected(self):
        with pytest.raises(Exception):
            OrderItemCreate(quantity=Decimal("0"))

    def test_quantity_negative_rejected(self):
        with pytest.raises(Exception):
            OrderItemCreate(quantity=Decimal("-1"))

    def test_quantity_exceeds_max(self):
        with pytest.raises(Exception):
            OrderItemCreate(quantity=Decimal("1000001"))

    def test_quantity_at_max(self):
        body = OrderItemCreate(quantity=Decimal("1000000"))
        assert body.quantity == Decimal("1000000")

    def test_unit_price_negative_rejected(self):
        with pytest.raises(Exception):
            OrderItemCreate(unit_price=Decimal("-0.01"))

    def test_unit_price_zero_allowed(self):
        body = OrderItemCreate(unit_price=Decimal("0"))
        assert body.unit_price == Decimal("0")

    def test_catalog_number_max_length(self):
        body = OrderItemCreate(catalog_number="A" * 100)
        assert len(body.catalog_number) == 100

    def test_catalog_number_exceeds_max_length(self):
        with pytest.raises(Exception):
            OrderItemCreate(catalog_number="A" * 101)

    def test_description_max_length(self):
        body = OrderItemCreate(description="A" * 1000)
        assert len(body.description) == 1000

    def test_description_exceeds_max_length(self):
        with pytest.raises(Exception):
            OrderItemCreate(description="A" * 1001)


# ---------------------------------------------------------------------------
# Schema validation -- OrderItemUpdate
# ---------------------------------------------------------------------------


class TestOrderItemUpdateValidation:
    """Test Pydantic model validation for OrderItemUpdate."""

    def test_all_none(self):
        body = OrderItemUpdate()
        assert body.catalog_number is None
        assert body.quantity is None
        assert body.extra is None

    def test_partial_update(self):
        body = OrderItemUpdate(quantity=Decimal("5"))
        assert body.quantity == Decimal("5")
        assert body.catalog_number is None

    def test_exclude_unset_behavior(self):
        body = OrderItemUpdate(description="Updated desc")
        dumped = body.model_dump(exclude_unset=True)
        assert "description" in dumped
        assert "quantity" not in dumped
        assert "catalog_number" not in dumped

    def test_quantity_zero_rejected(self):
        with pytest.raises(Exception):
            OrderItemUpdate(quantity=Decimal("0"))

    def test_quantity_negative_rejected(self):
        with pytest.raises(Exception):
            OrderItemUpdate(quantity=Decimal("-5"))

    def test_quantity_exceeds_max(self):
        with pytest.raises(Exception):
            OrderItemUpdate(quantity=Decimal("1000001"))


# ---------------------------------------------------------------------------
# Schema validation -- ReceiveBody / ReceiveItemEntry
# ---------------------------------------------------------------------------


class TestReceiveBodyValidation:
    """Test Pydantic model validation for ReceiveBody and ReceiveItemEntry."""

    def test_receive_item_entry_minimal(self):
        entry = ReceiveItemEntry()
        assert entry.quantity == Decimal("1")
        assert entry.order_item_id is None
        assert entry.product_id is None

    def test_receive_item_entry_all_fields(self):
        entry = ReceiveItemEntry(
            order_item_id=1,
            product_id=2,
            quantity=Decimal("10"),
            lot_number="LOT-001",
            unit="ml",
            expiry_date=date(2027, 1, 1),
        )
        assert entry.order_item_id == 1
        assert entry.expiry_date == date(2027, 1, 1)

    def test_receive_body(self):
        body = ReceiveBody(
            items=[ReceiveItemEntry(order_item_id=1, quantity=Decimal("5"))],
            location_id=10,
            received_by="Bob",
        )
        assert len(body.items) == 1
        assert body.received_by == "Bob"
        assert body.location_id == 10

    def test_receive_body_missing_received_by_rejected(self):
        with pytest.raises(Exception):
            ReceiveBody(items=[])

    def test_receive_item_entry_quantity_zero_rejected(self):
        with pytest.raises(Exception):
            ReceiveItemEntry(quantity=Decimal("0"))


# ---------------------------------------------------------------------------
# Status transition validation
# ---------------------------------------------------------------------------


class TestStatusTransitionValidation:
    """Test _validate_status_transition logic."""

    def test_pending_to_shipped(self):
        _validate_status_transition("pending", "shipped")

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

    def test_pending_to_received_invalid(self):
        with pytest.raises(ValidationError, match="Invalid status transition"):
            _validate_status_transition("pending", "received")

    def test_received_to_pending_invalid(self):
        with pytest.raises(ValidationError, match="Invalid status transition"):
            _validate_status_transition("received", "pending")

    def test_received_to_shipped_invalid(self):
        with pytest.raises(ValidationError, match="Invalid status transition"):
            _validate_status_transition("received", "shipped")

    def test_cancelled_to_anything_invalid(self):
        """cancelled is a terminal status -- no outgoing transitions defined."""
        with pytest.raises(ValidationError, match="Invalid status transition"):
            _validate_status_transition("cancelled", "pending")

    def test_deleted_to_anything_invalid(self):
        """deleted is a terminal status."""
        with pytest.raises(ValidationError, match="Invalid status transition"):
            _validate_status_transition("deleted", "pending")

    def test_error_message_contains_allowed(self):
        """Error message should list allowed transitions."""
        with pytest.raises(ValidationError, match="cancelled"):
            _validate_status_transition("cancelled", "shipped")

    def test_terminal_status_empty_allowed(self):
        """Terminal statuses should report '(terminal status)' in error."""
        with pytest.raises(ValidationError, match="terminal status"):
            _validate_status_transition("cancelled", "pending")


# ---------------------------------------------------------------------------
# _ensure_order_mutable
# ---------------------------------------------------------------------------


class TestEnsureOrderMutable:
    """Test _ensure_order_mutable guard for item operations."""

    def test_pending_order_is_mutable(self):
        order = _make_order(status="pending")
        _ensure_order_mutable(order)  # should not raise

    def test_shipped_order_is_mutable(self):
        order = _make_order(status="shipped")
        _ensure_order_mutable(order)  # should not raise

    def test_received_order_is_immutable(self):
        order = _make_order(status="received")
        with pytest.raises(ValidationError, match="Cannot modify items"):
            _ensure_order_mutable(order)

    def test_cancelled_order_is_immutable(self):
        order = _make_order(status="cancelled")
        with pytest.raises(ValidationError, match="Cannot modify items"):
            _ensure_order_mutable(order)

    def test_deleted_order_is_immutable(self):
        order = _make_order(status="deleted")
        with pytest.raises(ValidationError, match="Cannot modify items"):
            _ensure_order_mutable(order)


# ---------------------------------------------------------------------------
# _get_order_item_or_raise
# ---------------------------------------------------------------------------


class TestGetOrderItemOrRaise:
    """Test _get_order_item_or_raise helper."""

    def test_item_found(self):
        db = _make_db()
        item = _make_order_item(id=1, order_id=10)
        db.scalars.return_value.first.return_value = item
        result = _get_order_item_or_raise(db, 10, 1)
        assert result.id == 1
        assert result.order_id == 10

    def test_item_not_found_raises(self):
        db = _make_db()
        db.scalars.return_value.first.return_value = None
        with pytest.raises(NotFoundError, match="Order item"):
            _get_order_item_or_raise(db, 10, 999)

    def test_item_wrong_order_raises(self):
        """If item exists but belongs to a different order, scalars query returns None."""
        db = _make_db()
        db.scalars.return_value.first.return_value = None
        with pytest.raises(NotFoundError):
            _get_order_item_or_raise(db, 999, 1)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestOrderConstants:
    """Test module-level constants."""

    def test_valid_order_statuses(self):
        expected = {"pending", "shipped", "received", "cancelled", "deleted"}
        assert _VALID_ORDER_STATUSES == expected

    def test_immutable_order_statuses(self):
        assert "received" in _IMMUTABLE_ORDER_STATUSES
        assert "cancelled" in _IMMUTABLE_ORDER_STATUSES
        assert "deleted" in _IMMUTABLE_ORDER_STATUSES
        assert "pending" not in _IMMUTABLE_ORDER_STATUSES
        assert "shipped" not in _IMMUTABLE_ORDER_STATUSES

    def test_order_sortable_fields(self):
        expected = {
            "id",
            "created_at",
            "updated_at",
            "po_number",
            "order_date",
            "ship_date",
            "received_date",
            "status",
            "vendor_id",
        }
        assert _ORDER_SORTABLE == expected


# ---------------------------------------------------------------------------
# list_orders route
# ---------------------------------------------------------------------------


def _list_orders_kwargs(**overrides):
    """Build keyword arguments for list_orders, providing explicit None for all
    optional params so FastAPI Query defaults are not used."""
    defaults = dict(
        page=1,
        page_size=50,
        vendor_id=None,
        status=None,
        status_group=None,
        po_number=None,
        date_from=None,
        date_to=None,
        received_by=None,
        sort_by="id",
        sort_dir="asc",
    )
    defaults.update(overrides)
    return defaults


class TestListOrders:
    """Test the GET / orders list endpoint."""

    @patch("lab_manager.api.routes.orders.paginate")
    @patch("lab_manager.api.routes.orders.apply_sort")
    def test_basic_list(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.orders import list_orders

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        result = list_orders(**_list_orders_kwargs(), db=db)
        assert result["total"] == 0
        assert result["items"] == []

    @patch("lab_manager.api.routes.orders.paginate")
    @patch("lab_manager.api.routes.orders.apply_sort")
    def test_list_with_vendor_filter(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.orders import list_orders

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_orders(**_list_orders_kwargs(vendor_id=5), db=db)
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.orders.paginate")
    @patch("lab_manager.api.routes.orders.apply_sort")
    def test_list_with_status_filter(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.orders import list_orders

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_orders(**_list_orders_kwargs(status="pending"), db=db)
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.orders.paginate")
    @patch("lab_manager.api.routes.orders.apply_sort")
    def test_list_with_status_group_active(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.orders import list_orders

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_orders(**_list_orders_kwargs(status_group="active"), db=db)
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.orders.paginate")
    @patch("lab_manager.api.routes.orders.apply_sort")
    def test_list_with_status_group_past(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.orders import list_orders

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_orders(**_list_orders_kwargs(status_group="past"), db=db)
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.orders.paginate")
    @patch("lab_manager.api.routes.orders.apply_sort")
    def test_list_with_status_group_drafts(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.orders import list_orders

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_orders(**_list_orders_kwargs(status_group="drafts"), db=db)
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.orders.paginate")
    @patch("lab_manager.api.routes.orders.apply_sort")
    def test_list_with_po_number_filter(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.orders import list_orders

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_orders(**_list_orders_kwargs(po_number="PO-001"), db=db)
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.orders.paginate")
    @patch("lab_manager.api.routes.orders.apply_sort")
    def test_list_with_date_range(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.orders import list_orders

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_orders(
            **_list_orders_kwargs(
                date_from=date(2026, 1, 1), date_to=date(2026, 12, 31)
            ),
            db=db,
        )
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.orders.paginate")
    @patch("lab_manager.api.routes.orders.apply_sort")
    def test_list_with_received_by_filter(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.orders import list_orders

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_orders(**_list_orders_kwargs(received_by="Alice"), db=db)
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.orders.paginate")
    @patch("lab_manager.api.routes.orders.apply_sort")
    def test_list_with_custom_pagination(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.orders import list_orders

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result(
            [], total=0, page=3, page_size=10
        )
        db = _make_db()

        result = list_orders(**_list_orders_kwargs(page=3, page_size=10), db=db)
        assert result["page"] == 3
        assert result["page_size"] == 10

    @patch("lab_manager.api.routes.orders.paginate")
    @patch("lab_manager.api.routes.orders.apply_sort")
    def test_list_status_takes_precedence_over_status_group(
        self, mock_sort, mock_paginate
    ):
        """When both status and status_group are provided, status wins."""
        from lab_manager.api.routes.orders import list_orders

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_orders(
            **_list_orders_kwargs(status="pending", status_group="active"), db=db
        )
        mock_paginate.assert_called_once()


# ---------------------------------------------------------------------------
# create_order route
# ---------------------------------------------------------------------------


class TestCreateOrder:
    """Test the POST / create order endpoint."""

    @patch("lab_manager.api.routes.orders.index_order_record")
    @patch("lab_manager.api.routes.orders.find_duplicate_po")
    def test_create_basic(
        self,
        mock_find_dup,
        mock_index,
    ):
        from lab_manager.api.routes.orders import create_order

        db = _make_db()
        mock_find_dup.return_value = []

        body = OrderCreate(po_number="PO-001", vendor_id=1)
        result = create_order(body=body, db=db)

        db.add.assert_called_once()
        db.flush.assert_called_once()
        db.refresh.assert_called_once()
        mock_index.assert_called_once()
        assert result["_duplicate_warning"] is None

    @patch("lab_manager.api.routes.orders.index_order_record")
    @patch("lab_manager.api.routes.orders.find_duplicate_po")
    def test_create_non_pending_status_rejected(self, mock_find_dup, mock_index):
        from lab_manager.api.routes.orders import create_order

        db = _make_db()
        body = OrderCreate(status="shipped")

        with pytest.raises(ValidationError, match="New orders must be created"):
            create_order(body=body, db=db)

    @patch("lab_manager.api.routes.orders.index_order_record")
    @patch("lab_manager.api.routes.orders.find_duplicate_po")
    def test_create_with_all_fields(self, mock_find_dup, mock_index):
        from lab_manager.api.routes.orders import create_order

        db = _make_db()
        mock_find_dup.return_value = []

        body = OrderCreate(
            po_number="PO-FULL",
            vendor_id=3,
            order_date=date(2026, 3, 1),
            ship_date=date(2026, 3, 5),
            received_date=date(2026, 3, 10),
            received_by="Alice",
            status="pending",
            delivery_number="DN-001",
            invoice_number="INV-001",
            document_id=5,
            extra={"priority": "high"},
        )
        result = create_order(body=body, db=db)

        db.add.assert_called_once()
        assert result["_duplicate_warning"] is None

    @patch("lab_manager.api.routes.orders.index_order_record")
    @patch("lab_manager.api.routes.orders.find_duplicate_po")
    def test_create_with_duplicate_po_warning(self, mock_find_dup, mock_index):
        from lab_manager.api.routes.orders import create_order

        db = _make_db()
        dup_order = _make_order(id=99, po_number="PO-DUP")
        mock_find_dup.return_value = [dup_order]

        body = OrderCreate(po_number="PO-DUP", vendor_id=1)
        result = create_order(body=body, db=db)

        assert result["_duplicate_warning"] is not None
        assert result["_duplicate_warning"]["warning"] == "duplicate_po_number"
        assert 99 in result["_duplicate_warning"]["duplicate_order_ids"]

    @patch("lab_manager.api.routes.orders.index_order_record")
    @patch("lab_manager.api.routes.orders.find_duplicate_po")
    def test_create_no_po_number_skips_duplicate_check(self, mock_find_dup, mock_index):
        from lab_manager.api.routes.orders import create_order

        db = _make_db()

        body = OrderCreate(po_number=None)
        result = create_order(body=body, db=db)

        mock_find_dup.assert_not_called()
        assert result["_duplicate_warning"] is None

    @patch("lab_manager.api.routes.orders.index_order_record")
    @patch("lab_manager.api.routes.orders.find_duplicate_po")
    def test_create_uses_model_dump(self, mock_find_dup, mock_index):
        from lab_manager.api.routes.orders import create_order

        db = _make_db()
        mock_find_dup.return_value = []

        body = OrderCreate(po_number="PO-DUMP", vendor_id=7)
        create_order(body=body, db=db)

        added_obj = db.add.call_args[0][0]
        assert added_obj.po_number == "PO-DUMP"
        assert added_obj.vendor_id == 7


# ---------------------------------------------------------------------------
# get_order route
# ---------------------------------------------------------------------------


class TestGetOrder:
    """Test the GET /{order_id} endpoint."""

    def test_get_existing(self):
        from lab_manager.api.routes.orders import get_order

        order = _make_order(id=42, po_number="PO-FOUND")
        db = _make_db()
        db.get.return_value = order

        result = get_order(order_id=42, db=db)
        assert result.id == 42
        assert result.po_number == "PO-FOUND"

    def test_get_nonexistent_raises_not_found(self):
        from lab_manager.api.routes.orders import get_order

        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            get_order(order_id=9999, db=db)

    def test_get_uses_correct_model(self):
        from lab_manager.api.routes.orders import get_order
        from lab_manager.models.order import Order

        order = _make_order(id=5)
        db = _make_db()
        db.get.return_value = order

        get_order(order_id=5, db=db)
        db.get.assert_called_once_with(Order, 5)


# ---------------------------------------------------------------------------
# update_order route
# ---------------------------------------------------------------------------


class TestUpdateOrder:
    """Test the PATCH /{order_id} endpoint."""

    @patch("lab_manager.api.routes.orders.index_order_record")
    def test_update_po_number(self, mock_index):
        from lab_manager.api.routes.orders import update_order

        order = _make_order(id=1, po_number="PO-OLD", status="pending")
        db = _make_db()
        db.get.return_value = order

        body = OrderUpdate(po_number="PO-NEW")
        result = update_order(order_id=1, body=body, db=db)

        assert order.po_number == "PO-NEW"
        db.flush.assert_called_once()
        mock_index.assert_called_once()

    @patch("lab_manager.api.routes.orders.index_order_record")
    def test_update_status_valid_transition(self, mock_index):
        from lab_manager.api.routes.orders import update_order

        order = _make_order(id=1, status="pending")
        db = _make_db()
        db.get.return_value = order

        body = OrderUpdate(status="shipped")
        result = update_order(order_id=1, body=body, db=db)

        assert order.status == "shipped"

    @patch("lab_manager.api.routes.orders.index_order_record")
    def test_update_status_invalid_transition(self, mock_index):
        from lab_manager.api.routes.orders import update_order

        order = _make_order(id=1, status="pending")
        db = _make_db()
        db.get.return_value = order

        body = OrderUpdate(status="received")
        with pytest.raises(ValidationError, match="Invalid status transition"):
            update_order(order_id=1, body=body, db=db)

    @patch("lab_manager.api.routes.orders.index_order_record")
    def test_update_nonexistent_raises_not_found(self, mock_index):
        from lab_manager.api.routes.orders import update_order

        db = _make_db()
        db.get.return_value = None

        body = OrderUpdate(po_number="NOPE")
        with pytest.raises(NotFoundError):
            update_order(order_id=9999, body=body, db=db)

    @patch("lab_manager.api.routes.orders.index_order_record")
    def test_partial_update_only_sets_provided_fields(self, mock_index):
        from lab_manager.api.routes.orders import update_order

        order = _make_order(id=1, po_number="PO-KEEP", status="pending", vendor_id=5)
        db = _make_db()
        db.get.return_value = order

        body = OrderUpdate(vendor_id=10)
        update_order(order_id=1, body=body, db=db)

        assert order.vendor_id == 10
        # po_number and status should not have been changed by setattr calls
        # since they weren't in model_dump(exclude_unset=True)

    @patch("lab_manager.api.routes.orders.index_order_record")
    def test_update_empty_body_no_crash(self, mock_index):
        from lab_manager.api.routes.orders import update_order

        order = _make_order(id=1, status="pending")
        db = _make_db()
        db.get.return_value = order

        body = OrderUpdate()
        update_order(order_id=1, body=body, db=db)
        db.flush.assert_called_once()

    @patch("lab_manager.api.routes.orders.index_order_record")
    def test_update_multiple_fields(self, mock_index):
        from lab_manager.api.routes.orders import update_order

        order = _make_order(id=1, status="pending", po_number="PO-OLD")
        db = _make_db()
        db.get.return_value = order

        body = OrderUpdate(
            po_number="PO-NEW",
            delivery_number="DN-NEW",
            invoice_number="INV-NEW",
        )
        update_order(order_id=1, body=body, db=db)

        assert order.po_number == "PO-NEW"
        assert order.delivery_number == "DN-NEW"
        assert order.invoice_number == "INV-NEW"

    @patch("lab_manager.api.routes.orders.index_order_record")
    def test_update_received_to_deleted(self, mock_index):
        from lab_manager.api.routes.orders import update_order

        order = _make_order(id=1, status="received")
        db = _make_db()
        db.get.return_value = order

        body = OrderUpdate(status="deleted")
        update_order(order_id=1, body=body, db=db)
        assert order.status == "deleted"

    @patch("lab_manager.api.routes.orders.index_order_record")
    def test_update_shipped_to_received(self, mock_index):
        from lab_manager.api.routes.orders import update_order

        order = _make_order(id=1, status="shipped")
        db = _make_db()
        db.get.return_value = order

        body = OrderUpdate(status="received")
        update_order(order_id=1, body=body, db=db)
        assert order.status == "received"


# ---------------------------------------------------------------------------
# delete_order route
# ---------------------------------------------------------------------------


class TestDeleteOrder:
    """Test the DELETE /{order_id} endpoint (soft-delete)."""

    def test_delete_existing(self):
        from lab_manager.api.routes.orders import delete_order

        order = _make_order(id=1, status="pending")
        db = _make_db()
        db.get.return_value = order

        result = delete_order(order_id=1, db=db)
        assert result is None
        assert order.status == OrderStatus.deleted
        db.flush.assert_called_once()

    def test_delete_nonexistent_raises_not_found(self):
        from lab_manager.api.routes.orders import delete_order

        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            delete_order(order_id=9999, db=db)

    def test_soft_delete_sets_status(self):
        from lab_manager.api.routes.orders import delete_order

        order = _make_order(id=5, status="received")
        db = _make_db()
        db.get.return_value = order

        delete_order(order_id=5, db=db)
        assert order.status == "deleted"

    def test_delete_returns_none(self):
        from lab_manager.api.routes.orders import delete_order

        order = _make_order(id=1, status="pending")
        db = _make_db()
        db.get.return_value = order

        result = delete_order(order_id=1, db=db)
        assert result is None


# ---------------------------------------------------------------------------
# list_order_items route
# ---------------------------------------------------------------------------


def _list_items_kwargs(**overrides):
    """Build keyword arguments for list_order_items."""
    defaults = dict(
        page=1,
        page_size=50,
        catalog_number=None,
        lot_number=None,
    )
    defaults.update(overrides)
    return defaults


class TestListOrderItems:
    """Test the GET /{order_id}/items endpoint."""

    @patch("lab_manager.api.routes.orders.paginate")
    def test_basic_list(self, mock_paginate):
        from lab_manager.api.routes.orders import list_order_items

        order = _make_order(id=1)
        db = _make_db()
        db.get.return_value = order
        mock_paginate.return_value = _make_paginate_result([], total=0)

        result = list_order_items(order_id=1, **_list_items_kwargs(), db=db)
        assert result["total"] == 0

    @patch("lab_manager.api.routes.orders.paginate")
    def test_order_not_found_raises(self, mock_paginate):
        from lab_manager.api.routes.orders import list_order_items

        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            list_order_items(order_id=9999, **_list_items_kwargs(), db=db)

    @patch("lab_manager.api.routes.orders.paginate")
    def test_list_with_catalog_number_filter(self, mock_paginate):
        from lab_manager.api.routes.orders import list_order_items

        order = _make_order(id=1)
        db = _make_db()
        db.get.return_value = order
        mock_paginate.return_value = _make_paginate_result([], total=0)

        list_order_items(
            order_id=1, **_list_items_kwargs(catalog_number="CAT-001"), db=db
        )
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.orders.paginate")
    def test_list_with_lot_number_filter(self, mock_paginate):
        from lab_manager.api.routes.orders import list_order_items

        order = _make_order(id=1)
        db = _make_db()
        db.get.return_value = order
        mock_paginate.return_value = _make_paginate_result([], total=0)

        list_order_items(order_id=1, **_list_items_kwargs(lot_number="LOT-001"), db=db)
        mock_paginate.assert_called_once()


# ---------------------------------------------------------------------------
# create_order_item route
# ---------------------------------------------------------------------------


class TestCreateOrderItem:
    """Test the POST /{order_id}/items endpoint."""

    def test_create_basic(self):
        from lab_manager.api.routes.orders import create_order_item

        order = _make_order(id=1, status="pending")
        db = _make_db()
        db.get.return_value = order

        body = OrderItemCreate(catalog_number="CAT-001", quantity=Decimal("5"))
        result = create_order_item(order_id=1, body=body, db=db)

        db.add.assert_called_once()
        db.flush.assert_called_once()
        db.refresh.assert_called_once()

    def test_create_on_immutable_order_raises(self):
        from lab_manager.api.routes.orders import create_order_item

        order = _make_order(id=1, status="received")
        db = _make_db()
        db.get.return_value = order

        body = OrderItemCreate()
        with pytest.raises(ValidationError, match="Cannot modify items"):
            create_order_item(order_id=1, body=body, db=db)

    def test_create_on_cancelled_order_raises(self):
        from lab_manager.api.routes.orders import create_order_item

        order = _make_order(id=1, status="cancelled")
        db = _make_db()
        db.get.return_value = order

        body = OrderItemCreate()
        with pytest.raises(ValidationError, match="Cannot modify items"):
            create_order_item(order_id=1, body=body, db=db)

    def test_create_on_deleted_order_raises(self):
        from lab_manager.api.routes.orders import create_order_item

        order = _make_order(id=1, status="deleted")
        db = _make_db()
        db.get.return_value = order

        body = OrderItemCreate()
        with pytest.raises(ValidationError, match="Cannot modify items"):
            create_order_item(order_id=1, body=body, db=db)

    def test_create_order_not_found_raises(self):
        from lab_manager.api.routes.orders import create_order_item

        db = _make_db()
        db.get.return_value = None

        body = OrderItemCreate()
        with pytest.raises(NotFoundError):
            create_order_item(order_id=9999, body=body, db=db)

    def test_create_sets_order_id(self):
        from lab_manager.api.routes.orders import create_order_item

        order = _make_order(id=42, status="pending")
        db = _make_db()
        db.get.return_value = order

        body = OrderItemCreate(catalog_number="CAT-X")
        create_order_item(order_id=42, body=body, db=db)

        added_obj = db.add.call_args[0][0]
        assert added_obj.order_id == 42

    def test_create_with_all_fields(self):
        from lab_manager.api.routes.orders import create_order_item

        order = _make_order(id=1, status="pending")
        db = _make_db()
        db.get.return_value = order

        body = OrderItemCreate(
            catalog_number="CAT-001",
            description="Reagent X",
            quantity=Decimal("10.5"),
            unit="ml",
            lot_number="LOT-001",
            batch_number="BATCH-001",
            unit_price=Decimal("49.99"),
            product_id=3,
            extra={"hazardous": True},
        )
        create_order_item(order_id=1, body=body, db=db)
        added_obj = db.add.call_args[0][0]
        assert added_obj.catalog_number == "CAT-001"
        assert added_obj.quantity == Decimal("10.5")


# ---------------------------------------------------------------------------
# get_order_item route
# ---------------------------------------------------------------------------


class TestGetOrderItem:
    """Test the GET /{order_id}/items/{item_id} endpoint."""

    def test_get_existing_item(self):
        from lab_manager.api.routes.orders import get_order_item

        item = _make_order_item(id=1, order_id=10)
        db = _make_db()
        db.scalars.return_value.first.return_value = item

        result = get_order_item(order_id=10, item_id=1, db=db)
        assert result.id == 1
        assert result.order_id == 10

    def test_get_nonexistent_item_raises(self):
        from lab_manager.api.routes.orders import get_order_item

        db = _make_db()
        db.scalars.return_value.first.return_value = None

        with pytest.raises(NotFoundError, match="Order item"):
            get_order_item(order_id=10, item_id=999, db=db)


# ---------------------------------------------------------------------------
# update_order_item route
# ---------------------------------------------------------------------------


class TestUpdateOrderItem:
    """Test the PATCH /{order_id}/items/{item_id} endpoint."""

    def test_update_quantity(self):
        from lab_manager.api.routes.orders import update_order_item

        order = _make_order(id=1, status="pending")
        item = _make_order_item(id=10, order_id=1, quantity=Decimal("1"))
        db = _make_db()
        db.get.return_value = order
        db.scalars.return_value.first.return_value = item

        body = OrderItemUpdate(quantity=Decimal("5"))
        result = update_order_item(order_id=1, item_id=10, body=body, db=db)

        assert item.quantity == Decimal("5")
        db.flush.assert_called_once()

    def test_update_description(self):
        from lab_manager.api.routes.orders import update_order_item

        order = _make_order(id=1, status="pending")
        item = _make_order_item(id=10, order_id=1)
        db = _make_db()
        db.get.return_value = order
        db.scalars.return_value.first.return_value = item

        body = OrderItemUpdate(description="Updated description")
        update_order_item(order_id=1, item_id=10, body=body, db=db)
        assert item.description == "Updated description"

    def test_update_on_immutable_order_raises(self):
        from lab_manager.api.routes.orders import update_order_item

        order = _make_order(id=1, status="received")
        db = _make_db()
        db.get.return_value = order

        body = OrderItemUpdate(quantity=Decimal("5"))
        with pytest.raises(ValidationError, match="Cannot modify items"):
            update_order_item(order_id=1, item_id=10, body=body, db=db)

    def test_update_order_not_found_raises(self):
        from lab_manager.api.routes.orders import update_order_item

        db = _make_db()
        db.get.return_value = None

        body = OrderItemUpdate(quantity=Decimal("5"))
        with pytest.raises(NotFoundError):
            update_order_item(order_id=9999, item_id=10, body=body, db=db)

    def test_update_item_not_found_raises(self):
        from lab_manager.api.routes.orders import update_order_item

        order = _make_order(id=1, status="pending")
        db = _make_db()
        db.get.return_value = order
        db.scalars.return_value.first.return_value = None

        body = OrderItemUpdate(quantity=Decimal("5"))
        with pytest.raises(NotFoundError, match="Order item"):
            update_order_item(order_id=1, item_id=999, body=body, db=db)

    def test_update_partial_only_sets_provided(self):
        from lab_manager.api.routes.orders import update_order_item

        order = _make_order(id=1, status="pending")
        item = _make_order_item(id=10, order_id=1, catalog_number="CAT-OLD")
        db = _make_db()
        db.get.return_value = order
        db.scalars.return_value.first.return_value = item

        body = OrderItemUpdate(unit="kg")
        update_order_item(order_id=1, item_id=10, body=body, db=db)
        assert item.unit == "kg"
        # catalog_number not changed by setattr since it wasn't in exclude_unset

    def test_update_multiple_fields(self):
        from lab_manager.api.routes.orders import update_order_item

        order = _make_order(id=1, status="pending")
        item = _make_order_item(id=10, order_id=1)
        db = _make_db()
        db.get.return_value = order
        db.scalars.return_value.first.return_value = item

        body = OrderItemUpdate(
            catalog_number="CAT-NEW",
            lot_number="LOT-NEW",
            unit_price=Decimal("99.99"),
        )
        update_order_item(order_id=1, item_id=10, body=body, db=db)
        assert item.catalog_number == "CAT-NEW"
        assert item.lot_number == "LOT-NEW"
        assert item.unit_price == Decimal("99.99")


# ---------------------------------------------------------------------------
# delete_order_item route
# ---------------------------------------------------------------------------


class TestDeleteOrderItem:
    """Test the DELETE /{order_id}/items/{item_id} endpoint."""

    def test_delete_existing_item(self):
        from lab_manager.api.routes.orders import delete_order_item

        order = _make_order(id=1, status="pending")
        item = _make_order_item(id=10, order_id=1)
        db = _make_db()
        db.get.return_value = order
        db.scalars.return_value.first.return_value = item

        result = delete_order_item(order_id=1, item_id=10, db=db)
        assert result is None
        db.delete.assert_called_once_with(item)
        db.flush.assert_called_once()

    def test_delete_on_immutable_order_raises(self):
        from lab_manager.api.routes.orders import delete_order_item

        order = _make_order(id=1, status="cancelled")
        db = _make_db()
        db.get.return_value = order

        with pytest.raises(ValidationError, match="Cannot modify items"):
            delete_order_item(order_id=1, item_id=10, db=db)

    def test_delete_order_not_found_raises(self):
        from lab_manager.api.routes.orders import delete_order_item

        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            delete_order_item(order_id=9999, item_id=10, db=db)

    def test_delete_item_not_found_raises(self):
        from lab_manager.api.routes.orders import delete_order_item

        order = _make_order(id=1, status="pending")
        db = _make_db()
        db.get.return_value = order
        db.scalars.return_value.first.return_value = None

        with pytest.raises(NotFoundError, match="Order item"):
            delete_order_item(order_id=1, item_id=999, db=db)

    def test_delete_returns_none(self):
        from lab_manager.api.routes.orders import delete_order_item

        order = _make_order(id=1, status="pending")
        item = _make_order_item(id=10, order_id=1)
        db = _make_db()
        db.get.return_value = order
        db.scalars.return_value.first.return_value = item

        result = delete_order_item(order_id=1, item_id=10, db=db)
        assert result is None


# ---------------------------------------------------------------------------
# receive_order route
# ---------------------------------------------------------------------------


class TestReceiveOrder:
    """Test the POST /{order_id}/receive endpoint."""

    @patch("lab_manager.api.routes.orders.index_order_record", create=True)
    def test_receive_delegates_to_inventory_service(self, mock_index):
        from lab_manager.api.routes.orders import receive_order

        db = _make_db()
        body = ReceiveBody(
            items=[
                ReceiveItemEntry(order_item_id=1, quantity=Decimal("5")),
            ],
            location_id=10,
            received_by="Alice",
        )

        with patch("lab_manager.services.inventory.receive_items") as mock_recv:
            mock_recv.return_value = {"status": "ok"}
            result = receive_order(order_id=1, body=body, db=db)

            mock_recv.assert_called_once_with(
                1,
                [
                    {
                        "order_item_id": 1,
                        "product_id": None,
                        "quantity": Decimal("5"),
                        "lot_number": None,
                        "unit": None,
                        "expiry_date": None,
                    }
                ],
                10,
                "Alice",
                db,
            )
            assert result == {"status": "ok"}

    @patch("lab_manager.services.inventory.receive_items")
    def test_receive_with_multiple_items(self, mock_recv):
        from lab_manager.api.routes.orders import receive_order

        db = _make_db()
        body = ReceiveBody(
            items=[
                ReceiveItemEntry(order_item_id=1, quantity=Decimal("5")),
                ReceiveItemEntry(order_item_id=2, quantity=Decimal("10"), product_id=3),
            ],
            location_id=5,
            received_by="Bob",
        )
        mock_recv.return_value = {"received": 2}

        result = receive_order(order_id=1, body=body, db=db)
        assert result == {"received": 2}
        items_arg = mock_recv.call_args[0][1]
        assert len(items_arg) == 2

    @patch("lab_manager.services.inventory.receive_items")
    def test_receive_without_location(self, mock_recv):
        from lab_manager.api.routes.orders import receive_order

        db = _make_db()
        body = ReceiveBody(
            items=[ReceiveItemEntry(order_item_id=1)],
            location_id=None,
            received_by="Charlie",
        )
        mock_recv.return_value = {"status": "ok"}

        receive_order(order_id=1, body=body, db=db)
        mock_recv.assert_called_once()
        # location_id should be None
        assert mock_recv.call_args[0][2] is None

    @patch("lab_manager.services.inventory.receive_items")
    def test_receive_passes_correct_order_id(self, mock_recv):
        from lab_manager.api.routes.orders import receive_order

        db = _make_db()
        body = ReceiveBody(
            items=[ReceiveItemEntry()],
            received_by="Dave",
        )
        mock_recv.return_value = {}

        receive_order(order_id=42, body=body, db=db)
        assert mock_recv.call_args[0][0] == 42


# ---------------------------------------------------------------------------
# build_duplicate_warning (from orders service, tested via route import)
# ---------------------------------------------------------------------------


class TestBuildDuplicateWarning:
    """Test build_duplicate_warning from the orders service."""

    def test_no_duplicates(self):
        from lab_manager.services.orders import find_duplicate_po

        db = _make_db()
        db.scalars.return_value.all.return_value = []

        result = find_duplicate_po("PO-001", None, db)
        assert result == []

    def test_duplicate_warning_structure(self):
        from lab_manager.services.orders import build_duplicate_warning

        dup1 = _make_order(id=10, po_number="PO-DUP")
        dup2 = _make_order(id=20, po_number="PO-DUP")
        warning = build_duplicate_warning([dup1, dup2])

        assert warning["warning"] == "duplicate_po_number"
        assert len(warning["duplicate_order_ids"]) == 2
        assert 10 in warning["duplicate_order_ids"]
        assert 20 in warning["duplicate_order_ids"]
        assert "2 order(s)" in warning["message"]

    def test_find_duplicate_empty_po_returns_empty(self):
        from lab_manager.services.orders import find_duplicate_po

        db = _make_db()
        result = find_duplicate_po("", None, db)
        assert result == []

    def test_find_duplicate_whitespace_po_returns_empty(self):
        from lab_manager.services.orders import find_duplicate_po

        db = _make_db()
        result = find_duplicate_po("   ", None, db)
        assert result == []


# ---------------------------------------------------------------------------
# Edge cases and integration-style tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_order_status_enum_values(self):
        assert OrderStatus.pending.value == "pending"
        assert OrderStatus.shipped.value == "shipped"
        assert OrderStatus.received.value == "received"
        assert OrderStatus.cancelled.value == "cancelled"
        assert OrderStatus.deleted.value == "deleted"

    def test_order_create_default_extra_is_empty_dict(self):
        body = OrderCreate()
        assert body.extra == {}

    def test_order_item_create_default_extra_is_empty_dict(self):
        body = OrderItemCreate()
        assert body.extra == {}

    def test_order_update_with_extra_dict(self):
        body = OrderUpdate(extra={"key": "value"})
        assert body.extra == {"key": "value"}

    def test_order_item_update_with_extra_dict(self):
        body = OrderItemUpdate(extra={"note": "updated"})
        assert body.extra == {"note": "updated"}

    def test_order_create_with_empty_extra(self):
        body = OrderCreate(extra={})
        assert body.extra == {}

    @patch("lab_manager.api.routes.orders.index_order_record")
    @patch("lab_manager.api.routes.orders.find_duplicate_po")
    def test_create_order_response_structure(self, mock_find_dup, mock_index):
        from lab_manager.api.routes.orders import create_order

        db = _make_db()
        mock_find_dup.return_value = []

        body = OrderCreate(po_number="PO-RSP")
        result = create_order(body=body, db=db)

        assert "order" in result
        assert "_duplicate_warning" in result
        assert result["_duplicate_warning"] is None

    @patch("lab_manager.api.routes.orders.index_order_record")
    def test_update_order_response_is_the_order(self, mock_index):
        from lab_manager.api.routes.orders import update_order

        order = _make_order(id=1, status="pending")
        db = _make_db()
        db.get.return_value = order

        body = OrderUpdate(po_number="PO-RESULT")
        result = update_order(order_id=1, body=body, db=db)
        assert result is order

    def test_delete_order_does_not_hard_delete(self):
        """Delete should set status to 'deleted', not call db.delete()."""
        from lab_manager.api.routes.orders import delete_order

        order = _make_order(id=1, status="pending")
        db = _make_db()
        db.get.return_value = order

        delete_order(order_id=1, db=db)
        assert order.status == "deleted"
        db.delete.assert_not_called()

    @patch("lab_manager.api.routes.orders.paginate")
    @patch("lab_manager.api.routes.orders.apply_sort")
    def test_list_orders_default_sort_params(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.orders import list_orders

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([])
        db = _make_db()

        list_orders(**_list_orders_kwargs(), db=db)
        mock_sort.assert_called_once()
        # Verify default sort_by="id", sort_dir="asc"
        call_args = mock_sort.call_args
        assert call_args[0][2] == "id"  # sort_by
        assert call_args[0][3] == "asc"  # sort_dir

    def test_order_item_create_default_quantity(self):
        body = OrderItemCreate()
        assert body.quantity == Decimal("1")

    def test_order_item_create_custom_quantity(self):
        body = OrderItemCreate(quantity=Decimal("999999.9999"))
        assert body.quantity == Decimal("999999.9999")

    @patch("lab_manager.api.routes.orders.index_order_record")
    def test_update_order_cancelled_cannot_transition(self, mock_index):
        from lab_manager.api.routes.orders import update_order

        order = _make_order(id=1, status="cancelled")
        db = _make_db()
        db.get.return_value = order

        body = OrderUpdate(status="pending")
        with pytest.raises(ValidationError, match="Invalid status transition"):
            update_order(order_id=1, body=body, db=db)

    @patch("lab_manager.api.routes.orders.index_order_record")
    def test_update_order_deleted_cannot_transition(self, mock_index):
        from lab_manager.api.routes.orders import update_order

        order = _make_order(id=1, status="deleted")
        db = _make_db()
        db.get.return_value = order

        body = OrderUpdate(status="pending")
        with pytest.raises(ValidationError, match="Invalid status transition"):
            update_order(order_id=1, body=body, db=db)
