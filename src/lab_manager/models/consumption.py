"""Consumption log model for tracking all inventory state changes."""

import enum
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy import Column
from sqlmodel import Field, Relationship

from lab_manager.models.base import AuditMixin

if TYPE_CHECKING:
    from lab_manager.models.inventory import InventoryItem
    from lab_manager.models.product import Product


class ConsumptionAction(str, enum.Enum):
    receive = "receive"
    consume = "consume"
    transfer = "transfer"
    adjust = "adjust"
    dispose = "dispose"
    open = "open"


class ConsumptionLog(AuditMixin, table=True):
    __tablename__ = "consumption_log"
    __table_args__ = (
        sa.CheckConstraint(
            "action IN ('receive','consume','transfer','adjust','dispose','open')",
            name="ck_consumption_log_action",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    inventory_id: int = Field(
        sa_column=Column(
            sa.Integer,
            sa.ForeignKey("inventory.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
    )
    product_id: int | None = Field(
        default=None,
        sa_column=Column(sa.Integer, sa.ForeignKey("products.id", ondelete="SET NULL"), index=True),
    )
    quantity_used: Decimal = Field(sa_column=Column(sa.Numeric(12, 4), nullable=False))
    quantity_remaining: Decimal = Field(sa_column=Column(sa.Numeric(12, 4), nullable=False))
    consumed_by: str = Field(max_length=200)
    purpose: str | None = Field(default=None, max_length=500)
    action: str = Field(max_length=30)

    inventory_item: Optional["InventoryItem"] = Relationship(back_populates="consumption_logs")
    product: Optional["Product"] = Relationship(back_populates="consumption_logs")
