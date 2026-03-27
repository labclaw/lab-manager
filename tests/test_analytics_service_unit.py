"""Unit tests for analytics service — pure mock-based tests (no DB required)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock


from lab_manager.models.document import DocumentStatus
from lab_manager.services.analytics import (
    _money,
    dashboard_summary,
    document_processing_stats,
    inventory_report,
    inventory_value,
    order_history,
    spending_by_month,
    spending_by_vendor,
    staff_activity,
    top_products,
    vendor_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_execute_side_effect(responses: list):
    """Return a db mock whose .execute() returns items from *responses* in order.

    Each item in *responses* must itself be a mock with the appropriate
    ``.one()``, ``.all()``, or ``.scalar()`` method already configured.
    """
    db = MagicMock()
    db.execute.side_effect = responses
    return db


def _scalar_mock(val):
    """Return a mock result row where .scalar() returns *val*."""
    m = MagicMock()
    m.scalar.return_value = val
    return m


def _one_mock(**fields):
    """Return a mock result row where .one() returns a SimpleNamespace."""
    m = MagicMock()
    m.one.return_value = SimpleNamespace(**fields)
    return m


def _all_mock(rows: list):
    """Return a mock result row where .all() returns *rows*."""
    m = MagicMock()
    m.all.return_value = rows
    return m


# ---------------------------------------------------------------------------
# 1. _money
# ---------------------------------------------------------------------------


class TestMoney:
    """Tests for the _money helper function."""

    def test_none_returns_zero(self):
        assert _money(None) == 0.0

    def test_integer_to_float(self):
        assert _money(100) == 100.0

    def test_float_rounded_to_two_decimals(self):
        assert _money(3.14159) == 3.14

    def test_already_rounded(self):
        assert _money(3.14) == 3.14

    def test_negative_value(self):
        # Python banker's rounding: round(-5.555, 2) -> -5.55
        assert _money(-5.555) == -5.55

    def test_negative_integer(self):
        assert _money(-10) == -10.0

    def test_zero(self):
        assert _money(0) == 0.0

    def test_zero_float(self):
        assert _money(0.0) == 0.0

    def test_decimal_type(self):
        assert _money(Decimal("99.999")) == 100.0

    def test_large_number(self):
        assert _money(1234567.891) == 1234567.89

    def test_small_fraction(self):
        assert _money(0.001) == 0.0

    def test_rounding_half_up(self):
        # round(2.5, 2) stays 2.5; round(2.505, 2) is 2.5 (banker's)
        assert _money(2.505) == 2.5

    def test_boolean_true(self):
        # bool is a subclass of int in Python; True == 1
        assert _money(True) == 1.0

    def test_boolean_false(self):
        assert _money(False) == 0.0

    def test_string_number(self):
        # float("3.14") works
        assert _money("3.14") == 3.14

    def test_return_type_is_float(self):
        result = _money(5)
        assert isinstance(result, float)

    def test_nan_input(self):
        import math

        result = _money(float("nan"))
        assert math.isnan(result)


# ---------------------------------------------------------------------------
# 2. dashboard_summary
# ---------------------------------------------------------------------------


class TestDashboardSummary:
    """Tests for dashboard_summary with a fully mocked db session."""

    def _make_counts_row(self, **overrides):
        defaults = dict(
            products=10,
            vendors=5,
            orders=20,
            inventory=30,
            documents=8,
            staff=4,
            docs_pending=3,
            docs_approved=5,
        )
        defaults.update(overrides)
        return _one_mock(**defaults)

    def _make_db(
        self,
        counts_row=None,
        orders_by_status=(),
        inv_by_status=(),
        recent_orders=(),
        expiring_rows=(),
        low_stock_scalar=0,
    ):
        counts = counts_row or self._make_counts_row()
        db = MagicMock()
        db.execute.side_effect = [
            counts,  # counts subquery
            _all_mock(list(orders_by_status)),  # orders_by_status
            _all_mock(list(inv_by_status)),  # inventory_by_status
            _all_mock(list(recent_orders)),  # recent_orders
            _all_mock(list(expiring_rows)),  # expiring_soon
            _scalar_mock(low_stock_scalar),  # low_stock_count
        ]
        return db

    def test_basic_counts_returned(self):
        db = self._make_db(
            counts_row=self._make_counts_row(
                products=10,
                vendors=5,
                orders=20,
                inventory=30,
                documents=8,
                staff=4,
                docs_pending=3,
                docs_approved=5,
            )
        )
        result = dashboard_summary(db)
        assert result["total_products"] == 10
        assert result["total_vendors"] == 5
        assert result["total_orders"] == 20
        assert result["total_inventory_items"] == 30
        assert result["total_documents"] == 8
        assert result["total_staff"] == 4
        assert result["documents_pending_review"] == 3
        assert result["documents_approved"] == 5

    def test_none_counts_treated_as_zero(self):
        db = self._make_db(
            counts_row=self._make_counts_row(
                products=None,
                vendors=None,
                orders=None,
                inventory=None,
                documents=None,
                staff=None,
                docs_pending=None,
                docs_approved=None,
            )
        )
        result = dashboard_summary(db)
        assert result["total_products"] == 0
        assert result["total_vendors"] == 0
        assert result["total_orders"] == 0
        assert result["total_inventory_items"] == 0
        assert result["total_documents"] == 0
        assert result["total_staff"] == 0
        assert result["documents_pending_review"] == 0
        assert result["documents_approved"] == 0

    def test_orders_by_status(self):
        orders_by_status = [("received", 15), ("pending", 5)]
        db = self._make_db(orders_by_status=orders_by_status)
        result = dashboard_summary(db)
        assert result["orders_by_status"] == {"received": 15, "pending": 5}

    def test_inventory_by_status(self):
        inv_status = [("available", 25), ("disposed", 5)]
        db = self._make_db(inv_by_status=inv_status)
        result = dashboard_summary(db)
        assert result["inventory_by_status"] == {"available": 25, "disposed": 5}

    def test_recent_orders_parsed(self):
        order = MagicMock()
        order.id = 42
        order.po_number = "PO-042"
        order.status = "received"
        order.order_date = date(2025, 3, 1)
        recent = [(order, "Acme Corp")]
        db = self._make_db(recent_orders=recent)
        result = dashboard_summary(db)
        assert len(result["recent_orders"]) == 1
        ro = result["recent_orders"][0]
        assert ro["id"] == 42
        assert ro["po_number"] == "PO-042"
        assert ro["vendor_name"] == "Acme Corp"
        assert ro["status"] == "received"
        assert ro["order_date"] == "2025-03-01"

    def test_recent_orders_empty(self):
        db = self._make_db()
        result = dashboard_summary(db)
        assert result["recent_orders"] == []

    def test_expiring_soon_parsed(self):
        item = MagicMock()
        item.id = 7
        item.lot_number = "LOT-007"
        item.quantity_on_hand = 3
        item.expiry_date = date(2025, 4, 15)
        expiring = [(item, "Reagent X")]
        db = self._make_db(expiring_rows=expiring)
        result = dashboard_summary(db)
        assert len(result["expiring_soon"]) == 1
        es = result["expiring_soon"][0]
        assert es["id"] == 7
        assert es["product_name"] == "Reagent X"
        assert es["lot_number"] == "LOT-007"
        assert es["quantity_on_hand"] == 3
        assert es["expiry_date"] == "2025-04-15"

    def test_expiring_soon_empty(self):
        db = self._make_db()
        result = dashboard_summary(db)
        assert result["expiring_soon"] == []

    def test_low_stock_count(self):
        db = self._make_db(low_stock_scalar=5)
        result = dashboard_summary(db)
        assert result["low_stock_count"] == 5

    def test_low_stock_count_none_treated_as_zero(self):
        db = self._make_db(low_stock_scalar=None)
        result = dashboard_summary(db)
        assert result["low_stock_count"] == 0

    def test_all_keys_present(self):
        db = self._make_db()
        result = dashboard_summary(db)
        expected_keys = {
            "total_products",
            "total_vendors",
            "total_orders",
            "total_inventory_items",
            "total_documents",
            "total_staff",
            "documents_pending_review",
            "documents_approved",
            "orders_by_status",
            "inventory_by_status",
            "recent_orders",
            "expiring_soon",
            "low_stock_count",
        }
        assert set(result.keys()) == expected_keys

    def test_execute_called_six_times(self):
        db = self._make_db()
        dashboard_summary(db)
        assert db.execute.call_count == 6


# ---------------------------------------------------------------------------
# 3. spending_by_vendor
# ---------------------------------------------------------------------------


class TestSpendingByVendor:
    """Tests for spending_by_vendor."""

    def _make_db(self, rows=None):
        rows = rows or []
        db = MagicMock()
        db.execute.return_value = _all_mock(rows)
        return db

    def test_empty_db(self):
        db = self._make_db()
        result = spending_by_vendor(db)
        assert result == []

    def test_single_vendor(self):
        row = SimpleNamespace(
            vendor_name="Sigma",
            order_count=2,
            item_count=5,
            total_spend=Decimal("150.50"),
        )
        db = self._make_db([row])
        result = spending_by_vendor(db)
        assert len(result) == 1
        assert result[0]["vendor_name"] == "Sigma"
        assert result[0]["order_count"] == 2
        assert result[0]["item_count"] == 5
        assert result[0]["total_spend"] == 150.50

    def test_multiple_vendors(self):
        r1 = SimpleNamespace(
            vendor_name="V1", order_count=1, item_count=2, total_spend=100
        )
        r2 = SimpleNamespace(
            vendor_name="V2", order_count=3, item_count=6, total_spend=200
        )
        db = self._make_db([r1, r2])
        result = spending_by_vendor(db)
        assert len(result) == 2
        assert result[0]["vendor_name"] == "V1"
        assert result[1]["vendor_name"] == "V2"

    def test_none_total_spend_becomes_zero(self):
        row = SimpleNamespace(
            vendor_name="V", order_count=0, item_count=0, total_spend=None
        )
        db = self._make_db([row])
        result = spending_by_vendor(db)
        assert result[0]["total_spend"] == 0.0

    def test_with_date_from(self):
        db = self._make_db()
        result = spending_by_vendor(db, date_from=date(2025, 1, 1))
        assert result == []
        # Verify that execute was called (date filter was applied to query)
        assert db.execute.call_count == 1

    def test_with_date_to(self):
        db = self._make_db()
        result = spending_by_vendor(db, date_to=date(2025, 12, 31))
        assert result == []

    def test_with_both_date_filters(self):
        db = self._make_db()
        result = spending_by_vendor(
            db, date_from=date(2025, 1, 1), date_to=date(2025, 12, 31)
        )
        assert result == []

    def test_order_count_is_int(self):
        row = SimpleNamespace(
            vendor_name="V", order_count=5, item_count=10, total_spend=50
        )
        db = self._make_db([row])
        result = spending_by_vendor(db)
        assert isinstance(result[0]["order_count"], int)
        assert isinstance(result[0]["item_count"], int)

    def test_total_spend_is_float(self):
        row = SimpleNamespace(
            vendor_name="V", order_count=1, item_count=1, total_spend=99.999
        )
        db = self._make_db([row])
        result = spending_by_vendor(db)
        assert isinstance(result[0]["total_spend"], float)


# ---------------------------------------------------------------------------
# 4. spending_by_month
# ---------------------------------------------------------------------------


class TestSpendingByMonth:
    """Tests for spending_by_month."""

    def _make_db(self, rows=None):
        rows = rows or []
        db = MagicMock()
        db.execute.return_value = _all_mock(rows)
        return db

    def test_empty_db(self):
        db = self._make_db()
        result = spending_by_month(db)
        assert result == []

    def test_single_month(self):
        row = SimpleNamespace(
            yr=2025, mo=3, order_count=5, total_spend=Decimal("1234.56")
        )
        db = self._make_db([row])
        result = spending_by_month(db)
        assert len(result) == 1
        assert result[0]["month"] == "2025-03"
        assert result[0]["order_count"] == 5
        assert result[0]["total_spend"] == 1234.56

    def test_multiple_months(self):
        r1 = SimpleNamespace(yr=2025, mo=1, order_count=3, total_spend=100)
        r2 = SimpleNamespace(yr=2025, mo=2, order_count=7, total_spend=200)
        r3 = SimpleNamespace(yr=2025, mo=3, order_count=1, total_spend=50)
        db = self._make_db([r1, r2, r3])
        result = spending_by_month(db)
        assert len(result) == 3
        assert result[0]["month"] == "2025-01"
        assert result[2]["month"] == "2025-03"

    def test_default_months_is_12(self):
        db = self._make_db()
        spending_by_month(db)
        # Just verify it runs with default param without error
        assert db.execute.call_count == 1

    def test_custom_months_param(self):
        db = self._make_db()
        spending_by_month(db, months=6)
        assert db.execute.call_count == 1

    def test_month_formatting_single_digit(self):
        row = SimpleNamespace(yr=2025, mo=1, order_count=1, total_spend=10)
        db = self._make_db([row])
        result = spending_by_month(db)
        assert result[0]["month"] == "2025-01"

    def test_month_formatting_double_digit(self):
        row = SimpleNamespace(yr=2025, mo=11, order_count=1, total_spend=10)
        db = self._make_db([row])
        result = spending_by_month(db)
        assert result[0]["month"] == "2025-11"

    def test_order_count_is_int(self):
        row = SimpleNamespace(yr=2025, mo=1, order_count=10, total_spend=100)
        db = self._make_db([row])
        result = spending_by_month(db)
        assert isinstance(result[0]["order_count"], int)

    def test_total_spend_rounded(self):
        row = SimpleNamespace(yr=2025, mo=6, order_count=1, total_spend=99.999)
        db = self._make_db([row])
        result = spending_by_month(db)
        assert result[0]["total_spend"] == 100.0


# ---------------------------------------------------------------------------
# 5. inventory_value
# ---------------------------------------------------------------------------


class TestInventoryValue:
    """Tests for inventory_value."""

    def _make_db(self, total_value=0, item_count=0):
        db = MagicMock()
        db.execute.side_effect = [
            _scalar_mock(total_value),  # total value query
            _scalar_mock(item_count),  # item count query
        ]
        return db

    def test_empty_db(self):
        db = self._make_db(total_value=0, item_count=0)
        result = inventory_value(db)
        assert result["total_value"] == 0.0
        assert result["item_count"] == 0

    def test_with_items(self):
        db = self._make_db(total_value=Decimal("500.75"), item_count=10)
        result = inventory_value(db)
        assert result["total_value"] == 500.75
        assert result["item_count"] == 10

    def test_none_total_value(self):
        db = self._make_db(total_value=None, item_count=5)
        result = inventory_value(db)
        assert result["total_value"] == 0.0

    def test_none_item_count(self):
        db = self._make_db(total_value=100, item_count=None)
        result = inventory_value(db)
        assert result["item_count"] == 0

    def test_both_none(self):
        db = self._make_db(total_value=None, item_count=None)
        result = inventory_value(db)
        assert result["total_value"] == 0.0
        assert result["item_count"] == 0

    def test_total_value_is_float(self):
        db = self._make_db(total_value=123, item_count=1)
        result = inventory_value(db)
        assert isinstance(result["total_value"], float)

    def test_large_value(self):
        db = self._make_db(total_value=Decimal("999999.99"), item_count=1000)
        result = inventory_value(db)
        assert result["total_value"] == 999999.99
        assert result["item_count"] == 1000

    def test_return_structure(self):
        db = self._make_db()
        result = inventory_value(db)
        assert set(result.keys()) == {"total_value", "item_count"}


# ---------------------------------------------------------------------------
# 6. top_products
# ---------------------------------------------------------------------------


class TestTopProducts:
    """Tests for top_products."""

    def _make_db(self, rows=None):
        rows = rows or []
        db = MagicMock()
        db.execute.return_value = _all_mock(rows)
        return db

    def test_empty_db(self):
        db = self._make_db()
        result = top_products(db)
        assert result == []

    def test_single_product(self):
        row = SimpleNamespace(
            catalog_number="CAT-001",
            description="Reagent A",
            vendor="Sigma",
            times_ordered=5,
            total_quantity=100,
        )
        db = self._make_db([row])
        result = top_products(db)
        assert len(result) == 1
        assert result[0]["catalog_number"] == "CAT-001"
        assert result[0]["name"] == "Reagent A"
        assert result[0]["vendor"] == "Sigma"
        assert result[0]["times_ordered"] == 5
        assert result[0]["total_quantity"] == 100.0

    def test_multiple_products(self):
        r1 = SimpleNamespace(
            catalog_number="C-A",
            description="Product A",
            vendor="V1",
            times_ordered=10,
            total_quantity=200,
        )
        r2 = SimpleNamespace(
            catalog_number="C-B",
            description="Product B",
            vendor="V2",
            times_ordered=5,
            total_quantity=50,
        )
        db = self._make_db([r1, r2])
        result = top_products(db)
        assert len(result) == 2

    def test_default_limit(self):
        db = self._make_db()
        top_products(db)
        # Verify it executes without error
        assert db.execute.call_count == 1

    def test_custom_limit(self):
        db = self._make_db()
        top_products(db, limit=5)
        assert db.execute.call_count == 1

    def test_times_ordered_is_int(self):
        row = SimpleNamespace(
            catalog_number="C",
            description="D",
            vendor="V",
            times_ordered=7,
            total_quantity=3,
        )
        db = self._make_db([row])
        result = top_products(db)
        assert isinstance(result[0]["times_ordered"], int)

    def test_total_quantity_is_float(self):
        row = SimpleNamespace(
            catalog_number="C",
            description="D",
            vendor="V",
            times_ordered=1,
            total_quantity=42,
        )
        db = self._make_db([row])
        result = top_products(db)
        assert isinstance(result[0]["total_quantity"], float)

    def test_none_vendor(self):
        row = SimpleNamespace(
            catalog_number="C",
            description="D",
            vendor=None,
            times_ordered=1,
            total_quantity=10,
        )
        db = self._make_db([row])
        result = top_products(db)
        assert result[0]["vendor"] is None


# ---------------------------------------------------------------------------
# 7. order_history
# ---------------------------------------------------------------------------


class TestOrderHistory:
    """Tests for order_history."""

    def _make_db(self, rows=None):
        rows = rows or []
        db = MagicMock()
        db.execute.return_value = _all_mock(rows)
        return db

    def _make_order_tuple(
        self,
        order_id=1,
        po="PO-001",
        vendor_name="V",
        order_date_val=None,
        status="received",
        item_count=2,
        total_value=Decimal("100.00"),
    ):
        order = MagicMock()
        order.id = order_id
        order.po_number = po
        order.order_date = order_date_val
        order.status = status
        return (order, vendor_name, item_count, total_value)

    def test_empty_db(self):
        db = self._make_db()
        result = order_history(db)
        assert result == []

    def test_single_order(self):
        order_tuple = self._make_order_tuple(
            order_id=10,
            po="PO-010",
            vendor_name="Sigma",
            order_date_val=date(2025, 3, 15),
            status="received",
            item_count=3,
            total_value=Decimal("250.50"),
        )
        db = self._make_db([order_tuple])
        result = order_history(db)
        assert len(result) == 1
        assert result[0]["id"] == 10
        assert result[0]["po_number"] == "PO-010"
        assert result[0]["vendor_name"] == "Sigma"
        assert result[0]["order_date"] == "2025-03-15"
        assert result[0]["status"] == "received"
        assert result[0]["item_count"] == 3
        assert result[0]["total_value"] == 250.50

    def test_multiple_orders(self):
        t1 = self._make_order_tuple(order_id=1)
        t2 = self._make_order_tuple(order_id=2, po="PO-002")
        db = self._make_db([t1, t2])
        result = order_history(db)
        assert len(result) == 2

    def test_vendor_id_filter(self):
        db = self._make_db()
        order_history(db, vendor_id=5)
        assert db.execute.call_count == 1

    def test_date_from_filter(self):
        db = self._make_db()
        order_history(db, date_from=date(2025, 1, 1))
        assert db.execute.call_count == 1

    def test_date_to_filter(self):
        db = self._make_db()
        order_history(db, date_to=date(2025, 12, 31))
        assert db.execute.call_count == 1

    def test_both_date_filters(self):
        db = self._make_db()
        order_history(db, date_from=date(2025, 1, 1), date_to=date(2025, 12, 31))
        assert db.execute.call_count == 1

    def test_all_filters_combined(self):
        db = self._make_db()
        order_history(
            db,
            vendor_id=3,
            date_from=date(2025, 1, 1),
            date_to=date(2025, 12, 31),
            limit=100,
        )
        assert db.execute.call_count == 1

    def test_default_limit(self):
        db = self._make_db()
        order_history(db)
        assert db.execute.call_count == 1

    def test_custom_limit(self):
        db = self._make_db()
        order_history(db, limit=10)
        assert db.execute.call_count == 1

    def test_none_order_date(self):
        order_tuple = self._make_order_tuple(order_date_val=None)
        db = self._make_db([order_tuple])
        result = order_history(db)
        assert result[0]["order_date"] is None

    def test_none_total_value(self):
        order_tuple = self._make_order_tuple(total_value=None)
        db = self._make_db([order_tuple])
        result = order_history(db)
        assert result[0]["total_value"] == 0.0

    def test_item_count_is_int(self):
        order_tuple = self._make_order_tuple(item_count=7)
        db = self._make_db([order_tuple])
        result = order_history(db)
        assert isinstance(result[0]["item_count"], int)

    def test_total_value_is_float(self):
        order_tuple = self._make_order_tuple(total_value=Decimal("99.99"))
        db = self._make_db([order_tuple])
        result = order_history(db)
        assert isinstance(result[0]["total_value"], float)


# ---------------------------------------------------------------------------
# 8. staff_activity
# ---------------------------------------------------------------------------


class TestStaffActivity:
    """Tests for staff_activity."""

    def _make_db(self, rows=None):
        rows = rows or []
        db = MagicMock()
        db.execute.return_value = _all_mock(rows)
        return db

    def test_empty_db(self):
        db = self._make_db()
        result = staff_activity(db)
        assert result == []

    def test_single_staff_member(self):
        row = SimpleNamespace(
            received_by="Alice", orders_received=5, last_active=date(2025, 3, 1)
        )
        db = self._make_db([row])
        result = staff_activity(db)
        assert len(result) == 1
        assert result[0]["name"] == "Alice"
        assert result[0]["orders_received"] == 5
        assert result[0]["last_active"] == "2025-03-01"

    def test_multiple_staff(self):
        r1 = SimpleNamespace(
            received_by="Alice", orders_received=10, last_active=date(2025, 3, 15)
        )
        r2 = SimpleNamespace(
            received_by="Bob", orders_received=3, last_active=date(2025, 2, 1)
        )
        db = self._make_db([r1, r2])
        result = staff_activity(db)
        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[1]["name"] == "Bob"

    def test_orders_received_is_int(self):
        row = SimpleNamespace(
            received_by="X", orders_received=99, last_active=date(2025, 1, 1)
        )
        db = self._make_db([row])
        result = staff_activity(db)
        assert isinstance(result[0]["orders_received"], int)

    def test_last_active_with_datetime(self):
        dt = datetime(2025, 3, 15, 10, 30, 0)
        row = SimpleNamespace(received_by="Carol", orders_received=1, last_active=dt)
        db = self._make_db([row])
        result = staff_activity(db)
        assert result[0]["last_active"] == "2025-03-15T10:30:00"

    def test_last_active_none(self):
        row = SimpleNamespace(received_by="Dave", orders_received=1, last_active=None)
        db = self._make_db([row])
        result = staff_activity(db)
        assert result[0]["last_active"] is None


# ---------------------------------------------------------------------------
# 9. vendor_summary
# ---------------------------------------------------------------------------


class TestVendorSummary:
    """Tests for vendor_summary."""

    def _make_db(
        self,
        vendor=None,
        products_count=0,
        order_count=0,
        total_spend=Decimal("0"),
        last_order_date=None,
    ):
        db = MagicMock()
        db.get.return_value = vendor
        db.execute.side_effect = [
            _scalar_mock(products_count),  # products supplied
            _scalar_mock(order_count),  # order count
            _scalar_mock(total_spend),  # total spend
            _scalar_mock(last_order_date),  # last order date
        ]
        return db

    def _make_vendor(
        self, vid=1, name="TestVendor", website=None, phone=None, email=None
    ):
        v = MagicMock()
        v.id = vid
        v.name = name
        v.website = website
        v.phone = phone
        v.email = email
        return v

    def test_vendor_not_found(self):
        db = MagicMock()
        db.get.return_value = None
        result = vendor_summary(db, vendor_id=9999)
        assert result is None
        # No execute calls needed when vendor not found
        assert db.execute.call_count == 0

    def test_vendor_found_basic(self):
        vendor = self._make_vendor(
            vid=1,
            name="Sigma",
            website="https://sigma.com",
            phone="555-1234",
            email="info@sigma.com",
        )
        db = self._make_db(
            vendor=vendor,
            products_count=10,
            order_count=5,
            total_spend=Decimal("500.00"),
            last_order_date=date(2025, 3, 1),
        )
        result = vendor_summary(db, vendor_id=1)
        assert result is not None
        assert result["id"] == 1
        assert result["name"] == "Sigma"
        assert result["website"] == "https://sigma.com"
        assert result["phone"] == "555-1234"
        assert result["email"] == "info@sigma.com"
        assert result["products_supplied"] == 10
        assert result["order_count"] == 5
        assert result["total_spend"] == 500.00
        assert result["last_order_date"] == "2025-03-01"

    def test_zero_spend(self):
        vendor = self._make_vendor(name="EmptyVendor")
        db = self._make_db(vendor=vendor, total_spend=0, last_order_date=None)
        result = vendor_summary(db, vendor_id=1)
        assert result["total_spend"] == 0.0
        assert result["last_order_date"] is None

    def test_none_products_count(self):
        vendor = self._make_vendor()
        db = self._make_db(vendor=vendor, products_count=None, order_count=None)
        result = vendor_summary(db, vendor_id=1)
        assert result["products_supplied"] == 0
        assert result["order_count"] == 0

    def test_total_spend_is_float(self):
        vendor = self._make_vendor()
        db = self._make_db(vendor=vendor, total_spend=Decimal("123.45"))
        result = vendor_summary(db, vendor_id=1)
        assert isinstance(result["total_spend"], float)

    def test_execute_called_four_times(self):
        vendor = self._make_vendor()
        db = self._make_db(vendor=vendor)
        vendor_summary(db, vendor_id=1)
        assert db.execute.call_count == 4

    def test_vendor_with_no_contact_info(self):
        vendor = self._make_vendor(vid=2, name="NoInfo")
        db = self._make_db(vendor=vendor)
        result = vendor_summary(db, vendor_id=2)
        assert result["website"] is None
        assert result["phone"] is None
        assert result["email"] is None

    def test_last_order_date_with_datetime(self):
        vendor = self._make_vendor()
        dt = datetime(2025, 6, 15, 14, 30, 0)
        db = self._make_db(vendor=vendor, last_order_date=dt)
        result = vendor_summary(db, vendor_id=1)
        assert result["last_order_date"] == "2025-06-15T14:30:00"


# ---------------------------------------------------------------------------
# 10. inventory_report
# ---------------------------------------------------------------------------


class TestInventoryReport:
    """Tests for inventory_report."""

    def _make_db(self, rows=None):
        rows = rows or []
        db = MagicMock()
        db.execute.return_value = _all_mock(rows)
        return db

    def _make_item_tuple(
        self,
        item_id=1,
        product_name="Reagent",
        catalog_number="CAT-001",
        vendor_name="Sigma",
        location_name="Fridge A",
        lot_number="LOT-001",
        qty=10,
        unit="mL",
        expiry_date=None,
        status="available",
    ):
        item = MagicMock()
        item.id = item_id
        item.lot_number = lot_number
        item.quantity_on_hand = qty
        item.unit = unit
        item.expiry_date = expiry_date
        item.status = status
        return (item, product_name, catalog_number, vendor_name, location_name)

    def test_empty_db(self):
        db = self._make_db()
        result = inventory_report(db)
        assert result == []

    def test_single_item(self):
        row = self._make_item_tuple(
            item_id=1,
            product_name="Buffer",
            catalog_number="BUF-001",
            vendor_name="Sigma",
            location_name="Shelf B",
            lot_number="L-100",
            qty=500,
            unit="mL",
            expiry_date=date(2026, 1, 1),
            status="available",
        )
        db = self._make_db([row])
        result = inventory_report(db)
        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["product_name"] == "Buffer"
        assert result[0]["catalog_number"] == "BUF-001"
        assert result[0]["vendor_name"] == "Sigma"
        assert result[0]["location_name"] == "Shelf B"
        assert result[0]["lot_number"] == "L-100"
        assert result[0]["quantity_on_hand"] == 500
        assert result[0]["unit"] == "mL"
        assert result[0]["expiry_date"] == "2026-01-01"
        assert result[0]["status"] == "available"

    def test_multiple_items(self):
        r1 = self._make_item_tuple(item_id=1, product_name="P1")
        r2 = self._make_item_tuple(item_id=2, product_name="P2")
        db = self._make_db([r1, r2])
        result = inventory_report(db)
        assert len(result) == 2

    def test_with_location_id_filter(self):
        db = self._make_db()
        inventory_report(db, location_id=5)
        assert db.execute.call_count == 1

    def test_without_location_id_filter(self):
        db = self._make_db()
        inventory_report(db)
        assert db.execute.call_count == 1

    def test_none_joins(self):
        # product_name, catalog_number, vendor_name, location_name can all be None
        row = self._make_item_tuple(
            product_name=None,
            catalog_number=None,
            vendor_name=None,
            location_name=None,
        )
        db = self._make_db([row])
        result = inventory_report(db)
        assert result[0]["product_name"] is None
        assert result[0]["catalog_number"] is None
        assert result[0]["vendor_name"] is None
        assert result[0]["location_name"] is None

    def test_none_expiry_date(self):
        row = self._make_item_tuple(expiry_date=None)
        db = self._make_db([row])
        result = inventory_report(db)
        assert result[0]["expiry_date"] is None

    def test_all_fields_present(self):
        row = self._make_item_tuple()
        db = self._make_db([row])
        result = inventory_report(db)
        expected_keys = {
            "id",
            "product_name",
            "catalog_number",
            "vendor_name",
            "location_name",
            "lot_number",
            "quantity_on_hand",
            "unit",
            "expiry_date",
            "status",
        }
        assert set(result[0].keys()) == expected_keys


# ---------------------------------------------------------------------------
# 11. document_processing_stats
# ---------------------------------------------------------------------------


class TestDocumentProcessingStats:
    """Tests for document_processing_stats."""

    def _make_db(self, total=0, by_status=(), by_type=(), avg_confidence=None):
        db = MagicMock()
        db.execute.side_effect = [
            _scalar_mock(total),  # total count
            _all_mock(list(by_status)),  # by_status
            _all_mock(list(by_type)),  # by_type
            _scalar_mock(avg_confidence),  # avg confidence
        ]
        return db

    def test_empty_db(self):
        db = self._make_db()
        result = document_processing_stats(db)
        assert result["total_documents"] == 0
        assert result["by_status"] == {}
        assert result["by_type"] == {}
        assert result["average_confidence"] is None
        assert result["rejected_count"] == 0
        assert result["rejection_rate"] == 0.0

    def test_with_documents(self):
        by_status = [
            (DocumentStatus.approved, 10),
            (DocumentStatus.rejected, 2),
            (DocumentStatus.pending, 3),
        ]
        by_type = [("invoice", 8), ("packing_list", 7)]
        db = self._make_db(
            total=15, by_status=by_status, by_type=by_type, avg_confidence=0.92
        )
        result = document_processing_stats(db)
        assert result["total_documents"] == 15
        assert result["by_status"][DocumentStatus.approved] == 10
        assert result["by_status"][DocumentStatus.rejected] == 2
        assert result["by_type"]["invoice"] == 8
        assert result["by_type"]["packing_list"] == 7
        assert result["average_confidence"] == 0.92
        assert result["rejected_count"] == 2
        assert result["rejection_rate"] == 13.33

    def test_rejection_rate_calculation(self):
        # 5 rejected out of 20 total = 25%
        by_status = [(DocumentStatus.rejected, 5), (DocumentStatus.approved, 15)]
        db = self._make_db(total=20, by_status=by_status)
        result = document_processing_stats(db)
        assert result["rejection_rate"] == 25.0

    def test_none_avg_confidence(self):
        db = self._make_db(avg_confidence=None)
        result = document_processing_stats(db)
        assert result["average_confidence"] is None

    def test_avg_confidence_rounded(self):
        db = self._make_db(total=5, avg_confidence=0.87654)
        result = document_processing_stats(db)
        assert result["average_confidence"] == 0.88

    def test_zero_total_documents_rejection_rate(self):
        db = self._make_db(total=0)
        result = document_processing_stats(db)
        assert result["rejection_rate"] == 0.0

    def test_all_approved_no_rejections(self):
        by_status = [(DocumentStatus.approved, 10)]
        db = self._make_db(total=10, by_status=by_status, avg_confidence=0.95)
        result = document_processing_stats(db)
        assert result["rejected_count"] == 0
        assert result["rejection_rate"] == 0.0

    def test_none_total_count(self):
        db = self._make_db(total=None)
        result = document_processing_stats(db)
        assert result["total_documents"] == 0
        assert result["rejection_rate"] == 0.0

    def test_execute_called_four_times(self):
        db = self._make_db()
        document_processing_stats(db)
        assert db.execute.call_count == 4

    def test_all_keys_present(self):
        db = self._make_db()
        result = document_processing_stats(db)
        expected_keys = {
            "total_documents",
            "by_status",
            "by_type",
            "average_confidence",
            "rejected_count",
            "rejection_rate",
        }
        assert set(result.keys()) == expected_keys

    def test_by_status_empty(self):
        db = self._make_db(total=0, by_status=[])
        result = document_processing_stats(db)
        assert result["by_status"] == {}

    def test_by_type_empty(self):
        db = self._make_db(total=0, by_type=[])
        result = document_processing_stats(db)
        assert result["by_type"] == {}

    def test_all_rejected(self):
        by_status = [(DocumentStatus.rejected, 5)]
        db = self._make_db(total=5, by_status=by_status, avg_confidence=0.1)
        result = document_processing_stats(db)
        assert result["rejected_count"] == 5
        assert result["rejection_rate"] == 100.0
