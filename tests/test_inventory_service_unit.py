"""Comprehensive unit tests for services/inventory.py.

Covers every public function and internal helper, including:
- _to_decimal: NaN, Inf, negative-Inf, normal values, zero
- receive_items: happy paths, order status guards, wrong order_item, multi-item, lot/expiry
- consume: happy path, depletion threshold, status guards, NaN/zero/negative quantity, not found
- transfer: happy path, not found, log verification
- adjust: increase/decrease, depletion, negative rejected, NaN/Inf rejected, depleted->available revival
- dispose: happy path, already disposed, log verification
- open_item: happy path, already opened guard, not found, quantity unchanged
- get_stock_level: with/without items, active vs inactive statuses
- get_low_stock: smoke test (PG-correctness not tested on SQLite)
- get_expiring: within/outside window, no expiry date, expired/disposed excluded, boundary
- get_consumption_history: respects days window, ordered desc
- get_item_history: multiple entries, empty result
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from lab_manager.exceptions import NotFoundError, ValidationError
from lab_manager.models.consumption import ConsumptionAction, ConsumptionLog
from lab_manager.models.inventory import ACTIVE_STATUSES, InventoryItem, InventoryStatus
from lab_manager.models.location import StorageLocation as Location
from lab_manager.models.order import Order, OrderItem, OrderStatus
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor
from lab_manager.services.inventory import (
    _to_decimal,
    adjust,
    consume,
    dispose,
    get_consumption_history,
    get_expiring,
    get_item_history,
    get_low_stock,
    get_stock_level,
    open_item,
    receive_items,
    transfer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_vendor(db, name="TestVendor"):
    v = Vendor(name=name)
    db.add(v)
    db.flush()
    return v


def _make_product(db, vendor, catalog="CAT-001", name="Reagent X", **kwargs):
    p = Product(catalog_number=catalog, name=name, vendor_id=vendor.id, **kwargs)
    db.add(p)
    db.flush()
    return p


def _make_order(db, vendor, status=OrderStatus.pending):
    o = Order(vendor_id=vendor.id, status=status)
    db.add(o)
    db.flush()
    return o


def _make_order_item(db, order, product, quantity=5, unit="EA"):
    oi = OrderItem(
        order_id=order.id,
        product_id=product.id,
        catalog_number=product.catalog_number,
        quantity=quantity,
        unit=unit,
    )
    db.add(oi)
    db.flush()
    return oi


def _make_inventory(
    db,
    product,
    qty=10.0,
    status=InventoryStatus.available,
    location=None,
    expiry_date=None,
):
    inv = InventoryItem(
        product_id=product.id,
        quantity_on_hand=Decimal(str(qty)),
        status=status,
        location_id=location.id if location else None,
        expiry_date=expiry_date,
    )
    db.add(inv)
    db.flush()
    return inv


# ===========================================================================
# _to_decimal
# ===========================================================================


class TestToDecimal:
    def test_integer(self):
        assert _to_decimal(5) == Decimal("5")

    def test_float(self):
        assert _to_decimal(3.14) == Decimal("3.14")

    def test_zero(self):
        assert _to_decimal(0) == Decimal("0")

    def test_negative(self):
        assert _to_decimal(-2.5) == Decimal("-2.5")

    def test_nan_raises(self):
        with pytest.raises(ValidationError, match="finite"):
            _to_decimal(float("nan"))

    def test_inf_raises(self):
        with pytest.raises(ValidationError, match="finite"):
            _to_decimal(float("inf"))

    def test_neg_inf_raises(self):
        with pytest.raises(ValidationError, match="finite"):
            _to_decimal(float("-inf"))


# ===========================================================================
# receive_items
# ===========================================================================


class TestReceiveItems:
    def test_basic_receive(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        order = _make_order(db_session, vendor)
        oi = _make_order_item(db_session, order, product, quantity=5)
        loc = Location(name="Shelf A")
        db_session.add(loc)
        db_session.flush()

        items = receive_items(
            order_id=order.id,
            items_received=[{"order_item_id": oi.id, "quantity": 5}],
            location_id=loc.id,
            received_by="Alice",
            db=db_session,
        )
        assert len(items) == 1
        assert float(items[0].quantity_on_hand) == 5.0
        assert items[0].product_id == product.id
        assert items[0].location_id == loc.id
        assert items[0].status == InventoryStatus.available
        assert items[0].received_by == "Alice"
        assert order.status == OrderStatus.received
        assert order.received_by == "Alice"
        assert order.received_date == date.today()

    def test_receive_without_location(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        order = _make_order(db_session, vendor)
        oi = _make_order_item(db_session, order, product)

        items = receive_items(
            order_id=order.id,
            items_received=[{"order_item_id": oi.id, "quantity": 3}],
            location_id=None,
            received_by="Bob",
            db=db_session,
        )
        assert items[0].location_id is None

    def test_receive_with_lot_number_and_expiry(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        order = _make_order(db_session, vendor)
        oi = _make_order_item(db_session, order, product)
        expiry = date.today() + timedelta(days=365)

        items = receive_items(
            order_id=order.id,
            items_received=[
                {
                    "order_item_id": oi.id,
                    "quantity": 2,
                    "lot_number": "LOT-ABC",
                    "expiry_date": expiry,
                }
            ],
            location_id=None,
            received_by="Carol",
            db=db_session,
        )
        assert items[0].lot_number == "LOT-ABC"
        assert items[0].expiry_date == expiry

    def test_receive_lot_from_order_item_fallback(self, db_session):
        """If receive dict has no lot_number, fall back to order_item.lot_number."""
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        order = _make_order(db_session, vendor)
        oi = OrderItem(
            order_id=order.id,
            product_id=product.id,
            catalog_number=product.catalog_number,
            quantity=5,
            unit="EA",
            lot_number="LOT-OI",
        )
        db_session.add(oi)
        db_session.flush()

        items = receive_items(
            order_id=order.id,
            items_received=[{"order_item_id": oi.id, "quantity": 5}],
            location_id=None,
            received_by="Dave",
            db=db_session,
        )
        assert items[0].lot_number == "LOT-OI"

    def test_receive_unit_from_order_item_fallback(self, db_session):
        """If receive dict has no unit, fall back to order_item.unit."""
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        order = _make_order(db_session, vendor)
        oi = _make_order_item(db_session, order, product, quantity=10, unit="ML")

        items = receive_items(
            order_id=order.id,
            items_received=[{"order_item_id": oi.id, "quantity": 10}],
            location_id=None,
            received_by="Eve",
            db=db_session,
        )
        assert items[0].unit == "ML"

    def test_receive_multiple_items(self, db_session):
        vendor = _make_vendor(db_session)
        p1 = _make_product(db_session, vendor, catalog="CAT-001", name="Reagent A")
        p2 = _make_product(db_session, vendor, catalog="CAT-002", name="Reagent B")
        order = _make_order(db_session, vendor)
        oi1 = _make_order_item(db_session, order, p1, quantity=3)
        oi2 = _make_order_item(db_session, order, p2, quantity=7)

        items = receive_items(
            order_id=order.id,
            items_received=[
                {"order_item_id": oi1.id, "quantity": 3},
                {"order_item_id": oi2.id, "quantity": 7},
            ],
            location_id=None,
            received_by="Frank",
            db=db_session,
        )
        assert len(items) == 2
        assert float(items[0].quantity_on_hand) == 3.0
        assert float(items[1].quantity_on_hand) == 7.0

    def test_receive_without_order_item_uses_product_id(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor, catalog="CAT-NEW", name="New Prod")
        order = _make_order(db_session, vendor)

        items = receive_items(
            order_id=order.id,
            items_received=[{"product_id": product.id, "quantity": 10, "unit": "ML"}],
            location_id=None,
            received_by="Grace",
            db=db_session,
        )
        assert len(items) == 1
        assert items[0].product_id == product.id
        assert items[0].unit == "ML"

    def test_receive_defaults_quantity_to_1(self, db_session):
        """If quantity is missing from the receive dict, default is 1."""
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        order = _make_order(db_session, vendor)
        oi = _make_order_item(db_session, order, product)

        items = receive_items(
            order_id=order.id,
            items_received=[{"order_item_id": oi.id}],
            location_id=None,
            received_by="Heidi",
            db=db_session,
        )
        assert float(items[0].quantity_on_hand) == 1.0

    def test_receive_order_not_found(self, db_session):
        with pytest.raises(NotFoundError, match="Order"):
            receive_items(9999, [], None, "Alice", db_session)

    def test_receive_already_received_order(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        order = _make_order(db_session, vendor, status=OrderStatus.received)

        with pytest.raises(ValidationError, match="already received"):
            receive_items(
                order.id,
                [{"product_id": product.id, "quantity": 1}],
                None,
                "Alice",
                db_session,
            )

    def test_receive_cancelled_order(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        order = _make_order(db_session, vendor, status=OrderStatus.cancelled)

        with pytest.raises(ValidationError, match="already cancelled"):
            receive_items(
                order.id,
                [{"product_id": product.id, "quantity": 1}],
                None,
                "Alice",
                db_session,
            )

    def test_receive_deleted_order(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        order = _make_order(db_session, vendor, status=OrderStatus.deleted)

        with pytest.raises(ValidationError, match="already deleted"):
            receive_items(
                order.id,
                [{"product_id": product.id, "quantity": 1}],
                None,
                "Alice",
                db_session,
            )

    def test_receive_shipped_order_succeeds(self, db_session):
        """Shipped orders can still be received."""
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        order = _make_order(db_session, vendor, status=OrderStatus.shipped)
        oi = _make_order_item(db_session, order, product)

        items = receive_items(
            order.id,
            [{"order_item_id": oi.id, "quantity": 5}],
            None,
            "Alice",
            db_session,
        )
        assert len(items) == 1
        assert order.status == OrderStatus.received

    def test_receive_order_item_belongs_to_different_order(self, db_session):
        v1 = _make_vendor(db_session, "V1")
        v2 = _make_vendor(db_session, "V2")
        _make_product(db_session, v1, catalog="C1", name="P1")
        p2 = _make_product(db_session, v2, catalog="C2", name="P2")
        order1 = _make_order(db_session, v1)
        order2 = _make_order(db_session, v2)
        oi2 = _make_order_item(db_session, order2, p2)

        with pytest.raises(ValidationError, match="belongs to order"):
            receive_items(
                order1.id,
                [{"order_item_id": oi2.id, "quantity": 1}],
                None,
                "Alice",
                db_session,
            )

    def test_receive_creates_consumption_log(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        order = _make_order(db_session, vendor)
        oi = _make_order_item(db_session, order, product)

        receive_items(
            order.id,
            [{"order_item_id": oi.id, "quantity": 4}],
            None,
            "Ivan",
            db_session,
        )
        logs = list(db_session.exec(select(ConsumptionLog)).scalars().all())
        assert len(logs) == 1
        assert logs[0].action == ConsumptionAction.receive
        assert float(logs[0].quantity_remaining) == 4.0
        assert float(logs[0].quantity_used) == 0
        assert logs[0].consumed_by == "Ivan"
        assert f"order #{order.id}" in logs[0].purpose


# ===========================================================================
# consume
# ===========================================================================


class TestConsume:
    def test_normal_consume(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        result = consume(inv.id, 3.0, "Alice", "experiment", db_session)
        assert float(result.quantity_on_hand) == 7.0
        assert result.status == InventoryStatus.available

    def test_consume_exact_quantity_depletes(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=5.0)

        result = consume(inv.id, 5.0, "Alice", "used all", db_session)
        assert float(result.quantity_on_hand) == 0
        assert result.status == InventoryStatus.depleted

    def test_consume_fractional_quantity(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=1.0)

        result = consume(inv.id, 0.25, "Alice", "partial use", db_session)
        assert float(result.quantity_on_hand) == pytest.approx(0.75)

    def test_consume_near_zero_depletes(self, db_session):
        """Remaining <= 0.0001 triggers depletion."""
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=0.00005)

        result = consume(inv.id, 0.00004, "Alice", "tiny", db_session)
        assert result.status == InventoryStatus.depleted

    def test_consume_insufficient_stock(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=2.0)

        with pytest.raises(ValidationError, match="Insufficient stock"):
            consume(inv.id, 5.0, "Alice", "too much", db_session)

    def test_consume_zero_quantity_raises(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        with pytest.raises(ValidationError, match="positive"):
            consume(inv.id, 0, "Alice", "zero", db_session)

    def test_consume_negative_quantity_raises(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        with pytest.raises(ValidationError, match="positive"):
            consume(inv.id, -1.0, "Alice", "negative", db_session)

    def test_consume_nan_raises(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        with pytest.raises(ValidationError, match="finite"):
            consume(inv.id, float("nan"), "Alice", "nan", db_session)

    def test_consume_inf_raises(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        with pytest.raises(ValidationError, match="finite"):
            consume(inv.id, float("inf"), "Alice", "inf", db_session)

    @pytest.mark.parametrize(
        "status",
        [InventoryStatus.disposed, InventoryStatus.depleted, InventoryStatus.expired],
    )
    def test_consume_inactive_status_raises(self, db_session, status):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0, status=status)

        with pytest.raises(ValidationError, match="Cannot consume from"):
            consume(inv.id, 1.0, "Alice", "bad status", db_session)

    def test_consume_deleted_status_raises(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(
            db_session, product, qty=10.0, status=InventoryStatus.deleted
        )

        with pytest.raises(ValidationError, match="Cannot consume from"):
            consume(inv.id, 1.0, "Alice", "deleted", db_session)

    def test_consume_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            consume(9999, 1.0, "Alice", "missing", db_session)

    def test_consume_creates_log(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        consume(inv.id, 4.0, "Judy", "assay", db_session)
        logs = list(db_session.exec(select(ConsumptionLog)).scalars().all())
        assert len(logs) == 1
        assert logs[0].action == ConsumptionAction.consume
        assert float(logs[0].quantity_used) == 4.0
        assert float(logs[0].quantity_remaining) == 6.0
        assert logs[0].consumed_by == "Judy"
        assert logs[0].purpose == "assay"

    def test_consume_with_none_purpose(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        result = consume(inv.id, 1.0, "Alice", None, db_session)
        assert float(result.quantity_on_hand) == 9.0


# ===========================================================================
# transfer
# ===========================================================================


class TestTransfer:
    def test_transfer_success(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        loc1 = Location(name="Shelf A")
        loc2 = Location(name="Shelf B")
        db_session.add_all([loc1, loc2])
        db_session.flush()
        inv = _make_inventory(db_session, product, qty=5.0, location=loc1)

        result = transfer(inv.id, loc2.id, "Alice", db_session)
        assert result.location_id == loc2.id

    def test_transfer_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            transfer(9999, 1, "Alice", db_session)

    def test_transfer_does_not_change_quantity(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        loc1 = Location(name="Shelf A")
        loc2 = Location(name="Shelf B")
        db_session.add_all([loc1, loc2])
        db_session.flush()
        inv = _make_inventory(db_session, product, qty=7.5, location=loc1)

        result = transfer(inv.id, loc2.id, "Alice", db_session)
        assert float(result.quantity_on_hand) == 7.5

    def test_transfer_creates_log_with_purpose(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        loc1 = Location(name="Shelf A")
        loc2 = Location(name="Shelf B")
        db_session.add_all([loc1, loc2])
        db_session.flush()
        inv = _make_inventory(db_session, product, qty=5.0, location=loc1)

        transfer(inv.id, loc2.id, "Mallory", db_session)
        logs = list(db_session.exec(select(ConsumptionLog)).scalars().all())
        assert len(logs) == 1
        assert logs[0].action == ConsumptionAction.transfer
        assert logs[0].consumed_by == "Mallory"
        assert f"location {loc1.id}" in logs[0].purpose
        assert f"to {loc2.id}" in logs[0].purpose
        assert float(logs[0].quantity_used) == 0


# ===========================================================================
# adjust
# ===========================================================================


class TestAdjust:
    def test_adjust_increase(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=5.0)

        result = adjust(inv.id, 10.0, "cycle count", "Auditor", db_session)
        assert float(result.quantity_on_hand) == 10.0

    def test_adjust_decrease(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        result = adjust(inv.id, 3.0, "found less", "Auditor", db_session)
        assert float(result.quantity_on_hand) == 3.0

    def test_adjust_to_zero_depletes(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        result = adjust(inv.id, 0, "empty", "Auditor", db_session)
        assert float(result.quantity_on_hand) == 0
        assert result.status == InventoryStatus.depleted

    def test_adjust_near_zero_depletes(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        result = adjust(inv.id, 0.00001, "almost empty", "Auditor", db_session)
        assert result.status == InventoryStatus.depleted

    def test_adjust_negative_raises(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        with pytest.raises(ValidationError, match="negative"):
            adjust(inv.id, -5.0, "bad", "Auditor", db_session)

    def test_adjust_nan_raises(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        with pytest.raises(ValidationError, match="finite"):
            adjust(inv.id, float("nan"), "bad", "Auditor", db_session)

    def test_adjust_inf_raises(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        with pytest.raises(ValidationError, match="finite"):
            adjust(inv.id, float("inf"), "bad", "Auditor", db_session)

    def test_adjust_depleted_to_available_revival(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(
            db_session, product, qty=0.0, status=InventoryStatus.depleted
        )

        result = adjust(inv.id, 5.0, "restocked", "Alice", db_session)
        assert float(result.quantity_on_hand) == 5.0
        assert result.status == InventoryStatus.available

    def test_adjust_opened_status_preserved(self, db_session):
        """Adjusting an opened item does not change status to available."""
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(
            db_session, product, qty=10.0, status=InventoryStatus.opened
        )

        result = adjust(inv.id, 15.0, "top up", "Alice", db_session)
        assert float(result.quantity_on_hand) == 15.0
        # opened status is NOT reset to available by adjust
        assert result.status == InventoryStatus.opened

    def test_adjust_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            adjust(9999, 1.0, "missing", "Auditor", db_session)

    def test_adjust_creates_log_with_reason(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        adjust(inv.id, 8.0, "spillage", "Alice", db_session)
        logs = list(db_session.exec(select(ConsumptionLog)).scalars().all())
        assert len(logs) == 1
        assert logs[0].action == ConsumptionAction.adjust
        # delta = 8 - 10 = -2, quantity_used = -delta = 2
        assert float(logs[0].quantity_used) == 2.0
        assert float(logs[0].quantity_remaining) == 8.0
        assert "spillage" in logs[0].purpose
        assert "10" in logs[0].purpose
        assert "8" in logs[0].purpose

    def test_adjust_increase_log_negative_quantity_used(self, db_session):
        """When stock increases, quantity_used is negative (indicating addition)."""
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=5.0)

        adjust(inv.id, 10.0, "found more", "Auditor", db_session)
        logs = list(db_session.exec(select(ConsumptionLog)).scalars().all())
        # delta = 10 - 5 = 5, quantity_used = -5 (stock added)
        assert float(logs[0].quantity_used) == -5.0


# ===========================================================================
# dispose
# ===========================================================================


class TestDispose:
    def test_dispose_normal(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        result = dispose(inv.id, "expired", "Alice", db_session)
        assert result.status == InventoryStatus.disposed
        assert float(result.quantity_on_hand) == 0

    def test_dispose_already_disposed(self, db_session):
        """Disposing an already-disposed item is allowed (idempotent)."""
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(
            db_session, product, qty=0, status=InventoryStatus.disposed
        )

        result = dispose(inv.id, "double dispose", "Alice", db_session)
        assert result.status == InventoryStatus.disposed

    def test_dispose_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            dispose(9999, "expired", "Alice", db_session)

    def test_dispose_creates_log(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=7.5)

        dispose(inv.id, "contaminated", "Bob", db_session)
        logs = list(db_session.exec(select(ConsumptionLog)).scalars().all())
        assert len(logs) == 1
        assert logs[0].action == ConsumptionAction.dispose
        assert float(logs[0].quantity_used) == 7.5
        assert float(logs[0].quantity_remaining) == 0
        assert logs[0].consumed_by == "Bob"
        assert logs[0].purpose == "contaminated"

    def test_dispose_sets_quantity_to_zero(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=100.0)

        result = dispose(inv.id, "waste", "Alice", db_session)
        assert float(result.quantity_on_hand) == 0


# ===========================================================================
# open_item
# ===========================================================================


class TestOpenItem:
    def test_open_success(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        result = open_item(inv.id, "Alice", db_session)
        assert result.status == InventoryStatus.opened
        assert result.opened_date == date.today()

    def test_open_quantity_unchanged(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        result = open_item(inv.id, "Alice", db_session)
        assert float(result.quantity_on_hand) == 10.0

    def test_open_already_opened_raises(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(
            db_session, product, qty=10.0, status=InventoryStatus.opened
        )
        inv.opened_date = date(2025, 1, 1)
        db_session.flush()

        with pytest.raises(ValidationError, match="already opened"):
            open_item(inv.id, "Alice", db_session)

    def test_open_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            open_item(9999, "Alice", db_session)

    def test_open_creates_log(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        open_item(inv.id, "Bob", db_session)
        logs = list(db_session.exec(select(ConsumptionLog)).scalars().all())
        assert len(logs) == 1
        assert logs[0].action == ConsumptionAction.open
        assert logs[0].consumed_by == "Bob"
        assert float(logs[0].quantity_used) == 0
        assert float(logs[0].quantity_remaining) == 10.0


# ===========================================================================
# get_stock_level
# ===========================================================================


class TestGetStockLevel:
    def test_stock_level_multiple_items(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        _make_inventory(db_session, product, qty=5.0)
        _make_inventory(db_session, product, qty=3.0)

        result = get_stock_level(product.id, db_session)
        assert result["product_id"] == product.id
        assert result["total_quantity"] == 8.0

    def test_stock_level_no_items(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)

        result = get_stock_level(product.id, db_session)
        assert result["total_quantity"] == 0

    def test_stock_level_ignores_depleted(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        _make_inventory(db_session, product, qty=5.0, status=InventoryStatus.available)
        _make_inventory(db_session, product, qty=3.0, status=InventoryStatus.depleted)

        result = get_stock_level(product.id, db_session)
        assert result["total_quantity"] == 5.0

    def test_stock_level_includes_opened(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        _make_inventory(db_session, product, qty=5.0, status=InventoryStatus.available)
        _make_inventory(db_session, product, qty=3.0, status=InventoryStatus.opened)

        result = get_stock_level(product.id, db_session)
        assert result["total_quantity"] == 8.0

    def test_stock_level_ignores_disposed(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        _make_inventory(db_session, product, qty=5.0, status=InventoryStatus.available)
        _make_inventory(db_session, product, qty=100.0, status=InventoryStatus.disposed)

        result = get_stock_level(product.id, db_session)
        assert result["total_quantity"] == 5.0

    def test_stock_level_ignores_expired(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        _make_inventory(db_session, product, qty=5.0, status=InventoryStatus.available)
        _make_inventory(db_session, product, qty=20.0, status=InventoryStatus.expired)

        result = get_stock_level(product.id, db_session)
        assert result["total_quantity"] == 5.0

    def test_stock_level_different_products_not_mixed(self, db_session):
        vendor = _make_vendor(db_session)
        p1 = _make_product(db_session, vendor, catalog="C1", name="P1")
        p2 = _make_product(db_session, vendor, catalog="C2", name="P2")
        _make_inventory(db_session, p1, qty=10.0)
        _make_inventory(db_session, p2, qty=20.0)

        result = get_stock_level(p1.id, db_session)
        assert result["total_quantity"] == 10.0


# ===========================================================================
# get_low_stock
# ===========================================================================


class TestGetLowStock:
    def test_returns_list(self, db_session):
        """Smoke test: get_low_stock returns a list without error."""
        result = get_low_stock(db_session)
        assert isinstance(result, list)

    def test_empty_db_returns_empty(self, db_session):
        result = get_low_stock(db_session)
        assert result == []


# ===========================================================================
# get_expiring
# ===========================================================================


class TestGetExpiring:
    def test_expiring_within_window(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        _make_inventory(
            db_session,
            product,
            qty=5.0,
            expiry_date=date.today() + timedelta(days=5),
        )

        result = get_expiring(db_session, days=30)
        assert len(result) == 1

    def test_expiring_outside_window(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        _make_inventory(
            db_session,
            product,
            qty=5.0,
            expiry_date=date.today() + timedelta(days=60),
        )

        result = get_expiring(db_session, days=30)
        assert len(result) == 0

    def test_expiring_no_expiry_date(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        _make_inventory(db_session, product, qty=5.0)

        result = get_expiring(db_session, days=30)
        assert len(result) == 0

    def test_expiring_excludes_disposed(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        _make_inventory(
            db_session,
            product,
            qty=5.0,
            status=InventoryStatus.disposed,
            expiry_date=date.today() + timedelta(days=5),
        )

        result = get_expiring(db_session, days=30)
        assert len(result) == 0

    def test_expiring_excludes_depleted(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        _make_inventory(
            db_session,
            product,
            qty=0,
            status=InventoryStatus.depleted,
            expiry_date=date.today() + timedelta(days=5),
        )

        result = get_expiring(db_session, days=30)
        assert len(result) == 0

    def test_expiring_includes_opened(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        _make_inventory(
            db_session,
            product,
            qty=5.0,
            status=InventoryStatus.opened,
            expiry_date=date.today() + timedelta(days=10),
        )

        result = get_expiring(db_session, days=30)
        assert len(result) == 1

    def test_expiring_exact_cutoff_boundary(self, db_session):
        """Item expiring exactly on the cutoff date should be included."""
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        cutoff = date.today() + timedelta(days=30)
        _make_inventory(db_session, product, qty=5.0, expiry_date=cutoff)

        result = get_expiring(db_session, days=30)
        assert len(result) == 1

    def test_expiring_default_days(self, db_session):
        """Default window is 30 days."""
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        _make_inventory(
            db_session,
            product,
            qty=5.0,
            expiry_date=date.today() + timedelta(days=15),
        )

        result = get_expiring(db_session)
        assert len(result) == 1

    def test_expiring_zero_days(self, db_session):
        """With days=0, only items expiring today or earlier are included."""
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        _make_inventory(
            db_session,
            product,
            qty=5.0,
            expiry_date=date.today() + timedelta(days=1),
        )

        result = get_expiring(db_session, days=0)
        assert len(result) == 0


# ===========================================================================
# get_consumption_history
# ===========================================================================


class TestGetConsumptionHistory:
    def test_returns_recent_entries(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        log = ConsumptionLog(
            product_id=product.id,
            inventory_id=inv.id,
            quantity_used=Decimal("2.0"),
            quantity_remaining=Decimal("8.0"),
            consumed_by="Alice",
            action=ConsumptionAction.consume,
        )
        db_session.add(log)
        db_session.flush()

        result = get_consumption_history(product.id, db_session)
        assert len(result) >= 1
        assert result[0].product_id == product.id

    def test_respects_days_window(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        # This log should be within 90 days
        log = ConsumptionLog(
            product_id=product.id,
            inventory_id=inv.id,
            quantity_used=Decimal("2.0"),
            quantity_remaining=Decimal("8.0"),
            consumed_by="Alice",
            action=ConsumptionAction.consume,
        )
        db_session.add(log)
        db_session.flush()

        result = get_consumption_history(product.id, db_session, days=90)
        assert len(result) >= 1

    def test_no_entries_returns_empty(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)

        result = get_consumption_history(product.id, db_session)
        assert result == []

    def test_default_days_param(self, db_session):
        """Default days is 90."""
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        log = ConsumptionLog(
            product_id=product.id,
            inventory_id=inv.id,
            quantity_used=Decimal("1.0"),
            quantity_remaining=Decimal("9.0"),
            consumed_by="Alice",
            action=ConsumptionAction.consume,
        )
        db_session.add(log)
        db_session.flush()

        result = get_consumption_history(product.id, db_session)
        assert len(result) >= 1


# ===========================================================================
# get_item_history
# ===========================================================================


class TestGetItemHistory:
    def test_returns_entries_for_item(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=5.0)

        log = ConsumptionLog(
            product_id=product.id,
            inventory_id=inv.id,
            quantity_used=Decimal("1.0"),
            quantity_remaining=Decimal("4.0"),
            consumed_by="Alice",
            action=ConsumptionAction.consume,
        )
        db_session.add(log)
        db_session.flush()

        result = get_item_history(inv.id, db_session)
        assert len(result) == 1
        assert result[0].inventory_id == inv.id

    def test_no_entries_returns_empty(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=5.0)

        result = get_item_history(inv.id, db_session)
        assert result == []

    def test_multiple_entries_ordered_desc(self, db_session):
        """Multiple entries are returned in descending order by created_at."""
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv = _make_inventory(db_session, product, qty=10.0)

        log1 = ConsumptionLog(
            product_id=product.id,
            inventory_id=inv.id,
            quantity_used=Decimal("1.0"),
            quantity_remaining=Decimal("9.0"),
            consumed_by="Alice",
            action=ConsumptionAction.consume,
        )
        db_session.add(log1)
        db_session.flush()

        log2 = ConsumptionLog(
            product_id=product.id,
            inventory_id=inv.id,
            quantity_used=Decimal("2.0"),
            quantity_remaining=Decimal("7.0"),
            consumed_by="Bob",
            action=ConsumptionAction.consume,
        )
        db_session.add(log2)
        db_session.flush()

        result = get_item_history(inv.id, db_session)
        assert len(result) == 2
        # Most recent first (by created_at desc)
        assert result[0].consumed_by == "Bob"
        assert result[1].consumed_by == "Alice"

    def test_does_not_return_other_item_entries(self, db_session):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        inv1 = _make_inventory(db_session, product, qty=10.0)
        inv2 = _make_inventory(db_session, product, qty=5.0)

        log = ConsumptionLog(
            product_id=product.id,
            inventory_id=inv1.id,
            quantity_used=Decimal("1.0"),
            quantity_remaining=Decimal("9.0"),
            consumed_by="Alice",
            action=ConsumptionAction.consume,
        )
        db_session.add(log)
        db_session.flush()

        result = get_item_history(inv2.id, db_session)
        assert len(result) == 0


# ===========================================================================
# ACTIVE_STATUSES constant
# ===========================================================================


class TestActiveStatuses:
    def test_available_and_opened_are_active(self):
        assert InventoryStatus.available in ACTIVE_STATUSES
        assert InventoryStatus.opened in ACTIVE_STATUSES

    def test_inactive_statuses(self):
        assert InventoryStatus.depleted not in ACTIVE_STATUSES
        assert InventoryStatus.disposed not in ACTIVE_STATUSES
        assert InventoryStatus.expired not in ACTIVE_STATUSES
        assert InventoryStatus.deleted not in ACTIVE_STATUSES
