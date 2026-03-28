"""Test inventory state transition guards — dispose and open must reject terminal states."""

from decimal import Decimal

import pytest

from lab_manager.exceptions import ValidationError
from lab_manager.models.inventory import InventoryItem, InventoryStatus
from lab_manager.models.product import Product
from lab_manager.services import inventory as svc


@pytest.fixture
def _product(db_session):
    """Create a minimal product for FK constraint."""
    p = Product(catalog_number="GUARD-TEST-001", name="State Guard Test Product")
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def _item_factory(db_session, _product):
    """Factory to create inventory items in any status."""
    created = []

    def _make(status=InventoryStatus.available, qty=Decimal("10")):
        item = InventoryItem(
            product_id=_product.id,
            quantity_on_hand=qty,
            unit="ea",
            status=status,
            received_by="tester",
        )
        db_session.add(item)
        db_session.flush()
        created.append(item)
        return item

    yield _make


class TestDisposeStateGuard:
    def test_dispose_disposed_raises(self, db_session, _item_factory):
        item = _item_factory(status=InventoryStatus.disposed, qty=Decimal("0"))
        with pytest.raises(ValidationError, match="Cannot dispose"):
            svc.dispose(item.id, "double dispose", "tester", db_session)

    def test_dispose_deleted_raises(self, db_session, _item_factory):
        item = _item_factory(status=InventoryStatus.deleted, qty=Decimal("0"))
        with pytest.raises(ValidationError, match="Cannot dispose"):
            svc.dispose(item.id, "dispose deleted", "tester", db_session)

    def test_dispose_available_succeeds(self, db_session, _item_factory):
        item = _item_factory(status=InventoryStatus.available)
        result = svc.dispose(item.id, "valid dispose", "tester", db_session)
        assert result.status == InventoryStatus.disposed
        assert result.quantity_on_hand == Decimal("0")


class TestOpenItemStateGuard:
    def test_open_disposed_raises(self, db_session, _item_factory):
        item = _item_factory(status=InventoryStatus.disposed, qty=Decimal("0"))
        with pytest.raises(ValidationError, match="Cannot open"):
            svc.open_item(item.id, "tester", db_session)

    def test_open_deleted_raises(self, db_session, _item_factory):
        item = _item_factory(status=InventoryStatus.deleted, qty=Decimal("0"))
        with pytest.raises(ValidationError, match="Cannot open"):
            svc.open_item(item.id, "tester", db_session)

    def test_open_depleted_raises(self, db_session, _item_factory):
        item = _item_factory(status=InventoryStatus.depleted, qty=Decimal("0"))
        with pytest.raises(ValidationError, match="Cannot open"):
            svc.open_item(item.id, "tester", db_session)

    def test_open_expired_raises(self, db_session, _item_factory):
        item = _item_factory(status=InventoryStatus.expired, qty=Decimal("0"))
        with pytest.raises(ValidationError, match="Cannot open"):
            svc.open_item(item.id, "tester", db_session)

    def test_open_available_succeeds(self, db_session, _item_factory):
        item = _item_factory(status=InventoryStatus.available)
        result = svc.open_item(item.id, "tester", db_session)
        assert result.status == InventoryStatus.opened
        assert result.opened_date is not None
