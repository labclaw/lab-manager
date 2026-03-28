"""Test receive_items product_id validation."""

from decimal import Decimal

import pytest

from lab_manager.exceptions import ValidationError
from lab_manager.models.order import Order, OrderItem, OrderStatus
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor
from lab_manager.services import inventory as svc


@pytest.fixture
def _vendor(db_session):
    v = Vendor(name="TestVendor-Receive")
    db_session.add(v)
    db_session.flush()
    return v


@pytest.fixture
def _product(db_session, _vendor):
    p = Product(
        catalog_number="RCV-TEST-001",
        name="Receive Test Product",
        vendor_id=_vendor.id,
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def _order(db_session, _vendor):
    o = Order(
        vendor_id=_vendor.id,
        status=OrderStatus.pending,
    )
    db_session.add(o)
    db_session.flush()
    return o


@pytest.fixture
def _order_item(db_session, _order, _product):
    oi = OrderItem(
        order_id=_order.id,
        product_id=_product.id,
        quantity=Decimal("5"),
        unit="ea",
    )
    db_session.add(oi)
    db_session.flush()
    return oi


class TestReceiveItemsValidation:
    def test_missing_product_id_raises(self, db_session, _order):
        """receive_items with no order_item_id and no product_id must raise."""
        with pytest.raises(ValidationError, match="product_id is required"):
            svc.receive_items(
                _order.id,
                [{"quantity": 1}],  # no order_item_id, no product_id
                location_id=None,
                received_by="tester",
                db=db_session,
            )

    def test_with_order_item_id_succeeds(self, db_session, _order, _order_item):
        """receive_items with valid order_item_id should work."""
        result = svc.receive_items(
            _order.id,
            [{"order_item_id": _order_item.id, "quantity": 3}],
            location_id=None,
            received_by="tester",
            db=db_session,
        )
        assert len(result) == 1
        assert result[0].product_id == _order_item.product_id
        assert result[0].quantity_on_hand == Decimal("3")

    def test_with_explicit_product_id_succeeds(self, db_session, _order, _product):
        """receive_items with explicit product_id (no order_item_id) should work."""
        result = svc.receive_items(
            _order.id,
            [{"product_id": _product.id, "quantity": 2}],
            location_id=None,
            received_by="tester",
            db=db_session,
        )
        assert len(result) == 1
        assert result[0].product_id == _product.id
