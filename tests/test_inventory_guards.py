"""Test inventory state guards: depleted items cannot be opened."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from lab_manager.exceptions import ValidationError
from lab_manager.models.inventory import InventoryItem, InventoryStatus
from lab_manager.models.product import Product
from lab_manager.services.inventory import open_item


def test_open_depleted_item_raises(db_session):
    """Opening a depleted item must raise ValidationError."""
    product = Product(catalog_number="TEST-001", name="Test Chemical")
    db_session.add(product)
    db_session.flush()

    item = InventoryItem(
        product_id=product.id,
        location_id=None,
        quantity_on_hand=Decimal("0"),
        status=InventoryStatus.depleted,
        received_date=datetime.now(timezone.utc).date(),
    )
    db_session.add(item)
    db_session.flush()

    with pytest.raises(ValidationError, match="depleted"):
        open_item(item.id, "tester", db_session)
