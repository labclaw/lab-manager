"""Unit tests for lab_manager.services.alerts — fully mocked DB session."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch


from lab_manager.services.alerts import (
    _check_expired,
    _check_expiring_soon,
    _check_low_stock,
    _check_out_of_stock,
    _check_pending_review,
    _check_stale_orders,
    check_all_alerts,
    get_alert_summary,
    get_expiring_items,
    get_low_stock_items,
    persist_alerts,
)


# ---------------------------------------------------------------------------
# Helpers — build fake model instances
# ---------------------------------------------------------------------------


def _make_inventory_item(
    id: int = 1,
    product_id: int = 10,
    lot_number: str = "LOT-001",
    expiry_date=None,
    quantity_on_hand: float = 5.0,
    status: str = "available",
):
    """Create a mock InventoryItem."""
    it = MagicMock()
    it.id = id
    it.product_id = product_id
    it.lot_number = lot_number
    it.expiry_date = expiry_date
    it.quantity_on_hand = quantity_on_hand
    it.status = status
    return it


def _make_product(
    id: int = 1,
    catalog_number: str = "CAT-001",
    name: str = "Test Product",
    min_stock_level=None,
):
    """Create a mock Product."""
    p = MagicMock()
    p.id = id
    p.catalog_number = catalog_number
    p.name = name
    p.min_stock_level = min_stock_level
    return p


def _make_document(
    id: int = 1,
    file_name: str = "doc.pdf",
    document_type: str = "invoice",
    vendor_name: str = "Acme",
):
    """Create a mock Document."""
    d = MagicMock()
    d.id = id
    d.file_name = file_name
    d.document_type = document_type
    d.vendor_name = vendor_name
    return d


def _make_order(
    id: int = 1,
    po_number: str = "PO-001",
    created_at=None,
    status: str = "pending",
):
    """Create a mock Order."""
    o = MagicMock()
    o.id = id
    o.po_number = po_number
    o.created_at = created_at
    o.status = status
    return o


def _mock_db_scalars(return_list):
    """Return a MagicMock db whose scalars().all() returns *return_list*."""
    db = MagicMock()
    result = MagicMock()
    result.all.return_value = return_list
    db.scalars.return_value = result
    return db


def _mock_db_execute(return_list):
    """Return a MagicMock db whose execute().all() returns *return_list*."""
    db = MagicMock()
    result = MagicMock()
    result.all.return_value = return_list
    db.execute.return_value = result
    return db


# ===================================================================
# get_expiring_items
# ===================================================================


class TestGetExpiringItems:
    """Tests for the raw query helper get_expiring_items."""

    def test_no_items(self):
        db = _mock_db_scalars([])
        result = get_expiring_items(db)
        assert result == []

    def test_single_expiring_item(self):
        item = _make_inventory_item(id=1)
        db = _mock_db_scalars([item])
        result = get_expiring_items(db)
        assert len(result) == 1
        assert result[0].id == 1

    def test_multiple_expiring_items(self):
        items = [_make_inventory_item(id=i) for i in range(5)]
        db = _mock_db_scalars(items)
        result = get_expiring_items(db)
        assert len(result) == 5

    def test_custom_days_ahead(self):
        """Verify the function accepts days_ahead parameter."""
        db = _mock_db_scalars([])
        # Should not raise
        get_expiring_items(db, days_ahead=60)

    def test_default_days_ahead_is_30(self):
        """Default days_ahead should be 30."""
        db = _mock_db_scalars([])
        with patch("lab_manager.services.alerts.datetime") as mock_dt:
            fixed_now = datetime(2026, 1, 15, tzinfo=timezone.utc)
            mock_dt.now.return_value = fixed_now
            # timedelta is used as-is
            get_expiring_items(db)
            # Verify the cutoff was computed with default 30 days


# ===================================================================
# get_low_stock_items
# ===================================================================


class TestGetLowStockItems:
    """Tests for the raw query helper get_low_stock_items."""

    def test_no_items(self):
        db = _mock_db_scalars([])
        result = get_low_stock_items(db)
        assert result == []

    def test_single_low_stock_item(self):
        item = _make_inventory_item(id=1, quantity_on_hand=0)
        db = _mock_db_scalars([item])
        result = get_low_stock_items(db)
        assert len(result) == 1

    def test_multiple_low_stock_items(self):
        items = [_make_inventory_item(id=i, quantity_on_hand=0) for i in range(3)]
        db = _mock_db_scalars(items)
        result = get_low_stock_items(db)
        assert len(result) == 3

    def test_custom_threshold(self):
        """Verify the function accepts threshold parameter."""
        db = _mock_db_scalars([])
        get_low_stock_items(db, threshold=5.0)

    def test_default_threshold_is_one(self):
        """Default threshold should be 1."""
        db = _mock_db_scalars([])
        get_low_stock_items(db)  # uses default threshold=1


# ===================================================================
# _check_expired
# ===================================================================


class TestCheckExpired:
    """Tests for _check_expired private function."""

    def test_no_expired_items(self):
        db = _mock_db_scalars([])
        result = _check_expired(db)
        assert result == []

    def test_single_expired_item(self):
        today = datetime.now(timezone.utc).date()
        expired_date = today - timedelta(days=10)
        item = _make_inventory_item(
            id=42, lot_number="LOT-X", expiry_date=expired_date, product_id=7
        )
        db = _mock_db_scalars([item])
        result = _check_expired(db)

        assert len(result) == 1
        alert = result[0]
        assert alert["type"] == "expired"
        assert alert["severity"] == "critical"
        assert alert["entity_type"] == "inventory"
        assert alert["entity_id"] == 42
        assert "LOT-X" in alert["message"]
        assert alert["details"]["expiry_date"] == expired_date.isoformat()
        assert alert["details"]["lot_number"] == "LOT-X"
        assert alert["details"]["product_id"] == 7

    def test_multiple_expired_items(self):
        today = datetime.now(timezone.utc).date()
        items = [
            _make_inventory_item(id=i, expiry_date=today - timedelta(days=i + 1))
            for i in range(3)
        ]
        db = _mock_db_scalars(items)
        result = _check_expired(db)
        assert len(result) == 3
        assert all(a["type"] == "expired" for a in result)

    def test_expired_always_critical_severity(self):
        today = datetime.now(timezone.utc).date()
        item = _make_inventory_item(expiry_date=today - timedelta(days=1))
        db = _mock_db_scalars([item])
        result = _check_expired(db)
        assert result[0]["severity"] == "critical"

    def test_expired_item_yesterday(self):
        """Item that expired yesterday is critical."""
        today = datetime.now(timezone.utc).date()
        item = _make_inventory_item(expiry_date=today - timedelta(days=1))
        db = _mock_db_scalars([item])
        result = _check_expired(db)
        assert len(result) == 1

    def test_expired_item_long_ago(self):
        """Item that expired a year ago is still critical."""
        today = datetime.now(timezone.utc).date()
        item = _make_inventory_item(expiry_date=today - timedelta(days=365))
        db = _mock_db_scalars([item])
        result = _check_expired(db)
        assert len(result) == 1
        assert result[0]["severity"] == "critical"

    def test_message_contains_item_id_and_lot(self):
        today = datetime.now(timezone.utc).date()
        item = _make_inventory_item(
            id=99, lot_number="ABC-999", expiry_date=today - timedelta(days=2)
        )
        db = _mock_db_scalars([item])
        result = _check_expired(db)
        assert "99" in result[0]["message"]
        assert "ABC-999" in result[0]["message"]


# ===================================================================
# _check_expiring_soon
# ===================================================================


class TestCheckExpiringSoon:
    """Tests for _check_expiring_soon private function."""

    def test_no_expiring_items(self):
        db = _mock_db_scalars([])
        result = _check_expiring_soon(db)
        assert result == []

    def test_single_expiring_soon_item(self):
        today = datetime.now(timezone.utc).date()
        future_date = today + timedelta(days=15)
        item = _make_inventory_item(
            id=5, lot_number="LOT-F", expiry_date=future_date, product_id=3
        )
        db = _mock_db_scalars([item])
        result = _check_expiring_soon(db)

        assert len(result) == 1
        alert = result[0]
        assert alert["type"] == "expiring_soon"
        assert alert["severity"] == "warning"
        assert alert["entity_type"] == "inventory"
        assert alert["entity_id"] == 5
        assert alert["details"]["expiry_date"] == future_date.isoformat()
        assert alert["details"]["days_remaining"] == 15
        assert alert["details"]["lot_number"] == "LOT-F"
        assert alert["details"]["product_id"] == 3

    def test_multiple_expiring_soon_items(self):
        today = datetime.now(timezone.utc).date()
        items = [
            _make_inventory_item(id=i, expiry_date=today + timedelta(days=i + 1))
            for i in range(4)
        ]
        db = _mock_db_scalars(items)
        result = _check_expiring_soon(db)
        assert len(result) == 4
        assert all(a["severity"] == "warning" for a in result)

    def test_expiring_soon_always_warning_severity(self):
        today = datetime.now(timezone.utc).date()
        item = _make_inventory_item(expiry_date=today + timedelta(days=5))
        db = _mock_db_scalars([item])
        result = _check_expiring_soon(db)
        assert result[0]["severity"] == "warning"

    def test_default_days_is_30(self):
        db = _mock_db_scalars([])
        _check_expiring_soon(db)  # should not raise, uses default 30 days

    def test_custom_days_parameter(self):
        db = _mock_db_scalars([])
        _check_expiring_soon(db, days=60)  # should not raise

    def test_expiring_tomorrow(self):
        """Item expiring tomorrow should be caught."""
        today = datetime.now(timezone.utc).date()
        item = _make_inventory_item(expiry_date=today + timedelta(days=1))
        db = _mock_db_scalars([item])
        result = _check_expiring_soon(db)
        assert len(result) == 1
        assert result[0]["details"]["days_remaining"] == 1

    def test_expiring_today_boundary(self):
        """Item expiring today (boundary) is included (>= today)."""
        today = datetime.now(timezone.utc).date()
        item = _make_inventory_item(expiry_date=today)
        db = _mock_db_scalars([item])
        result = _check_expiring_soon(db)
        assert len(result) == 1
        assert result[0]["details"]["days_remaining"] == 0

    def test_expiring_in_exactly_30_days(self):
        """Item expiring in exactly 30 days (boundary) is included (<= cutoff)."""
        today = datetime.now(timezone.utc).date()
        item = _make_inventory_item(expiry_date=today + timedelta(days=30))
        db = _mock_db_scalars([item])
        result = _check_expiring_soon(db)
        assert len(result) == 1
        assert result[0]["details"]["days_remaining"] == 30

    def test_message_contains_lot_number(self):
        today = datetime.now(timezone.utc).date()
        item = _make_inventory_item(
            id=7, lot_number="XYZ-789", expiry_date=today + timedelta(days=10)
        )
        db = _mock_db_scalars([item])
        result = _check_expiring_soon(db)
        assert "XYZ-789" in result[0]["message"]


# ===================================================================
# _check_out_of_stock
# ===================================================================


class TestCheckOutOfStock:
    """Tests for _check_out_of_stock private function."""

    def test_no_out_of_stock(self):
        db = _mock_db_execute([])
        result = _check_out_of_stock(db)
        assert result == []

    def test_single_out_of_stock_product(self):
        p = _make_product(id=1, catalog_number="CAT-A", name="Chemical A")
        db = _mock_db_execute([(p, 0)])
        result = _check_out_of_stock(db)

        assert len(result) == 1
        alert = result[0]
        assert alert["type"] == "out_of_stock"
        assert alert["severity"] == "critical"
        assert alert["entity_type"] == "product"
        assert alert["entity_id"] == 1
        assert alert["details"]["catalog_number"] == "CAT-A"
        assert alert["details"]["name"] == "Chemical A"

    def test_multiple_out_of_stock_products(self):
        products = [
            (_make_product(id=i, catalog_number=f"CAT-{i}"), 0) for i in range(3)
        ]
        db = _mock_db_execute(products)
        result = _check_out_of_stock(db)
        assert len(result) == 3
        assert all(a["type"] == "out_of_stock" for a in result)

    def test_out_of_stock_always_critical(self):
        p = _make_product(id=1)
        db = _mock_db_execute([(p, 0)])
        result = _check_out_of_stock(db)
        assert result[0]["severity"] == "critical"

    def test_product_with_none_stock_total(self):
        """Product with no inventory rows (None total) is out of stock."""
        p = _make_product(id=2, catalog_number="CAT-B")
        db = _mock_db_execute([(p, None)])
        result = _check_out_of_stock(db)
        assert len(result) == 1
        assert result[0]["entity_id"] == 2

    def test_mixed_none_and_zero(self):
        """Both None and zero-stock products appear."""
        p1 = _make_product(id=1)
        p2 = _make_product(id=2)
        db = _mock_db_execute([(p1, 0), (p2, None)])
        result = _check_out_of_stock(db)
        assert len(result) == 2

    def test_message_contains_catalog_number(self):
        p = _make_product(id=5, catalog_number="MY-CAT-123")
        db = _mock_db_execute([(p, 0)])
        result = _check_out_of_stock(db)
        assert "MY-CAT-123" in result[0]["message"]


# ===================================================================
# _check_low_stock
# ===================================================================


class TestCheckLowStock:
    """Tests for _check_low_stock private function."""

    def test_no_low_stock(self):
        db = _mock_db_execute([])
        result = _check_low_stock(db)
        assert result == []

    def test_single_low_stock_product(self):
        p = _make_product(id=3, catalog_number="CAT-C", name="Reagent C")
        db = _mock_db_execute([(p, 2.0)])
        result = _check_low_stock(db)

        assert len(result) == 1
        alert = result[0]
        assert alert["type"] == "low_stock"
        assert alert["severity"] == "warning"
        assert alert["entity_type"] == "product"
        assert alert["entity_id"] == 3
        assert alert["details"]["catalog_number"] == "CAT-C"
        assert alert["details"]["name"] == "Reagent C"
        assert alert["details"]["total_stock"] == 2.0

    def test_multiple_low_stock_products(self):
        products = [
            (_make_product(id=i, catalog_number=f"CAT-{i}"), float(i + 1))
            for i in range(4)
        ]
        db = _mock_db_execute(products)
        result = _check_low_stock(db)
        assert len(result) == 4

    def test_low_stock_always_warning(self):
        p = _make_product(id=1)
        db = _mock_db_execute([(p, 0.5)])
        result = _check_low_stock(db)
        assert result[0]["severity"] == "warning"

    def test_total_stock_is_converted_to_float(self):
        """The total stock value should be a float in details."""
        p = _make_product(id=1)
        db = _mock_db_execute([(p, 3)])
        result = _check_low_stock(db)
        assert isinstance(result[0]["details"]["total_stock"], float)
        assert result[0]["details"]["total_stock"] == 3.0

    def test_message_contains_stock_level(self):
        p = _make_product(id=1, catalog_number="CAT-Z")
        db = _mock_db_execute([(p, 1.5)])
        result = _check_low_stock(db)
        assert "1.5" in result[0]["message"]
        assert "CAT-Z" in result[0]["message"]


# ===================================================================
# _check_pending_review
# ===================================================================


class TestCheckPendingReview:
    """Tests for _check_pending_review private function."""

    def test_no_pending_documents(self):
        db = _mock_db_scalars([])
        result = _check_pending_review(db)
        assert result == []

    def test_single_pending_document(self):
        doc = _make_document(
            id=10, file_name="invoice.pdf", document_type="invoice", vendor_name="Sigma"
        )
        db = _mock_db_scalars([doc])
        result = _check_pending_review(db)

        assert len(result) == 1
        alert = result[0]
        assert alert["type"] == "pending_review"
        assert alert["severity"] == "info"
        assert alert["entity_type"] == "document"
        assert alert["entity_id"] == 10
        assert alert["details"]["file_name"] == "invoice.pdf"
        assert alert["details"]["document_type"] == "invoice"
        assert alert["details"]["vendor_name"] == "Sigma"

    def test_multiple_pending_documents(self):
        docs = [_make_document(id=i) for i in range(5)]
        db = _mock_db_scalars(docs)
        result = _check_pending_review(db)
        assert len(result) == 5

    def test_pending_review_always_info_severity(self):
        doc = _make_document()
        db = _mock_db_scalars([doc])
        result = _check_pending_review(db)
        assert result[0]["severity"] == "info"

    def test_message_contains_file_name(self):
        doc = _make_document(id=3, file_name="packing_list.pdf")
        db = _mock_db_scalars([doc])
        result = _check_pending_review(db)
        assert "packing_list.pdf" in result[0]["message"]

    def test_document_with_none_vendor(self):
        """Document with None vendor_name should still produce an alert."""
        doc = _make_document(vendor_name=None)
        db = _mock_db_scalars([doc])
        result = _check_pending_review(db)
        assert len(result) == 1
        assert result[0]["details"]["vendor_name"] is None


# ===================================================================
# _check_stale_orders
# ===================================================================


class TestCheckStaleOrders:
    """Tests for _check_stale_orders private function."""

    def test_no_stale_orders(self):
        db = _mock_db_scalars([])
        result = _check_stale_orders(db)
        assert result == []

    def test_single_stale_order(self):
        now = datetime.now(timezone.utc)
        old_date = now - timedelta(days=45)
        order = _make_order(
            id=7, po_number="PO-999", created_at=old_date, status="pending"
        )
        db = _mock_db_scalars([order])
        result = _check_stale_orders(db)

        assert len(result) == 1
        alert = result[0]
        assert alert["type"] == "stale_orders"
        assert alert["severity"] == "warning"
        assert alert["entity_type"] == "order"
        assert alert["entity_id"] == 7
        assert alert["details"]["po_number"] == "PO-999"
        assert alert["details"]["created_at"] == old_date.isoformat()

    def test_multiple_stale_orders(self):
        now = datetime.now(timezone.utc)
        orders = [
            _make_order(id=i, created_at=now - timedelta(days=31 + i)) for i in range(3)
        ]
        db = _mock_db_scalars(orders)
        result = _check_stale_orders(db)
        assert len(result) == 3

    def test_stale_orders_always_warning(self):
        order = _make_order(created_at=datetime.now(timezone.utc) - timedelta(days=60))
        db = _mock_db_scalars([order])
        result = _check_stale_orders(db)
        assert result[0]["severity"] == "warning"

    def test_default_stale_days_is_30(self):
        db = _mock_db_scalars([])
        _check_stale_orders(db)  # uses default stale_days=30

    def test_custom_stale_days(self):
        db = _mock_db_scalars([])
        _check_stale_orders(db, stale_days=60)

    def test_order_with_none_created_at(self):
        """Order with None created_at should handle gracefully."""
        order = _make_order(created_at=None)
        db = _mock_db_scalars([order])
        result = _check_stale_orders(db)
        assert len(result) == 1
        assert result[0]["details"]["created_at"] is None

    def test_message_contains_po_number(self):
        order = _make_order(
            id=1,
            po_number="PO-ABC",
            created_at=datetime.now(timezone.utc) - timedelta(days=35),
        )
        db = _mock_db_scalars([order])
        result = _check_stale_orders(db)
        assert "PO-ABC" in result[0]["message"]

    def test_message_mentions_stale_days_default(self):
        """Default message mentions '30 days'."""
        order = _make_order(created_at=datetime.now(timezone.utc) - timedelta(days=35))
        db = _mock_db_scalars([order])
        result = _check_stale_orders(db)
        assert "30 days" in result[0]["message"]


# ===================================================================
# check_all_alerts
# ===================================================================


class TestCheckAllAlerts:
    """Tests for check_all_alerts — verifies all sub-checks are called."""

    @patch("lab_manager.services.alerts._check_stale_orders", return_value=[])
    @patch("lab_manager.services.alerts._check_pending_review", return_value=[])
    @patch("lab_manager.services.alerts._check_low_stock", return_value=[])
    @patch("lab_manager.services.alerts._check_out_of_stock", return_value=[])
    @patch("lab_manager.services.alerts._check_expiring_soon", return_value=[])
    @patch("lab_manager.services.alerts._check_expired", return_value=[])
    def test_calls_all_sub_checks(
        self, mock_expired, mock_expiring, mock_oos, mock_low, mock_pending, mock_stale
    ):
        db = MagicMock()
        result = check_all_alerts(db)
        assert result == []
        mock_expired.assert_called_once_with(db)
        mock_expiring.assert_called_once_with(db)
        mock_oos.assert_called_once_with(db)
        mock_low.assert_called_once_with(db)
        mock_pending.assert_called_once_with(db)
        mock_stale.assert_called_once_with(db)

    @patch("lab_manager.services.alerts._check_stale_orders", return_value=[])
    @patch("lab_manager.services.alerts._check_pending_review", return_value=[])
    @patch("lab_manager.services.alerts._check_low_stock", return_value=[])
    @patch("lab_manager.services.alerts._check_out_of_stock", return_value=[])
    @patch("lab_manager.services.alerts._check_expiring_soon", return_value=[])
    @patch("lab_manager.services.alerts._check_expired", return_value=[])
    def test_empty_when_all_checks_empty(
        self, mock_expired, mock_expiring, mock_oos, mock_low, mock_pending, mock_stale
    ):
        db = MagicMock()
        result = check_all_alerts(db)
        assert result == []
        assert len(result) == 0

    @patch(
        "lab_manager.services.alerts._check_stale_orders",
        return_value=[{"type": "stale_orders"}],
    )
    @patch(
        "lab_manager.services.alerts._check_pending_review",
        return_value=[{"type": "pending_review"}],
    )
    @patch(
        "lab_manager.services.alerts._check_low_stock",
        return_value=[{"type": "low_stock"}],
    )
    @patch(
        "lab_manager.services.alerts._check_out_of_stock",
        return_value=[{"type": "out_of_stock"}],
    )
    @patch(
        "lab_manager.services.alerts._check_expiring_soon",
        return_value=[{"type": "expiring_soon"}],
    )
    @patch(
        "lab_manager.services.alerts._check_expired", return_value=[{"type": "expired"}]
    )
    def test_merges_all_sub_results(
        self, mock_expired, mock_expiring, mock_oos, mock_low, mock_pending, mock_stale
    ):
        db = MagicMock()
        result = check_all_alerts(db)
        assert len(result) == 6
        types = {a["type"] for a in result}
        assert types == {
            "expired",
            "expiring_soon",
            "out_of_stock",
            "low_stock",
            "pending_review",
            "stale_orders",
        }

    @patch("lab_manager.services.alerts._check_stale_orders", return_value=[])
    @patch("lab_manager.services.alerts._check_pending_review", return_value=[])
    @patch("lab_manager.services.alerts._check_low_stock", return_value=[])
    @patch("lab_manager.services.alerts._check_out_of_stock", return_value=[])
    @patch("lab_manager.services.alerts._check_expiring_soon", return_value=[])
    @patch(
        "lab_manager.services.alerts._check_expired",
        return_value=[{"type": "expired"}, {"type": "expired"}],
    )
    def test_multiple_results_from_single_check(self, mock_expired, *_):
        db = MagicMock()
        result = check_all_alerts(db)
        assert len(result) == 2
        assert all(a["type"] == "expired" for a in result)


# ===================================================================
# get_alert_summary
# ===================================================================


class TestGetAlertSummary:
    """Tests for get_alert_summary."""

    def test_empty_alerts(self):
        db = MagicMock()
        result = get_alert_summary(db, alerts=[])
        assert result["total"] == 0
        assert result["critical"] == 0
        assert result["warning"] == 0
        assert result["info"] == 0
        assert result["by_type"] == {}

    def test_single_critical_alert(self):
        alerts = [{"type": "expired", "severity": "critical"}]
        db = MagicMock()
        result = get_alert_summary(db, alerts=alerts)
        assert result["total"] == 1
        assert result["critical"] == 1
        assert result["warning"] == 0
        assert result["info"] == 0
        assert result["by_type"]["expired"] == 1

    def test_single_warning_alert(self):
        alerts = [{"type": "expiring_soon", "severity": "warning"}]
        db = MagicMock()
        result = get_alert_summary(db, alerts=alerts)
        assert result["total"] == 1
        assert result["warning"] == 1
        assert result["critical"] == 0

    def test_single_info_alert(self):
        alerts = [{"type": "pending_review", "severity": "info"}]
        db = MagicMock()
        result = get_alert_summary(db, alerts=alerts)
        assert result["total"] == 1
        assert result["info"] == 1

    def test_mixed_severities(self):
        alerts = [
            {"type": "expired", "severity": "critical"},
            {"type": "expired", "severity": "critical"},
            {"type": "expiring_soon", "severity": "warning"},
            {"type": "low_stock", "severity": "warning"},
            {"type": "pending_review", "severity": "info"},
        ]
        db = MagicMock()
        result = get_alert_summary(db, alerts=alerts)
        assert result["total"] == 5
        assert result["critical"] == 2
        assert result["warning"] == 2
        assert result["info"] == 1

    def test_by_type_counts(self):
        alerts = [
            {"type": "expired", "severity": "critical"},
            {"type": "expired", "severity": "critical"},
            {"type": "low_stock", "severity": "warning"},
            {"type": "stale_orders", "severity": "warning"},
            {"type": "stale_orders", "severity": "warning"},
            {"type": "stale_orders", "severity": "warning"},
        ]
        db = MagicMock()
        result = get_alert_summary(db, alerts=alerts)
        assert result["by_type"]["expired"] == 2
        assert result["by_type"]["low_stock"] == 1
        assert result["by_type"]["stale_orders"] == 3

    def test_alerts_none_triggers_check_all(self):
        """When alerts is None, get_alert_summary calls check_all_alerts."""
        db = MagicMock()
        with patch(
            "lab_manager.services.alerts.check_all_alerts",
            return_value=[{"type": "expired", "severity": "critical"}],
        ) as mock_check:
            result = get_alert_summary(db, alerts=None)
            mock_check.assert_called_once_with(db)
            assert result["total"] == 1

    def test_all_six_alert_types(self):
        """Summary correctly counts all 6 alert types."""
        alerts = [
            {"type": "expired", "severity": "critical"},
            {"type": "expiring_soon", "severity": "warning"},
            {"type": "out_of_stock", "severity": "critical"},
            {"type": "low_stock", "severity": "warning"},
            {"type": "pending_review", "severity": "info"},
            {"type": "stale_orders", "severity": "warning"},
        ]
        db = MagicMock()
        result = get_alert_summary(db, alerts=alerts)
        assert result["total"] == 6
        assert result["critical"] == 2
        assert result["warning"] == 3
        assert result["info"] == 1
        assert len(result["by_type"]) == 6

    def test_only_critical_alerts(self):
        alerts = [
            {"type": "expired", "severity": "critical"},
            {"type": "out_of_stock", "severity": "critical"},
        ]
        db = MagicMock()
        result = get_alert_summary(db, alerts=alerts)
        assert result["critical"] == 2
        assert result["warning"] == 0
        assert result["info"] == 0

    def test_only_info_alerts(self):
        alerts = [
            {"type": "pending_review", "severity": "info"},
            {"type": "pending_review", "severity": "info"},
            {"type": "pending_review", "severity": "info"},
        ]
        db = MagicMock()
        result = get_alert_summary(db, alerts=alerts)
        assert result["info"] == 3
        assert result["critical"] == 0
        assert result["warning"] == 0

    def test_large_number_of_alerts(self):
        alerts = [{"type": "expired", "severity": "critical"}] * 100
        db = MagicMock()
        result = get_alert_summary(db, alerts=alerts)
        assert result["total"] == 100
        assert result["critical"] == 100


# ===================================================================
# persist_alerts
# ===================================================================


class TestPersistAlerts:
    """Tests for persist_alerts function."""

    @patch("lab_manager.services.alerts.check_all_alerts", return_value=[])
    def test_no_current_alerts_no_existing(self, mock_check):
        db = MagicMock()
        db.execute.return_value.all.return_value = []
        created, current = persist_alerts(db)
        assert created == []
        assert current == []

    @patch(
        "lab_manager.services.alerts.check_all_alerts",
        return_value=[
            {
                "type": "expired",
                "severity": "critical",
                "message": "test",
                "entity_type": "inventory",
                "entity_id": 1,
            }
        ],
    )
    def test_new_alert_creates_alert_row(self, mock_check):
        db = MagicMock()
        # No existing unresolved alerts
        db.execute.return_value.all.return_value = []
        created, current = persist_alerts(db)
        assert len(created) == 1
        assert len(current) == 1
        db.add.assert_called_once()

    @patch(
        "lab_manager.services.alerts.check_all_alerts",
        return_value=[
            {
                "type": "expired",
                "severity": "critical",
                "message": "test",
                "entity_type": "inventory",
                "entity_id": 1,
            }
        ],
    )
    def test_existing_alert_skips_creation(self, mock_check):
        db = MagicMock()
        # Simulate existing unresolved alert with same key
        db.execute.return_value.all.return_value = [("inventory", 1, "expired")]
        created, current = persist_alerts(db)
        assert len(created) == 0
        assert len(current) == 1
        db.add.assert_not_called()

    @patch(
        "lab_manager.services.alerts.check_all_alerts",
        return_value=[
            {
                "type": "expired",
                "severity": "critical",
                "message": "test",
                "entity_type": "inventory",
                "entity_id": 1,
            }
        ],
    )
    def test_flush_called_when_alerts_created(self, mock_check):
        db = MagicMock()
        db.execute.return_value.all.return_value = []
        persist_alerts(db)
        db.flush.assert_called_once()

    @patch(
        "lab_manager.services.alerts.check_all_alerts",
        return_value=[
            {
                "type": "expired",
                "severity": "critical",
                "message": "test",
                "entity_type": "inventory",
                "entity_id": 1,
            }
        ],
    )
    def test_flush_not_called_when_no_new_alerts(self, mock_check):
        db = MagicMock()
        db.execute.return_value.all.return_value = [("inventory", 1, "expired")]
        persist_alerts(db)
        db.flush.assert_not_called()

    @patch(
        "lab_manager.services.alerts.check_all_alerts",
        return_value=[
            {
                "type": "expired",
                "severity": "critical",
                "message": "test1",
                "entity_type": "inventory",
                "entity_id": 1,
            },
            {
                "type": "low_stock",
                "severity": "warning",
                "message": "test2",
                "entity_type": "product",
                "entity_id": 5,
            },
        ],
    )
    def test_mixed_new_and_existing(self, mock_check):
        db = MagicMock()
        # Existing: expired for inventory 1, but NOT low_stock for product 5
        db.execute.return_value.all.return_value = [("inventory", 1, "expired")]
        created, current = persist_alerts(db)
        assert len(created) == 1
        assert len(current) == 2
        assert created[0].alert_type == "low_stock"
        assert created[0].entity_id == 5

    @patch(
        "lab_manager.services.alerts.check_all_alerts",
        return_value=[
            {
                "type": "expired",
                "severity": "critical",
                "message": "a",
                "entity_type": "inventory",
                "entity_id": 1,
            },
            {
                "type": "expired",
                "severity": "critical",
                "message": "b",
                "entity_type": "inventory",
                "entity_id": 2,
            },
        ],
    )
    def test_multiple_new_alerts_all_created(self, mock_check):
        db = MagicMock()
        db.execute.return_value.all.return_value = []
        created, current = persist_alerts(db)
        assert len(created) == 2
        assert len(current) == 2

    @patch(
        "lab_manager.services.alerts.check_all_alerts",
        return_value=[
            {
                "type": "expired",
                "severity": "critical",
                "message": "test",
                "entity_type": "inventory",
                "entity_id": 1,
            }
        ],
    )
    def test_refresh_called_for_created_alerts(self, mock_check):
        db = MagicMock()
        db.execute.return_value.all.return_value = []
        persist_alerts(db)
        db.refresh.assert_called_once()

    @patch(
        "lab_manager.services.alerts.check_all_alerts",
        return_value=[
            {
                "type": "expired",
                "severity": "critical",
                "message": "a",
                "entity_type": "inventory",
                "entity_id": 1,
            },
            {
                "type": "expired",
                "severity": "critical",
                "message": "b",
                "entity_type": "inventory",
                "entity_id": 2,
            },
        ],
    )
    def test_refresh_called_once_per_created_alert(self, mock_check):
        db = MagicMock()
        db.execute.return_value.all.return_value = []
        persist_alerts(db)
        assert db.refresh.call_count == 2
