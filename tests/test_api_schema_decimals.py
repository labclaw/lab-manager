"""API schema tests for Decimal-backed quantity and money fields."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from lab_manager.api.routes.equipment import EquipmentCreate, EquipmentUpdate
from lab_manager.api.routes.inventory import ConsumeBody, InventoryItemCreate
from lab_manager.api.routes.orders import OrderItemCreate


def test_order_item_create_uses_decimal_fields():
    body = OrderItemCreate(quantity="1.2500", unit_price="9.9900")

    assert isinstance(body.quantity, Decimal)
    assert body.quantity == Decimal("1.2500")
    assert isinstance(body.unit_price, Decimal)
    assert body.unit_price == Decimal("9.9900")


def test_inventory_create_and_consume_use_decimal_fields():
    create_body = InventoryItemCreate(product_id=1, quantity_on_hand="3.5000")
    consume_body = ConsumeBody(quantity="0.2500", consumed_by="scientist")

    assert isinstance(create_body.quantity_on_hand, Decimal)
    assert create_body.quantity_on_hand == Decimal("3.5000")
    assert isinstance(consume_body.quantity, Decimal)
    assert consume_body.quantity == Decimal("0.2500")


def test_equipment_estimated_value_uses_decimal():
    create_body = EquipmentCreate(name="Centrifuge", estimated_value="1250.50")
    update_body = EquipmentUpdate(estimated_value="999.99")

    assert isinstance(create_body.estimated_value, Decimal)
    assert create_body.estimated_value == Decimal("1250.50")
    assert isinstance(update_body.estimated_value, Decimal)
    assert update_body.estimated_value == Decimal("999.99")


def test_equipment_estimated_value_rejects_negative_values():
    with pytest.raises(ValidationError):
        EquipmentCreate(name="Microscope", estimated_value="-1")

    with pytest.raises(ValidationError):
        EquipmentUpdate(estimated_value="-1")
