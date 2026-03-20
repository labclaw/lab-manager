"""Inventory stock model."""

import enum
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

import sqlalchemy as sa
from sqlalchemy import Column
from sqlmodel import Field, Relationship

from lab_manager.models.base import AuditMixin

if TYPE_CHECKING:
    from lab_manager.models.consumption import ConsumptionLog
    from lab_manager.models.location import StorageLocation
    from lab_manager.models.order import OrderItem
    from lab_manager.models.product import Product


class InventoryStatus(str, enum.Enum):
    available = "available"
    opened = "opened"
    depleted = "depleted"
    disposed = "disposed"
    expired = "expired"
    deleted = "deleted"


# Canonical set of statuses considered "active" for stock and expiry calculations.
# available = unopened and usable, opened = in-use but still usable.
ACTIVE_STATUSES = frozenset({InventoryStatus.available, InventoryStatus.opened})


class InventoryItem(AuditMixin, table=True):
    __tablename__ = "inventory"
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('available','opened','depleted','disposed','expired','deleted')",
            name="ck_inventory_status",
        ),
        sa.CheckConstraint(
            "quantity_on_hand >= 0",
            name="ck_inventory_qty_nonneg",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(
        sa_column=Column(
            sa.Integer,
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            index=True,
            nullable=False,
        ),
    )
    location_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            sa.Integer, sa.ForeignKey("locations.id", ondelete="SET NULL"), index=True
        ),
    )
    lot_number: Optional[str] = Field(default=None, max_length=100)
    quantity_on_hand: Decimal = Field(
        default=0, sa_column=Column(sa.Numeric(12, 4), default=0)
    )
    unit: Optional[str] = Field(default=None, max_length=50)
    expiry_date: Optional[date] = Field(default=None, index=True)
    opened_date: Optional[date] = Field(default=None)
    status: str = Field(default="available", max_length=30, index=True)
    notes: Optional[str] = Field(default=None)
    received_by: Optional[str] = Field(default=None, max_length=200)
    order_item_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            sa.Integer, sa.ForeignKey("order_items.id", ondelete="SET NULL"), index=True
        ),
    )

    product: "Product" = Relationship(back_populates="inventory_items")
    location: Optional["StorageLocation"] = Relationship(
        back_populates="inventory_items"
    )
    order_item: Optional["OrderItem"] = Relationship(back_populates="inventory_items")
    consumption_logs: List["ConsumptionLog"] = Relationship(
        back_populates="inventory_item"
    )
