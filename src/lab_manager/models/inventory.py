"""Inventory stock model."""

import enum
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy import Column
from sqlmodel import Field, Relationship

from lab_manager.models.base import AuditMixin

if TYPE_CHECKING:
    from lab_manager.models.consumption import ConsumptionLog
    from lab_manager.models.location import StorageLocation
    from lab_manager.models.order import OrderItem
    from lab_manager.models.product import Product


class InventoryStatus(enum.StrEnum):
    available = "available"
    opened = "opened"
    depleted = "depleted"
    disposed = "disposed"
    expired = "expired"
    deleted = "deleted"


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

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(
        sa_column=Column(
            sa.Integer,
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            index=True,
            nullable=False,
        ),
    )
    location_id: int | None = Field(
        default=None,
        sa_column=Column(sa.Integer, sa.ForeignKey("locations.id", ondelete="SET NULL"), index=True),
    )
    lot_number: str | None = Field(default=None, max_length=100)
    quantity_on_hand: Decimal = Field(default=0, sa_column=Column(sa.Numeric(12, 4), default=0))
    unit: str | None = Field(default=None, max_length=50)
    expiry_date: date | None = Field(default=None, index=True)
    opened_date: date | None = Field(default=None)
    status: str = Field(default="available", max_length=30, index=True)
    notes: str | None = Field(default=None)
    received_by: str | None = Field(default=None, max_length=200)
    order_item_id: int | None = Field(
        default=None,
        sa_column=Column(sa.Integer, sa.ForeignKey("order_items.id", ondelete="SET NULL")),
    )

    product: "Product" = Relationship(back_populates="inventory_items")
    location: Optional["StorageLocation"] = Relationship(back_populates="inventory_items")
    order_item: Optional["OrderItem"] = Relationship(back_populates="inventory_items")
    consumption_logs: list["ConsumptionLog"] = Relationship(back_populates="inventory_item")
