"""Unit tests for inventory route — CRUD, lifecycle, validation, edge cases.

Uses MagicMock for DB sessions to isolate route logic from the database.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from lab_manager.api.routes.inventory import (
    AdjustBody,
    ConsumeBody,
    DisposeBody,
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    OpenBody,
    TransferBody,
    _INV_SORTABLE,
    _VALID_INV_STATUSES,
    _flatten_item,
    _format_quantity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(
    id: int = 1,
    product_id: int = 10,
    location_id: int | None = 20,
    lot_number: str | None = "LOT001",
    quantity_on_hand: Decimal = Decimal("100.0000"),
    unit: str | None = "mL",
    expiry_date: date | None = None,
    opened_date: date | None = None,
    status: str = "available",
    notes: str | None = None,
    received_by: str | None = "alice",
    order_item_id: int | None = None,
):
    """Create a mock InventoryItem."""
    item = MagicMock()
    item.id = id
    item.product_id = product_id
    item.location_id = location_id
    item.lot_number = lot_number
    item.quantity_on_hand = quantity_on_hand
    item.unit = unit
    item.expiry_date = expiry_date
    item.opened_date = opened_date
    item.status = status
    item.notes = notes
    item.received_by = received_by
    item.order_item_id = order_item_id
    # Joined relationships
    product = MagicMock()
    product.name = "Test Product"
    product.catalog_number = "CAT-001"
    product.category = "reagent"
    vendor = MagicMock()
    vendor.name = "Sigma-Aldrich"
    product.vendor = vendor
    product.is_hazardous = False
    item.product = product
    location = MagicMock()
    location.name = "Shelf A"
    item.location = location
    return item


def _make_db():
    """Create a mock DB session."""
    db = MagicMock()
    db.get.return_value = None
    db.add.return_value = None
    db.flush.return_value = None
    db.refresh.side_effect = lambda obj: None
    db.scalars.return_value = MagicMock()
    db.execute.return_value = MagicMock()
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
# Schema validation tests
# ---------------------------------------------------------------------------


class TestInventoryItemCreateValidation:
    """Test Pydantic model validation for InventoryItemCreate."""

    def test_valid_minimal(self):
        body = InventoryItemCreate(product_id=1)
        assert body.product_id == 1
        assert body.location_id is None
        assert body.quantity_on_hand == Decimal("0")
        assert body.status == "available"

    def test_valid_all_fields(self):
        body = InventoryItemCreate(
            product_id=5,
            location_id=2,
            lot_number="LOT-ABC",
            quantity_on_hand=Decimal("50.5"),
            unit="mL",
            expiry_date=date(2026, 12, 31),
            opened_date=date(2026, 1, 15),
            status="opened",
            notes="Test notes",
            received_by="bob",
            order_item_id=99,
        )
        assert body.product_id == 5
        assert body.quantity_on_hand == Decimal("50.5")
        assert body.status == "opened"

    def test_default_quantity_is_zero(self):
        body = InventoryItemCreate(product_id=1)
        assert body.quantity_on_hand == Decimal("0")

    def test_negative_quantity_rejected(self):
        with pytest.raises(Exception):
            InventoryItemCreate(product_id=1, quantity_on_hand=Decimal("-1"))

    def test_default_status_available(self):
        body = InventoryItemCreate(product_id=1)
        assert body.status == "available"

    def test_all_valid_statuses(self):
        for status in _VALID_INV_STATUSES:
            body = InventoryItemCreate(product_id=1, status=status)
            assert body.status == status

    def test_invalid_status_rejected(self):
        with pytest.raises(Exception):
            InventoryItemCreate(product_id=1, status="nonexistent")

    def test_lot_number_max_length(self):
        body = InventoryItemCreate(product_id=1, lot_number="A" * 100)
        assert len(body.lot_number) == 100

    def test_lot_number_exceeds_max_length(self):
        with pytest.raises(Exception):
            InventoryItemCreate(product_id=1, lot_number="A" * 101)

    def test_notes_max_length(self):
        body = InventoryItemCreate(product_id=1, notes="N" * 2000)
        assert len(body.notes) == 2000

    def test_notes_exceeds_max_length(self):
        with pytest.raises(Exception):
            InventoryItemCreate(product_id=1, notes="N" * 2001)

    def test_received_by_max_length(self):
        body = InventoryItemCreate(product_id=1, received_by="X" * 200)
        assert len(body.received_by) == 200

    def test_received_by_exceeds_max_length(self):
        with pytest.raises(Exception):
            InventoryItemCreate(product_id=1, received_by="X" * 201)

    def test_unit_max_length(self):
        body = InventoryItemCreate(product_id=1, unit="U" * 50)
        assert len(body.unit) == 50

    def test_unit_exceeds_max_length(self):
        with pytest.raises(Exception):
            InventoryItemCreate(product_id=1, unit="U" * 51)


class TestInventoryItemUpdateValidation:
    """Test Pydantic model validation for InventoryItemUpdate."""

    def test_all_none(self):
        body = InventoryItemUpdate()
        assert body.product_id is None
        assert body.status is None
        assert body.quantity_on_hand is None

    def test_partial_update(self):
        body = InventoryItemUpdate(status="opened")
        assert body.status == "opened"
        assert body.product_id is None

    def test_valid_status(self):
        for status in _VALID_INV_STATUSES:
            body = InventoryItemUpdate(status=status)
            assert body.status == status

    def test_invalid_status_rejected(self):
        with pytest.raises(Exception):
            InventoryItemUpdate(status="bad_status")

    def test_none_status_is_valid(self):
        body = InventoryItemUpdate(status=None)
        assert body.status is None

    def test_exclude_unset_behavior(self):
        body = InventoryItemUpdate(status="opened")
        dumped = body.model_dump(exclude_unset=True)
        assert "status" in dumped
        assert "product_id" not in dumped
        assert "quantity_on_hand" not in dumped


class TestConsumeBodyValidation:
    """Test ConsumeBody schema."""

    def test_valid(self):
        body = ConsumeBody(quantity=Decimal("10"), consumed_by="alice")
        assert body.quantity == Decimal("10")
        assert body.consumed_by == "alice"
        assert body.purpose is None

    def test_zero_quantity_rejected(self):
        with pytest.raises(Exception):
            ConsumeBody(quantity=Decimal("0"), consumed_by="alice")

    def test_negative_quantity_rejected(self):
        with pytest.raises(Exception):
            ConsumeBody(quantity=Decimal("-1"), consumed_by="alice")

    def test_with_purpose(self):
        body = ConsumeBody(
            quantity=Decimal("5"), consumed_by="bob", purpose="experiment"
        )
        assert body.purpose == "experiment"


class TestTransferBodyValidation:
    """Test TransferBody schema."""

    def test_valid(self):
        body = TransferBody(location_id=5, transferred_by="alice")
        assert body.location_id == 5
        assert body.transferred_by == "alice"


class TestAdjustBodyValidation:
    """Test AdjustBody schema."""

    def test_valid(self):
        body = AdjustBody(
            new_quantity=Decimal("50"), reason="cycle count", adjusted_by="alice"
        )
        assert body.new_quantity == Decimal("50")

    def test_zero_quantity_valid(self):
        body = AdjustBody(
            new_quantity=Decimal("0"), reason="depleted", adjusted_by="alice"
        )
        assert body.new_quantity == Decimal("0")

    def test_negative_quantity_rejected(self):
        with pytest.raises(Exception):
            AdjustBody(new_quantity=Decimal("-1"), reason="test", adjusted_by="alice")


class TestDisposeBodyValidation:
    """Test DisposeBody schema."""

    def test_valid(self):
        body = DisposeBody(reason="expired", disposed_by="alice")
        assert body.reason == "expired"

    def test_reason_max_length(self):
        body = DisposeBody(reason="R" * 500, disposed_by="alice")
        assert len(body.reason) == 500

    def test_reason_exceeds_max_length(self):
        with pytest.raises(Exception):
            DisposeBody(reason="R" * 501, disposed_by="alice")


class TestOpenBodyValidation:
    """Test OpenBody schema."""

    def test_valid(self):
        body = OpenBody(opened_by="alice")
        assert body.opened_by == "alice"

    def test_opened_by_max_length(self):
        body = OpenBody(opened_by="A" * 200)
        assert len(body.opened_by) == 200

    def test_opened_by_exceeds_max_length(self):
        with pytest.raises(Exception):
            OpenBody(opened_by="A" * 201)


# ---------------------------------------------------------------------------
# Constants tests
# ---------------------------------------------------------------------------


class TestSortableColumns:
    """Test _INV_SORTABLE set."""

    def test_contains_expected_columns(self):
        expected = {
            "id",
            "created_at",
            "updated_at",
            "product_id",
            "location_id",
            "quantity_on_hand",
            "expiry_date",
            "status",
        }
        assert _INV_SORTABLE == expected

    def test_is_a_set(self):
        assert isinstance(_INV_SORTABLE, set)


class TestValidStatuses:
    """Test _VALID_INV_STATUSES set."""

    def test_contains_all_enum_values(self):
        expected = {"available", "opened", "depleted", "disposed", "expired", "deleted"}
        assert _VALID_INV_STATUSES == expected

    def test_is_a_set(self):
        assert isinstance(_VALID_INV_STATUSES, set)


# ---------------------------------------------------------------------------
# _format_quantity helper
# ---------------------------------------------------------------------------


class TestFormatQuantity:
    """Test the _format_quantity helper."""

    def test_none_returns_zero(self):
        assert _format_quantity(None) == "0"

    def test_integer_decimal(self):
        assert _format_quantity(Decimal("1.0000")) == "1"

    def test_fractional_decimal(self):
        assert _format_quantity(Decimal("2.5000")) == "2.5"

    def test_zero(self):
        assert _format_quantity(Decimal("0")) == "0"

    def test_plain_string_number(self):
        assert _format_quantity("42") == "42"

    def test_large_number(self):
        assert _format_quantity(Decimal("12345.6789")) == "12345.6789"

    def test_trailing_zeros_stripped(self):
        assert _format_quantity(Decimal("100.00")) == "100"


# ---------------------------------------------------------------------------
# _flatten_item helper
# ---------------------------------------------------------------------------


class TestFlattenItem:
    """Test the _flatten_item helper."""

    def test_basic_flatten(self):
        item = _make_item(
            id=1,
            product_id=10,
            quantity_on_hand=Decimal("50.0000"),
            expiry_date=date(2026, 6, 1),
        )
        result = _flatten_item(item)
        assert result["id"] == 1
        assert result["product_id"] == 10
        assert result["product_name"] == "Test Product"
        assert result["catalog_number"] == "CAT-001"
        assert result["vendor_name"] == "Sigma-Aldrich"
        assert result["location_name"] == "Shelf A"
        assert result["quantity_on_hand"] == 50.0
        assert result["status"] == "available"
        assert result["expiry_date"] == "2026-06-01"

    def test_none_product(self):
        item = _make_item()
        item.product = None
        result = _flatten_item(item)
        assert result["product_name"] is None
        assert result["catalog_number"] is None
        assert result["vendor_name"] is None

    def test_none_location(self):
        item = _make_item()
        item.location = None
        result = _flatten_item(item)
        assert result["location_name"] is None
        assert result["location_id"] == 20

    def test_none_dates(self):
        item = _make_item(expiry_date=None, opened_date=None)
        result = _flatten_item(item)
        assert result["expiry_date"] is None
        assert result["opened_date"] is None

    def test_opened_date_format(self):
        item = _make_item(opened_date=date(2026, 3, 15))
        result = _flatten_item(item)
        assert result["opened_date"] == "2026-03-15"

    def test_none_quantity(self):
        item = _make_item()
        item.quantity_on_hand = None
        result = _flatten_item(item)
        assert result["quantity_on_hand"] == 0

    def test_quantity_display_format(self):
        item = _make_item(quantity_on_hand=Decimal("100.0000"))
        result = _flatten_item(item)
        assert result["quantity_display"] == "100"


# ---------------------------------------------------------------------------
# list_inventory route
# ---------------------------------------------------------------------------


class TestListInventory:
    """Test the GET / inventory list endpoint."""

    @patch("lab_manager.api.routes.inventory.paginate")
    @patch("lab_manager.api.routes.inventory.apply_sort")
    def test_basic_list_empty(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.inventory import list_inventory

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        result = list_inventory(
            page=1,
            page_size=50,
            product_id=None,
            location_id=None,
            status=None,
            expiring_before=None,
            search=None,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        assert result["total"] == 0
        assert result["items"] == []

    @patch("lab_manager.api.routes.inventory.paginate")
    @patch("lab_manager.api.routes.inventory.apply_sort")
    def test_list_with_items(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.inventory import list_inventory

        item = _make_item(id=1)
        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([item], total=1)
        db = _make_db()

        result = list_inventory(
            page=1,
            page_size=50,
            product_id=None,
            location_id=None,
            status=None,
            expiring_before=None,
            search=None,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        assert result["total"] == 1
        assert len(result["items"]) == 1
        assert result["items"][0]["id"] == 1

    @patch("lab_manager.api.routes.inventory.paginate")
    @patch("lab_manager.api.routes.inventory.apply_sort")
    def test_list_flattens_items(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.inventory import list_inventory

        item = _make_item(id=5, product_id=10)
        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([item], total=1)
        db = _make_db()

        result = list_inventory(
            page=1,
            page_size=50,
            product_id=None,
            location_id=None,
            status=None,
            expiring_before=None,
            search=None,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        flat = result["items"][0]
        assert "product_name" in flat
        assert "vendor_name" in flat
        assert "location_name" in flat
        assert "quantity_display" in flat

    @patch("lab_manager.api.routes.inventory.paginate")
    @patch("lab_manager.api.routes.inventory.apply_sort")
    def test_list_with_product_id_filter(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.inventory import list_inventory

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_inventory(
            page=1,
            page_size=50,
            product_id=5,
            location_id=None,
            status=None,
            expiring_before=None,
            search=None,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.inventory.paginate")
    @patch("lab_manager.api.routes.inventory.apply_sort")
    def test_list_with_location_id_filter(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.inventory import list_inventory

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_inventory(
            page=1,
            page_size=50,
            product_id=None,
            location_id=3,
            status=None,
            expiring_before=None,
            search=None,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.inventory.paginate")
    @patch("lab_manager.api.routes.inventory.apply_sort")
    def test_list_with_status_filter(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.inventory import list_inventory

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_inventory(
            page=1,
            page_size=50,
            product_id=None,
            location_id=None,
            status="available",
            expiring_before=None,
            search=None,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.inventory.paginate")
    @patch("lab_manager.api.routes.inventory.apply_sort")
    def test_list_with_expiring_before_filter(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.inventory import list_inventory

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_inventory(
            page=1,
            page_size=50,
            product_id=None,
            location_id=None,
            status=None,
            expiring_before=date(2026, 6, 1),
            search=None,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.inventory.paginate")
    @patch("lab_manager.api.routes.inventory.apply_sort")
    def test_list_with_search_filter(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.inventory import list_inventory

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_inventory(
            page=1,
            page_size=50,
            product_id=None,
            location_id=None,
            status=None,
            expiring_before=None,
            search="LOT001",
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.inventory.paginate")
    @patch("lab_manager.api.routes.inventory.apply_sort")
    def test_list_pagination_params(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.inventory import list_inventory

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result(
            [], total=0, page=2, page_size=10
        )
        db = _make_db()

        result = list_inventory(
            page=2,
            page_size=10,
            product_id=None,
            location_id=None,
            status=None,
            expiring_before=None,
            search=None,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        assert result["page"] == 2
        assert result["page_size"] == 10

    @patch("lab_manager.api.routes.inventory.paginate")
    @patch("lab_manager.api.routes.inventory.apply_sort")
    def test_list_sort_params_passed(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.inventory import list_inventory

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([])
        db = _make_db()

        list_inventory(
            page=1,
            page_size=50,
            product_id=None,
            location_id=None,
            status=None,
            expiring_before=None,
            search=None,
            sort_by="quantity_on_hand",
            sort_dir="desc",
            db=db,
        )
        mock_sort.assert_called_once()

    @patch("lab_manager.api.routes.inventory.paginate")
    @patch("lab_manager.api.routes.inventory.apply_sort")
    def test_list_all_filters_combined(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.inventory import list_inventory

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([])
        db = _make_db()

        list_inventory(
            product_id=1,
            location_id=2,
            status="available",
            expiring_before=date(2026, 12, 31),
            search="test",
            sort_by="id",
            sort_dir="asc",
            page=1,
            page_size=50,
            db=db,
        )
        mock_paginate.assert_called_once()


# ---------------------------------------------------------------------------
# create_inventory_item route
# ---------------------------------------------------------------------------


class TestCreateInventoryItem:
    """Test the POST / inventory create endpoint."""

    @patch("lab_manager.api.routes.inventory.index_inventory_record")
    def test_create_basic(self, mock_index):
        from lab_manager.api.routes.inventory import create_inventory_item

        db = _make_db()
        body = InventoryItemCreate(product_id=1)

        result = create_inventory_item(body=body, db=db)

        db.add.assert_called_once()
        db.flush.assert_called_once()
        db.refresh.assert_called_once()
        mock_index.assert_called_once()

    @patch("lab_manager.api.routes.inventory.index_inventory_record")
    def test_create_with_all_fields(self, mock_index):
        from lab_manager.api.routes.inventory import create_inventory_item

        db = _make_db()
        body = InventoryItemCreate(
            product_id=5,
            location_id=2,
            lot_number="LOT-XYZ",
            quantity_on_hand=Decimal("100.5"),
            unit="g",
            expiry_date=date(2026, 12, 31),
            status="available",
            notes="Fresh batch",
            received_by="charlie",
        )

        create_inventory_item(body=body, db=db)
        db.add.assert_called_once()

    @patch("lab_manager.api.routes.inventory.index_inventory_record")
    def test_create_uses_model_dump(self, mock_index):
        from lab_manager.api.routes.inventory import create_inventory_item

        db = _make_db()
        body = InventoryItemCreate(product_id=3, lot_number="LOT-999")

        create_inventory_item(body=body, db=db)

        added_obj = db.add.call_args[0][0]
        assert added_obj.product_id == 3
        assert added_obj.lot_number == "LOT-999"

    @patch("lab_manager.api.routes.inventory.index_inventory_record")
    def test_create_indexes_after_flush(self, mock_index):
        from lab_manager.api.routes.inventory import create_inventory_item

        db = _make_db()
        body = InventoryItemCreate(product_id=1)

        create_inventory_item(body=body, db=db)

        # index_inventory_record is called after flush+refresh
        mock_index.assert_called_once()
        # The argument passed to index_inventory_record is the added object
        indexed_item = mock_index.call_args[0][0]
        assert indexed_item.product_id == 1


# ---------------------------------------------------------------------------
# get_inventory_item route
# ---------------------------------------------------------------------------


class TestGetInventoryItem:
    """Test the GET /{item_id} endpoint."""

    def test_get_existing(self):
        from lab_manager.api.routes.inventory import get_inventory_item

        item = _make_item(id=42)
        db = _make_db()
        db.get.return_value = item

        result = get_inventory_item(item_id=42, db=db)
        assert result.id == 42

    def test_get_nonexistent_raises_not_found(self):
        from lab_manager.api.routes.inventory import get_inventory_item
        from lab_manager.exceptions import NotFoundError

        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            get_inventory_item(item_id=9999, db=db)

    def test_get_calls_db_with_correct_model(self):
        from lab_manager.api.routes.inventory import get_inventory_item
        from lab_manager.models.inventory import InventoryItem

        item = _make_item(id=5)
        db = _make_db()
        db.get.return_value = item

        get_inventory_item(item_id=5, db=db)
        db.get.assert_called_once_with(InventoryItem, 5)


# ---------------------------------------------------------------------------
# update_inventory_item route
# ---------------------------------------------------------------------------


class TestUpdateInventoryItem:
    """Test the PATCH /{item_id} endpoint."""

    @patch("lab_manager.api.routes.inventory.index_inventory_record")
    def test_update_status(self, mock_index):
        from lab_manager.api.routes.inventory import update_inventory_item

        item = _make_item(id=1, status="available")
        db = _make_db()
        db.get.return_value = item

        body = InventoryItemUpdate(status="opened")
        update_inventory_item(item_id=1, body=body, db=db)

        assert item.status == "opened"
        db.flush.assert_called_once()

    @patch("lab_manager.api.routes.inventory.index_inventory_record")
    def test_update_quantity(self, mock_index):
        from lab_manager.api.routes.inventory import update_inventory_item

        item = _make_item(id=1)
        db = _make_db()
        db.get.return_value = item

        body = InventoryItemUpdate(quantity_on_hand=Decimal("75"))
        update_inventory_item(item_id=1, body=body, db=db)

        assert item.quantity_on_hand == Decimal("75")

    @patch("lab_manager.api.routes.inventory.index_inventory_record")
    def test_update_notes(self, mock_index):
        from lab_manager.api.routes.inventory import update_inventory_item

        item = _make_item(id=1)
        db = _make_db()
        db.get.return_value = item

        body = InventoryItemUpdate(notes="Updated notes")
        update_inventory_item(item_id=1, body=body, db=db)

        assert item.notes == "Updated notes"

    @patch("lab_manager.api.routes.inventory.index_inventory_record")
    def test_update_nonexistent_raises_not_found(self, mock_index):
        from lab_manager.api.routes.inventory import update_inventory_item
        from lab_manager.exceptions import NotFoundError

        db = _make_db()
        db.get.return_value = None

        body = InventoryItemUpdate(status="opened")
        with pytest.raises(NotFoundError):
            update_inventory_item(item_id=9999, body=body, db=db)

    def test_update_deleted_item_raises_validation_error(self):
        from lab_manager.api.routes.inventory import update_inventory_item
        from lab_manager.exceptions import ValidationError

        item = _make_item(id=1, status="deleted")
        db = _make_db()
        db.get.return_value = item

        body = InventoryItemUpdate(notes="Try to update")
        with pytest.raises(ValidationError):
            update_inventory_item(item_id=1, body=body, db=db)

    def test_update_disposed_item_raises_validation_error(self):
        from lab_manager.api.routes.inventory import update_inventory_item
        from lab_manager.exceptions import ValidationError

        item = _make_item(id=1, status="disposed")
        db = _make_db()
        db.get.return_value = item

        body = InventoryItemUpdate(notes="Try to update")
        with pytest.raises(ValidationError):
            update_inventory_item(item_id=1, body=body, db=db)

    def test_update_depleted_item_raises_validation_error(self):
        from lab_manager.api.routes.inventory import update_inventory_item
        from lab_manager.exceptions import ValidationError

        item = _make_item(id=1, status="depleted")
        db = _make_db()
        db.get.return_value = item

        body = InventoryItemUpdate(notes="Try to update")
        with pytest.raises(ValidationError):
            update_inventory_item(item_id=1, body=body, db=db)

    @patch("lab_manager.api.routes.inventory.index_inventory_record")
    def test_partial_update_only_sets_provided_fields(self, mock_index):
        from lab_manager.api.routes.inventory import update_inventory_item

        item = _make_item(id=1, status="available")
        db = _make_db()
        db.get.return_value = item

        body = InventoryItemUpdate(status="opened")
        dumped = body.model_dump(exclude_unset=True)
        assert "status" in dumped
        assert "quantity_on_hand" not in dumped

        update_inventory_item(item_id=1, body=body, db=db)
        assert item.status == "opened"

    @patch("lab_manager.api.routes.inventory.index_inventory_record")
    def test_update_indexes_after_flush(self, mock_index):
        from lab_manager.api.routes.inventory import update_inventory_item

        item = _make_item(id=1, status="available")
        db = _make_db()
        db.get.return_value = item

        body = InventoryItemUpdate(status="opened")
        update_inventory_item(item_id=1, body=body, db=db)

        mock_index.assert_called_once()


# ---------------------------------------------------------------------------
# delete_inventory_item route
# ---------------------------------------------------------------------------


class TestDeleteInventoryItem:
    """Test the DELETE /{item_id} endpoint (soft delete)."""

    def test_delete_existing(self):
        from lab_manager.api.routes.inventory import delete_inventory_item

        item = _make_item(id=1, status="available")
        db = _make_db()
        db.get.return_value = item

        result = delete_inventory_item(item_id=1, db=db)
        assert result is None
        assert item.status == "deleted"
        db.flush.assert_called_once()

    def test_delete_nonexistent_raises_not_found(self):
        from lab_manager.api.routes.inventory import delete_inventory_item
        from lab_manager.exceptions import NotFoundError

        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            delete_inventory_item(item_id=9999, db=db)

    def test_soft_delete_sets_status(self):
        from lab_manager.api.routes.inventory import delete_inventory_item
        from lab_manager.models.inventory import InventoryStatus

        item = _make_item(id=5, status="available")
        db = _make_db()
        db.get.return_value = item

        delete_inventory_item(item_id=5, db=db)
        assert item.status == InventoryStatus.deleted


# ---------------------------------------------------------------------------
# low_stock route
# ---------------------------------------------------------------------------


class TestLowStock:
    """Test the GET /low-stock endpoint."""

    @patch("lab_manager.api.routes.inventory.inv_svc")
    def test_low_stock_delegates_to_service(self, mock_svc):
        from lab_manager.api.routes.inventory import low_stock

        mock_svc.get_low_stock.return_value = [
            {"product_id": 1, "name": "Reagent A", "total_quantity": 2},
        ]
        db = _make_db()

        result = low_stock(db=db)
        mock_svc.get_low_stock.assert_called_once_with(db)
        assert len(result) == 1

    @patch("lab_manager.api.routes.inventory.inv_svc")
    def test_low_stock_empty(self, mock_svc):
        from lab_manager.api.routes.inventory import low_stock

        mock_svc.get_low_stock.return_value = []
        db = _make_db()

        result = low_stock(db=db)
        assert result == []


# ---------------------------------------------------------------------------
# expiring route
# ---------------------------------------------------------------------------


class TestExpiring:
    """Test the GET /expiring endpoint."""

    @patch("lab_manager.api.routes.inventory.inv_svc")
    def test_expiring_default_30_days(self, mock_svc):
        from lab_manager.api.routes.inventory import expiring

        mock_svc.get_expiring.return_value = []
        db = _make_db()

        result = expiring(days=30, db=db)
        mock_svc.get_expiring.assert_called_once_with(db, days=30)
        assert result == []

    @patch("lab_manager.api.routes.inventory.inv_svc")
    def test_expiring_custom_days(self, mock_svc):
        from lab_manager.api.routes.inventory import expiring

        mock_svc.get_expiring.return_value = [_make_item(id=1)]
        db = _make_db()

        result = expiring(days=7, db=db)
        mock_svc.get_expiring.assert_called_once_with(db, days=7)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# item_history route
# ---------------------------------------------------------------------------


class TestItemHistory:
    """Test the GET /{item_id}/history endpoint."""

    @patch("lab_manager.api.routes.inventory.inv_svc")
    def test_history_delegates_to_service(self, mock_svc):
        from lab_manager.api.routes.inventory import item_history

        mock_svc.get_item_history.return_value = [
            {"action": "consume", "quantity_used": 5},
        ]
        db = _make_db()

        result = item_history(item_id=1, db=db)
        mock_svc.get_item_history.assert_called_once_with(1, db)
        assert len(result) == 1

    @patch("lab_manager.api.routes.inventory.inv_svc")
    def test_history_empty(self, mock_svc):
        from lab_manager.api.routes.inventory import item_history

        mock_svc.get_item_history.return_value = []
        db = _make_db()

        result = item_history(item_id=99, db=db)
        assert result == []


# ---------------------------------------------------------------------------
# consume_item route
# ---------------------------------------------------------------------------


class TestConsumeItem:
    """Test the POST /{item_id}/consume endpoint."""

    @patch("lab_manager.api.routes.inventory.inv_svc")
    def test_consume_basic(self, mock_svc):
        from lab_manager.api.routes.inventory import consume_item

        item = _make_item(
            id=1, product_id=10, quantity_on_hand=Decimal("90"), status="available"
        )
        item.product.is_hazardous = False
        mock_svc.consume.return_value = item
        db = _make_db()

        body = ConsumeBody(quantity=Decimal("10"), consumed_by="alice")
        result = consume_item(item_id=1, body=body, db=db)

        assert result["id"] == 1
        assert result["product_id"] == 10
        assert result["quantity_on_hand"] == 90.0
        assert result["status"] == "available"
        assert "safety_reminder" not in result
        mock_svc.consume.assert_called_once_with(1, Decimal("10"), "alice", None, db)

    @patch("lab_manager.api.routes.inventory.inv_svc")
    def test_consume_with_purpose(self, mock_svc):
        from lab_manager.api.routes.inventory import consume_item

        item = _make_item(id=1, quantity_on_hand=Decimal("50"), status="available")
        item.product.is_hazardous = False
        mock_svc.consume.return_value = item
        db = _make_db()

        body = ConsumeBody(
            quantity=Decimal("5"), consumed_by="bob", purpose="experiment"
        )
        result = consume_item(item_id=1, body=body, db=db)

        mock_svc.consume.assert_called_once_with(
            1, Decimal("5"), "bob", "experiment", db
        )

    @patch("lab_manager.api.routes.inventory.inv_svc")
    def test_consume_hazardous_item_adds_safety_reminder(self, mock_svc):
        from lab_manager.api.routes.inventory import consume_item

        item = _make_item(id=1, quantity_on_hand=Decimal("50"), status="available")
        item.product.is_hazardous = True
        item.product.id = 10
        item.product.name = "Dangerous Reagent"
        item.product.hazard_info = "H225 H314"
        mock_svc.consume.return_value = item
        db = _make_db()

        body = ConsumeBody(quantity=Decimal("5"), consumed_by="alice")
        result = consume_item(item_id=1, body=body, db=db)

        assert "safety_reminder" in result
        assert result["safety_reminder"]["product_id"] == 10
        assert result["safety_reminder"]["is_hazardous"] is True

    @patch("lab_manager.api.routes.inventory.inv_svc")
    def test_consume_non_hazardous_no_safety_reminder(self, mock_svc):
        from lab_manager.api.routes.inventory import consume_item

        item = _make_item(id=1, quantity_on_hand=Decimal("50"), status="available")
        item.product.is_hazardous = False
        mock_svc.consume.return_value = item
        db = _make_db()

        body = ConsumeBody(quantity=Decimal("5"), consumed_by="alice")
        result = consume_item(item_id=1, body=body, db=db)

        assert "safety_reminder" not in result


# ---------------------------------------------------------------------------
# transfer_item route
# ---------------------------------------------------------------------------


class TestTransferItem:
    """Test the POST /{item_id}/transfer endpoint."""

    @patch("lab_manager.api.routes.inventory.inv_svc")
    def test_transfer_basic(self, mock_svc):
        from lab_manager.api.routes.inventory import transfer_item

        item = _make_item(id=1, location_id=5)
        mock_svc.transfer.return_value = item
        db = _make_db()

        body = TransferBody(location_id=10, transferred_by="alice")
        result = transfer_item(item_id=1, body=body, db=db)

        mock_svc.transfer.assert_called_once_with(1, 10, "alice", db)
        assert result == item


# ---------------------------------------------------------------------------
# adjust_item route
# ---------------------------------------------------------------------------


class TestAdjustItem:
    """Test the POST /{item_id}/adjust endpoint."""

    @patch("lab_manager.api.routes.inventory.inv_svc")
    def test_adjust_basic(self, mock_svc):
        from lab_manager.api.routes.inventory import adjust_item

        item = _make_item(id=1, quantity_on_hand=Decimal("50"))
        mock_svc.adjust.return_value = item
        db = _make_db()

        body = AdjustBody(
            new_quantity=Decimal("50"), reason="cycle count", adjusted_by="alice"
        )
        result = adjust_item(item_id=1, body=body, db=db)

        mock_svc.adjust.assert_called_once_with(
            1, Decimal("50"), "cycle count", "alice", db
        )
        assert result == item


# ---------------------------------------------------------------------------
# dispose_item route
# ---------------------------------------------------------------------------


class TestDisposeItem:
    """Test the POST /{item_id}/dispose endpoint."""

    @patch("lab_manager.api.routes.inventory.inv_svc")
    def test_dispose_basic(self, mock_svc):
        from lab_manager.api.routes.inventory import dispose_item

        item = _make_item(id=1, status="disposed")
        mock_svc.dispose.return_value = item
        db = _make_db()

        body = DisposeBody(reason="expired", disposed_by="alice")
        result = dispose_item(item_id=1, body=body, db=db)

        mock_svc.dispose.assert_called_once_with(1, "expired", "alice", db)
        assert result == item


# ---------------------------------------------------------------------------
# open_item route
# ---------------------------------------------------------------------------


class TestOpenItem:
    """Test the POST /{item_id}/open endpoint."""

    @patch("lab_manager.api.routes.inventory.inv_svc")
    def test_open_basic(self, mock_svc):
        from lab_manager.api.routes.inventory import open_item

        item = _make_item(id=1, status="opened")
        mock_svc.open_item.return_value = item
        db = _make_db()

        body = OpenBody(opened_by="alice")
        result = open_item(item_id=1, body=body, db=db)

        mock_svc.open_item.assert_called_once_with(1, "alice", db)
        assert result == item


# ---------------------------------------------------------------------------
# get_reorder_url_endpoint route
# ---------------------------------------------------------------------------


class TestGetReorderUrl:
    """Test the GET /{item_id}/reorder-url endpoint."""

    @patch("lab_manager.api.routes.inventory.get_reorder_url")
    def test_reorder_url_with_known_vendor(self, mock_get_url):
        from lab_manager.api.routes.inventory import get_reorder_url_endpoint

        item = _make_item(id=1)
        item.product.catalog_number = "S1234"
        item.product.vendor.name = "Sigma-Aldrich"
        mock_get_url.return_value = "https://www.sigmaaldrich.com/US/en/search/S1234"
        db = _make_db()
        db.get.return_value = item

        result = get_reorder_url_endpoint(item_id=1, db=db)

        assert result["url"] == "https://www.sigmaaldrich.com/US/en/search/S1234"
        assert result["vendor"] == "Sigma-Aldrich"
        assert result["catalog_number"] == "S1234"
        mock_get_url.assert_called_once_with("Sigma-Aldrich", "S1234")

    @patch("lab_manager.api.routes.inventory.get_reorder_url")
    def test_reorder_url_no_product(self, mock_get_url):
        from lab_manager.api.routes.inventory import get_reorder_url_endpoint

        item = _make_item(id=1)
        item.product = None
        mock_get_url.return_value = None
        db = _make_db()
        db.get.return_value = item

        result = get_reorder_url_endpoint(item_id=1, db=db)

        assert result["url"] is None
        assert result["vendor"] is None
        assert result["catalog_number"] is None
        mock_get_url.assert_called_once_with("", "")

    @patch("lab_manager.api.routes.inventory.get_reorder_url")
    def test_reorder_url_no_vendor(self, mock_get_url):
        from lab_manager.api.routes.inventory import get_reorder_url_endpoint

        item = _make_item(id=1)
        item.product.vendor = None
        item.product.catalog_number = "CAT-001"
        mock_get_url.return_value = None
        db = _make_db()
        db.get.return_value = item

        result = get_reorder_url_endpoint(item_id=1, db=db)

        assert result["vendor"] is None
        assert result["catalog_number"] == "CAT-001"
        mock_get_url.assert_called_once_with("", "CAT-001")

    def test_reorder_url_nonexistent_item_raises_not_found(self):
        from lab_manager.api.routes.inventory import get_reorder_url_endpoint
        from lab_manager.exceptions import NotFoundError

        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            get_reorder_url_endpoint(item_id=9999, db=db)

    @patch("lab_manager.api.routes.inventory.get_reorder_url")
    def test_reorder_url_product_no_catalog(self, mock_get_url):
        from lab_manager.api.routes.inventory import get_reorder_url_endpoint

        item = _make_item(id=1)
        item.product.catalog_number = None
        item.product.vendor.name = "Sigma-Aldrich"
        mock_get_url.return_value = None
        db = _make_db()
        db.get.return_value = item

        result = get_reorder_url_endpoint(item_id=1, db=db)

        assert result["catalog_number"] is None
        mock_get_url.assert_called_once_with("Sigma-Aldrich", "")


# ---------------------------------------------------------------------------
# InventoryItemResponse schema
# ---------------------------------------------------------------------------


class TestInventoryItemResponseSchema:
    """Test InventoryItemResponse Pydantic model."""

    def test_from_attributes(self):
        item = _make_item(
            id=1,
            product_id=10,
            quantity_on_hand=Decimal("50"),
            status="available",
        )
        item.extra = {}
        item.created_at = "2026-01-01T00:00:00Z"
        item.updated_at = "2026-01-01T00:00:00Z"

        resp = InventoryItemResponse.model_validate(item)
        assert resp.id == 1
        assert resp.product_id == 10
        assert resp.status == "available"

    def test_optional_fields_default_none(self):
        item = _make_item(
            id=1, product_id=10, quantity_on_hand=Decimal("0"), status="available"
        )
        item.extra = {}
        item.created_at = None
        item.updated_at = None

        resp = InventoryItemResponse.model_validate(item)
        assert resp.location_id is not None  # _make_item defaults to 20
        assert resp.lot_number is not None  # _make_item defaults to "LOT001"
        assert resp.extra == {}
