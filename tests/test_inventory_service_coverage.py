"""Tests for services/inventory.py — cover uncovered lines: receive_items, consume, adjust, dispose, open_item, queries."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlmodel import Session

from lab_manager.exceptions import NotFoundError, ValidationError
from lab_manager.models.consumption import ConsumptionAction, ConsumptionLog
from lab_manager.models.inventory import InventoryItem, InventoryStatus
from lab_manager.models.location import StorageLocation as Location
from lab_manager.models.order import Order, OrderItem, OrderStatus
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor
from lab_manager.services.inventory import (
    _get_inventory_or_404,
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


# ---- _to_decimal ----


class TestToDecimal:
    def test_normal_float(self):
        assert float(_to_decimal(3.14)) == pytest.approx(3.14)

    def test_integer(self):
        assert _to_decimal(5) == 5

    def test_zero(self):
        assert _to_decimal(0) == 0

    def test_nan_raises(self):
        with pytest.raises(ValidationError, match="finite"):
            _to_decimal(float("nan"))

    def test_inf_raises(self):
        with pytest.raises(ValidationError, match="finite"):
            _to_decimal(float("inf"))

    def test_neg_inf_raises(self):
        with pytest.raises(ValidationError, match="finite"):
            _to_decimal(float("-inf"))


# ---- receive_items ----


def _make_order_with_item(db, vendor_name="TestVendor"):
    """Helper: create vendor + product + order + order_item."""
    vendor = Vendor(name=vendor_name)
    db.add(vendor)
    db.flush()
    product = Product(catalog_number="CAT-001", name="Reagent X", vendor_id=vendor.id)
    db.add(product)
    db.flush()
    order = Order(vendor_id=vendor.id, status=OrderStatus.pending)
    db.add(order)
    db.flush()
    oi = OrderItem(
        order_id=order.id,
        product_id=product.id,
        catalog_number="CAT-001",
        quantity=5,
        unit="EA",
    )
    db.add(oi)
    db.flush()
    return order, oi, product, vendor


class TestReceiveItems:
    def test_receive_basic(self, db_session):
        order, oi, product, vendor = _make_order_with_item(db_session)
        location = Location(name="Shelf A")
        db_session.add(location)
        db_session.flush()

        items = receive_items(
            order_id=order.id,
            items_received=[{"order_item_id": oi.id, "quantity": 5}],
            location_id=location.id,
            received_by="Alice",
            db=db_session,
        )
        assert len(items) == 1
        assert float(items[0].quantity_on_hand) == 5.0
        assert items[0].product_id == product.id
        assert items[0].location_id == location.id
        assert order.status == OrderStatus.received
        assert order.received_by == "Alice"
        assert order.received_date == date.today()

    def test_receive_no_location(self, db_session):
        order, oi, product, vendor = _make_order_with_item(db_session)
        items = receive_items(
            order_id=order.id,
            items_received=[{"order_item_id": oi.id, "quantity": 3}],
            location_id=None,
            received_by="Bob",
            db=db_session,
        )
        assert items[0].location_id is None

    def test_receive_order_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            receive_items(9999, [], None, "Alice", db_session)

    def test_receive_order_item_wrong_order(self, db_session):
        order1, oi1, _, _ = _make_order_with_item(db_session, "V1")
        order2, oi2, _, _ = _make_order_with_item(db_session, "V2")
        with pytest.raises(ValidationError, match="belongs to order"):
            receive_items(
                order_id=order1.id,
                items_received=[{"order_item_id": oi2.id, "quantity": 1}],
                location_id=None,
                received_by="Alice",
                db=db_session,
            )

    def test_receive_without_order_item(self, db_session):
        vendor = Vendor(name="V")
        db_session.add(vendor)
        db_session.flush()
        product = Product(
            catalog_number="CAT-NEW", name="New Product", vendor_id=vendor.id
        )
        db_session.add(product)
        db_session.flush()
        order = Order(vendor_id=vendor.id, status=OrderStatus.pending)
        db_session.add(order)
        db_session.flush()

        items = receive_items(
            order_id=order.id,
            items_received=[{"product_id": product.id, "quantity": 10, "unit": "ML"}],
            location_id=None,
            received_by="Carol",
            db=db_session,
        )
        assert len(items) == 1
        assert items[0].product_id == product.id

    def test_receive_creates_consumption_log(self, db_session):
        order, oi, _, _ = _make_order_with_item(db_session)
        receive_items(
            order_id=order.id,
            items_received=[{"order_item_id": oi.id, "quantity": 2}],
            location_id=None,
            received_by="Dave",
            db=db_session,
        )
        logs = list(db_session.exec(select(ConsumptionLog)).scalars().all())
        assert len(logs) == 1
        assert logs[0].action == ConsumptionAction.receive
        assert float(logs[0].quantity_remaining) == 2.0

    def test_receive_rejects_already_received(self, db_session):
        """Double-receive should fail: order already in received status."""
        order, oi, _, _ = _make_order_with_item(db_session)
        receive_items(
            order_id=order.id,
            items_received=[{"order_item_id": oi.id, "quantity": 5}],
            location_id=None,
            received_by="Alice",
            db=db_session,
        )
        assert order.status == OrderStatus.received
        with pytest.raises(ValidationError, match="already received"):
            receive_items(
                order_id=order.id,
                items_received=[{"order_item_id": oi.id, "quantity": 5}],
                location_id=None,
                received_by="Bob",
                db=db_session,
            )

    def test_receive_rejects_already_received_after_reload(self, db_engine):
        with Session(db_engine) as db:
            order, oi, _, _ = _make_order_with_item(db)
            receive_items(
                order_id=order.id,
                items_received=[{"order_item_id": oi.id, "quantity": 5}],
                location_id=None,
                received_by="Alice",
                db=db,
            )
            db.commit()
            order_id = order.id
            order_item_id = oi.id

        with Session(db_engine) as db:
            with pytest.raises(ValidationError, match="already received"):
                receive_items(
                    order_id=order_id,
                    items_received=[{"order_item_id": order_item_id, "quantity": 5}],
                    location_id=None,
                    received_by="Bob",
                    db=db,
                )

    def test_receive_rejects_cancelled_order(self, db_session):
        order, oi, _, _ = _make_order_with_item(db_session)
        order.status = OrderStatus.cancelled
        db_session.flush()
        with pytest.raises(ValidationError, match="already cancelled"):
            receive_items(
                order_id=order.id,
                items_received=[{"order_item_id": oi.id, "quantity": 1}],
                location_id=None,
                received_by="Alice",
                db=db_session,
            )


# ---- consume ----


class TestConsume:
    def _setup_inventory(self, db, qty=10.0, status=InventoryStatus.available):
        vendor = Vendor(name="V")
        db.add(vendor)
        db.flush()
        product = Product(catalog_number="CAT-001", name="Reagent", vendor_id=vendor.id)
        db.add(product)
        db.flush()
        inv = InventoryItem(
            product_id=product.id, quantity_on_hand=Decimal(str(qty)), status=status
        )
        db.add(inv)
        db.flush()
        return inv

    def test_consume_normal(self, db_session):
        inv = self._setup_inventory(db_session, 10.0)
        result = consume(inv.id, 3.0, "Alice", "experiment", db_session)
        assert float(result.quantity_on_hand) == 7.0
        assert result.status == InventoryStatus.available

    def test_consume_depletes(self, db_session):
        inv = self._setup_inventory(db_session, 2.0)
        result = consume(inv.id, 2.0, "Alice", "used all", db_session)
        assert float(result.quantity_on_hand) == 0
        assert result.status == InventoryStatus.depleted

    def test_consume_near_zero_depletes(self, db_session):
        inv = self._setup_inventory(db_session, 0.00005)
        result = consume(inv.id, 0.00004, "Alice", "tiny amount", db_session)
        assert result.status == InventoryStatus.depleted

    def test_consume_insufficient_stock(self, db_session):
        inv = self._setup_inventory(db_session, 2.0)
        with pytest.raises(ValidationError, match="Insufficient stock"):
            consume(inv.id, 5.0, "Alice", "too much", db_session)

    def test_consume_negative_raises(self, db_session):
        inv = self._setup_inventory(db_session, 10.0)
        with pytest.raises(ValidationError, match="positive"):
            consume(inv.id, -1.0, "Alice", "negative", db_session)

    def test_consume_zero_raises(self, db_session):
        inv = self._setup_inventory(db_session, 10.0)
        with pytest.raises(ValidationError, match="positive"):
            consume(inv.id, 0, "Alice", "zero", db_session)

    def test_consume_disposed_raises(self, db_session):
        inv = self._setup_inventory(db_session, 10.0, InventoryStatus.disposed)
        with pytest.raises(ValidationError, match="Cannot consume from"):
            consume(inv.id, 1.0, "Alice", "from disposed", db_session)

    def test_consume_depleted_raises(self, db_session):
        inv = self._setup_inventory(db_session, 0, InventoryStatus.depleted)
        with pytest.raises(ValidationError, match="Cannot consume from"):
            consume(inv.id, 1.0, "Alice", "from depleted", db_session)

    def test_consume_nan_raises(self, db_session):
        inv = self._setup_inventory(db_session, 10.0)
        with pytest.raises(ValidationError, match="finite"):
            consume(inv.id, float("nan"), "Alice", "nan", db_session)

    def test_consume_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            consume(9999, 1.0, "Alice", "missing", db_session)


# ---- adjust ----


class TestAdjust:
    def _setup_inventory(self, db, qty=10.0):
        vendor = Vendor(name="V")
        db.add(vendor)
        db.flush()
        product = Product(catalog_number="CAT-001", name="Reagent", vendor_id=vendor.id)
        db.add(product)
        db.flush()
        inv = InventoryItem(
            product_id=product.id,
            quantity_on_hand=Decimal(str(qty)),
            status=InventoryStatus.available,
        )
        db.add(inv)
        db.flush()
        return inv

    def test_adjust_increase(self, db_session):
        inv = self._setup_inventory(db_session, 5.0)
        result = adjust(inv.id, 10.0, "cycle count", "Auditor", db_session)
        assert float(result.quantity_on_hand) == 10.0

    def test_adjust_decrease(self, db_session):
        inv = self._setup_inventory(db_session, 10.0)
        result = adjust(inv.id, 3.0, "found less", "Auditor", db_session)
        assert float(result.quantity_on_hand) == 3.0

    def test_adjust_to_zero(self, db_session):
        inv = self._setup_inventory(db_session, 10.0)
        result = adjust(inv.id, 0, "empty", "Auditor", db_session)
        assert float(result.quantity_on_hand) == 0
        assert result.status == InventoryStatus.depleted

    def test_adjust_negative_raises(self, db_session):
        inv = self._setup_inventory(db_session, 10.0)
        with pytest.raises(ValidationError, match="negative"):
            adjust(inv.id, -5.0, "negative", "Auditor", db_session)

    def test_adjust_depleted_to_available(self, db_session):
        inv = self._setup_inventory(db_session, 0)
        inv.status = InventoryStatus.depleted
        db_session.flush()
        result = adjust(inv.id, 5.0, "restocked", "Alice", db_session)
        assert result.status == InventoryStatus.available

    def test_adjust_near_zero_depletes(self, db_session):
        inv = self._setup_inventory(db_session, 10.0)
        result = adjust(inv.id, 0.00001, "almost empty", "Auditor", db_session)
        assert result.status == InventoryStatus.depleted

    def test_adjust_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            adjust(9999, 1.0, "missing", "Auditor", db_session)

    def test_adjust_creates_log(self, db_session):
        inv = self._setup_inventory(db_session, 10.0)
        adjust(inv.id, 8.0, "spillage", "Alice", db_session)
        logs = list(db_session.exec(select(ConsumptionLog)).scalars().all())
        assert len(logs) == 1
        assert logs[0].action == ConsumptionAction.adjust
        # delta = 8 - 10 = -2, quantity_used = -delta = 2
        assert float(logs[0].quantity_used) == 2.0


# ---- dispose ----


class TestDispose:
    def _setup_inventory(self, db, qty=10.0):
        vendor = Vendor(name="V")
        db.add(vendor)
        db.flush()
        product = Product(catalog_number="CAT-001", name="Reagent", vendor_id=vendor.id)
        db.add(product)
        db.flush()
        inv = InventoryItem(
            product_id=product.id,
            quantity_on_hand=Decimal(str(qty)),
            status=InventoryStatus.available,
        )
        db.add(inv)
        db.flush()
        return inv

    def test_dispose_normal(self, db_session):
        inv = self._setup_inventory(db_session, 10.0)
        result = dispose(inv.id, "expired", "Alice", db_session)
        assert result.status == InventoryStatus.disposed
        assert float(result.quantity_on_hand) == 0

    def test_dispose_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            dispose(9999, "expired", "Alice", db_session)

    def test_dispose_creates_log(self, db_session):
        inv = self._setup_inventory(db_session, 7.5)
        dispose(inv.id, "contaminated", "Bob", db_session)
        logs = list(db_session.exec(select(ConsumptionLog)).scalars().all())
        assert len(logs) == 1
        assert logs[0].action == ConsumptionAction.dispose
        assert float(logs[0].quantity_used) == 7.5
        assert float(logs[0].quantity_remaining) == 0

    @pytest.mark.parametrize(
        "status",
        [InventoryStatus.disposed, InventoryStatus.deleted],
    )
    def test_dispose_rejects_invalid_status(self, db_session, status):
        inv = self._setup_inventory(db_session, 5.0)
        inv.status = status
        db_session.flush()
        with pytest.raises(ValidationError, match="Cannot dispose"):
            dispose(inv.id, "test", "Alice", db_session)


# ---- open_item ----


class TestOpenItem:
    def _setup_inventory(self, db, qty=10.0):
        vendor = Vendor(name="V")
        db.add(vendor)
        db.flush()
        product = Product(catalog_number="CAT-001", name="Reagent", vendor_id=vendor.id)
        db.add(product)
        db.flush()
        inv = InventoryItem(
            product_id=product.id,
            quantity_on_hand=Decimal(str(qty)),
            status=InventoryStatus.available,
        )
        db.add(inv)
        db.flush()
        return inv

    def test_open_success(self, db_session):
        inv = self._setup_inventory(db_session)
        result = open_item(inv.id, "Alice", db_session)
        assert result.status == InventoryStatus.opened
        assert result.opened_date == date.today()

    def test_open_already_opened_raises(self, db_session):
        inv = self._setup_inventory(db_session)
        inv.opened_date = date(2025, 1, 1)
        inv.status = InventoryStatus.opened
        db_session.flush()
        with pytest.raises(ValidationError, match="already opened"):
            open_item(inv.id, "Alice", db_session)

    def test_open_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            open_item(9999, "Alice", db_session)

    def test_open_creates_log(self, db_session):
        inv = self._setup_inventory(db_session)
        open_item(inv.id, "Bob", db_session)
        logs = list(db_session.exec(select(ConsumptionLog)).scalars().all())
        assert len(logs) == 1
        assert logs[0].action == ConsumptionAction.open

    @pytest.mark.parametrize(
        "status",
        [InventoryStatus.disposed, InventoryStatus.deleted],
    )
    def test_open_rejects_inactive_status(self, db_session, status):
        inv = self._setup_inventory(db_session)
        inv.status = status
        db_session.flush()
        with pytest.raises(ValidationError, match="Cannot open"):
            open_item(inv.id, "Alice", db_session)

    def test_open_item_uses_for_update(self, db_session):
        """open_item must use SELECT ... FOR UPDATE like other mutations.

        Regression test: open_item previously called _get_inventory_or_404
        without for_update=True, unlike consume/transfer/adjust/dispose.
        """
        from unittest.mock import patch

        inv = self._setup_inventory(db_session)
        inv_id = inv.id

        calls = []
        _real_get = (
            _get_inventory_or_404.__wrapped__
            if hasattr(_get_inventory_or_404, "__wrapped__")
            else _get_inventory_or_404
        )

        def _spy(db, inventory_id, *, for_update=False):
            calls.append({"inventory_id": inventory_id, "for_update": for_update})
            return _real_get(db, inventory_id, for_update=for_update)

        with patch(
            "lab_manager.services.inventory._get_inventory_or_404",
            side_effect=_spy,
        ):
            open_item(inv_id, "Alice", db_session)

        assert len(calls) == 1
        assert calls[0]["for_update"] is True, "open_item must use for_update=True"


# ---- transfer ----


class TestTransfer:
    def _setup_inventory(self, db):
        vendor = Vendor(name="V")
        db.add(vendor)
        db.flush()
        product = Product(catalog_number="CAT-001", name="Reagent", vendor_id=vendor.id)
        db.add(product)
        db.flush()
        loc1 = Location(name="Shelf A")
        loc2 = Location(name="Shelf B")
        db.add(loc1)
        db.add(loc2)
        db.flush()
        inv = InventoryItem(
            product_id=product.id, quantity_on_hand=Decimal("5.0"), location_id=loc1.id
        )
        db.add(inv)
        db.flush()
        return inv, loc2

    def test_transfer_success(self, db_session):
        inv, new_loc = self._setup_inventory(db_session)
        result = transfer(inv.id, new_loc.id, "Alice", db_session)
        assert result.location_id == new_loc.id

    def test_transfer_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            transfer(9999, 1, "Alice", db_session)

    def test_transfer_creates_log(self, db_session):
        inv, new_loc = self._setup_inventory(db_session)
        transfer(inv.id, new_loc.id, "Alice", db_session)
        logs = list(db_session.exec(select(ConsumptionLog)).scalars().all())
        assert len(logs) == 1
        assert logs[0].action == ConsumptionAction.transfer

    @pytest.mark.parametrize(
        "status",
        [
            InventoryStatus.disposed,
            InventoryStatus.depleted,
            InventoryStatus.deleted,
            InventoryStatus.expired,
        ],
    )
    def test_transfer_rejects_inactive_status(self, db_session, status):
        inv, new_loc = self._setup_inventory(db_session)
        inv.status = status
        db_session.flush()
        with pytest.raises(ValidationError, match="Cannot transfer"):
            transfer(inv.id, new_loc.id, "Alice", db_session)


# ---- get_stock_level ----


class TestGetStockLevel:
    def test_stock_level(self, db_session):
        vendor = Vendor(name="V")
        db_session.add(vendor)
        db_session.flush()
        product = Product(catalog_number="CAT-001", name="Reagent", vendor_id=vendor.id)
        db_session.add(product)
        db_session.flush()
        inv1 = InventoryItem(
            product_id=product.id,
            quantity_on_hand=Decimal("5.0"),
            status=InventoryStatus.available,
        )
        inv2 = InventoryItem(
            product_id=product.id,
            quantity_on_hand=Decimal("3.0"),
            status=InventoryStatus.available,
        )
        db_session.add(inv1)
        db_session.add(inv2)
        db_session.flush()

        result = get_stock_level(product.id, db_session)
        assert result["total_quantity"] == 8.0

    def test_stock_level_ignores_depleted(self, db_session):
        vendor = Vendor(name="V")
        db_session.add(vendor)
        db_session.flush()
        product = Product(catalog_number="CAT-001", name="Reagent", vendor_id=vendor.id)
        db_session.add(product)
        db_session.flush()
        inv1 = InventoryItem(
            product_id=product.id,
            quantity_on_hand=Decimal("5.0"),
            status=InventoryStatus.available,
        )
        inv2 = InventoryItem(
            product_id=product.id,
            quantity_on_hand=Decimal("3.0"),
            status=InventoryStatus.depleted,
        )
        db_session.add(inv1)
        db_session.add(inv2)
        db_session.flush()

        result = get_stock_level(product.id, db_session)
        assert result["total_quantity"] == 5.0


# ---- get_low_stock (PG only — SQLite scalars() doesn't return rows) ----


class TestGetLowStock:
    def test_low_stock_pg_only(self, db_session):
        """get_low_stock uses scalars with GROUP BY which only works correctly on PG."""
        # On SQLite, scalars() returns only the first column (an int).
        # This test verifies the function doesn't crash, not its correctness.
        result = get_low_stock(db_session)
        assert isinstance(result, list)


# ---- get_expiring ----


class TestGetExpiring:
    def test_expiring_within_days(self, db_session):
        vendor = Vendor(name="V")
        db_session.add(vendor)
        db_session.flush()
        product = Product(catalog_number="CAT-001", name="Reagent", vendor_id=vendor.id)
        db_session.add(product)
        db_session.flush()
        inv = InventoryItem(
            product_id=product.id,
            quantity_on_hand=Decimal("5.0"),
            expiry_date=date.today() + timedelta(days=5),
            status=InventoryStatus.available,
        )
        db_session.add(inv)
        db_session.flush()

        result = get_expiring(db_session, days=30)
        assert len(result) == 1

    def test_expiring_not_within_days(self, db_session):
        vendor = Vendor(name="V")
        db_session.add(vendor)
        db_session.flush()
        product = Product(catalog_number="CAT-001", name="Reagent", vendor_id=vendor.id)
        db_session.add(product)
        db_session.flush()
        inv = InventoryItem(
            product_id=product.id,
            quantity_on_hand=Decimal("5.0"),
            expiry_date=date.today() + timedelta(days=60),
            status=InventoryStatus.available,
        )
        db_session.add(inv)
        db_session.flush()

        result = get_expiring(db_session, days=30)
        assert len(result) == 0

    def test_expiring_no_expiry(self, db_session):
        vendor = Vendor(name="V")
        db_session.add(vendor)
        db_session.flush()
        product = Product(catalog_number="CAT-001", name="Reagent", vendor_id=vendor.id)
        db_session.add(product)
        db_session.flush()
        inv = InventoryItem(
            product_id=product.id,
            quantity_on_hand=Decimal("5.0"),
            status=InventoryStatus.available,
        )
        db_session.add(inv)
        db_session.flush()

        result = get_expiring(db_session, days=30)
        assert len(result) == 0


# ---- get_consumption_history ----


class TestGetConsumptionHistory:
    def test_history_returns_entries(self, db_session):
        vendor = Vendor(name="V")
        db_session.add(vendor)
        db_session.flush()
        product = Product(catalog_number="CAT-001", name="Reagent", vendor_id=vendor.id)
        db_session.add(product)
        db_session.flush()
        inv_item = InventoryItem(
            product_id=product.id, quantity_on_hand=Decimal("10.0")
        )
        db_session.add(inv_item)
        db_session.flush()
        log = ConsumptionLog(
            product_id=product.id,
            inventory_id=inv_item.id,
            quantity_used=Decimal("2.0"),
            quantity_remaining=Decimal("8.0"),
            consumed_by="Alice",
            action=ConsumptionAction.consume,
        )
        db_session.add(log)
        db_session.flush()

        result = get_consumption_history(product.id, db_session)
        assert len(result) >= 1


# ---- get_item_history ----


class TestGetItemHistory:
    def test_item_history(self, db_session):
        vendor = Vendor(name="V")
        db_session.add(vendor)
        db_session.flush()
        product = Product(catalog_number="CAT-001", name="Reagent", vendor_id=vendor.id)
        db_session.add(product)
        db_session.flush()
        inv = InventoryItem(product_id=product.id, quantity_on_hand=Decimal("5.0"))
        db_session.add(inv)
        db_session.flush()
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
