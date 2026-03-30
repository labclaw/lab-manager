"""Tests for performance and reliability fixes."""

import threading
import time
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fix 1: PubChem rate limiter — slot-claiming correctness under concurrency
# ---------------------------------------------------------------------------


class TestPubChemRateLimiter:
    """Verify _rate_limit enforces minimum interval under concurrent access."""

    def test_rate_limiter_enforces_minimum_interval(self):
        """Two threads calling _rate_limit should be separated by >= MIN_INTERVAL."""
        from lab_manager.services.pubchem import (
            _MIN_INTERVAL,
            _rate_limit,
        )

        timestamps: list[float] = []
        barrier = threading.Barrier(2)

        def worker():
            barrier.wait(timeout=5)
            _rate_limit()
            timestamps.append(time.monotonic())

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert len(timestamps) == 2
        gap = abs(timestamps[1] - timestamps[0])
        assert gap >= _MIN_INTERVAL * 0.9  # allow small scheduling jitter

    def test_rate_limiter_no_burst(self):
        """Rapid sequential calls should each wait the minimum interval."""
        from lab_manager.services.pubchem import _MIN_INTERVAL, _rate_limit

        # Reset module state
        import lab_manager.services.pubchem as _mod

        _mod._last_request_time = 0.0

        times = []
        for _ in range(3):
            _rate_limit()
            times.append(time.monotonic())

        for i in range(1, len(times)):
            gap = times[i] - times[i - 1]
            assert gap >= _MIN_INTERVAL * 0.9


# ---------------------------------------------------------------------------
# Fix 2: IMAP timeout
# ---------------------------------------------------------------------------


class TestIMAPTimeout:
    def test_connect_passes_timeout(self):
        """_connect_imap should pass timeout=30 to IMAP4_SSL."""
        with patch("lab_manager.services.email_poller.imaplib.IMAP4_SSL") as mock_ssl:
            mock_conn = MagicMock()
            mock_ssl.return_value = mock_conn

            from lab_manager.services.email_poller import _connect_imap

            _connect_imap({"host": "imap.example.com", "user": "u"}, "pass")

            mock_ssl.assert_called_once_with("imap.example.com", timeout=30)


# ---------------------------------------------------------------------------
# Fix 3: LiteLLM timeout
# ---------------------------------------------------------------------------


class TestLiteLLMTimeout:
    def test_default_timeout_passed(self):
        """create_completion should pass timeout=60 to litellm.completion."""
        with (
            patch(
                "lab_manager.services.litellm_client.get_client_params"
            ) as mock_params,
            patch("lab_manager.services.litellm_client.completion") as mock_completion,
        ):
            mock_params.return_value = {"model": "gemini/test", "api_key": "k"}
            mock_completion.return_value = MagicMock()

            from lab_manager.services.litellm_client import create_completion

            create_completion(
                model="gemini-2.5-flash", messages=[{"role": "user", "content": "hi"}]
            )

            call_kwargs = mock_completion.call_args[1]
            assert call_kwargs["timeout"] == 60

    def test_custom_timeout_override(self):
        """Caller should be able to override timeout via kwargs."""
        with (
            patch(
                "lab_manager.services.litellm_client.get_client_params"
            ) as mock_params,
            patch("lab_manager.services.litellm_client.completion") as mock_completion,
        ):
            mock_params.return_value = {"model": "gemini/test", "api_key": "k"}
            mock_completion.return_value = MagicMock()

            from lab_manager.services.litellm_client import create_completion

            create_completion(
                model="gemini-2.5-flash",
                messages=[{"role": "user", "content": "hi"}],
                timeout=120,
            )

            call_kwargs = mock_completion.call_args[1]
            assert call_kwargs["timeout"] == 120


# ---------------------------------------------------------------------------
# Fix 5: inventory_value excludes disposed items
# ---------------------------------------------------------------------------


class TestInventoryValueExcludesDisposed:
    def test_disposed_items_excluded(self, client, db_session):
        """Disposed items should not be counted in inventory value."""

        from lab_manager.models.inventory import InventoryItem
        from lab_manager.models.order import Order, OrderItem
        from lab_manager.models.product import Product
        from lab_manager.models.vendor import Vendor

        vendor = Vendor(name="TestVendor")
        db_session.add(vendor)
        db_session.flush()

        product = Product(
            catalog_number="D001", name="Disposal Test", vendor_id=vendor.id
        )
        db_session.add(product)
        db_session.flush()

        order = Order(vendor_id=vendor.id, status="received", received_by="Alice")
        db_session.add(order)
        db_session.flush()

        item = OrderItem(
            order_id=order.id,
            catalog_number="D001",
            description="Disposal Test",
            quantity=1,
            unit_price=100.0,
        )
        db_session.add(item)
        db_session.flush()

        # Active item — should be counted
        active_inv = InventoryItem(
            product_id=product.id,
            order_item_id=item.id,
            quantity_on_hand=2,
            status="available",
        )
        db_session.add(active_inv)

        # Disposed item — should NOT be counted
        disposed_inv = InventoryItem(
            product_id=product.id,
            order_item_id=item.id,
            quantity_on_hand=999,
            status="disposed",
        )
        db_session.add(disposed_inv)
        db_session.commit()

        resp = client.get("/api/v1/analytics/inventory/value")
        assert resp.status_code == 200
        data = resp.json()
        # Only the active item: 2 * $100 = $200
        assert data["total_value"] == 200.0
        assert data["item_count"] == 1


# ---------------------------------------------------------------------------
# Fix 6: list_orders drafts status group maps to pending
# ---------------------------------------------------------------------------


class TestOrdersDraftsStatusGroup:
    def test_drafts_maps_to_pending(self, client, db_session):
        """status_group=drafts should return pending orders."""
        from lab_manager.models.order import Order
        from lab_manager.models.vendor import Vendor

        vendor = Vendor(name="DraftTest Vendor")
        db_session.add(vendor)
        db_session.flush()

        pending_order = Order(
            vendor_id=vendor.id, status="pending", po_number="DRAFT-001"
        )
        db_session.add(pending_order)

        received_order = Order(
            vendor_id=vendor.id, status="received", po_number="RECV-001"
        )
        db_session.add(received_order)
        db_session.commit()

        resp = client.get("/api/v1/orders/?status_group=drafts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["po_number"] == "DRAFT-001"

    def test_unknown_status_group_returns_400(self, client, db_session):
        """Unknown status_group should return 400."""
        resp = client.get("/api/v1/orders/?status_group=nonexistent")
        assert resp.status_code == 400
