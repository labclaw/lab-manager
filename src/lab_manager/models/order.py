"""Order and order line item models."""

import enum
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

import sqlalchemy as sa
from sqlalchemy import Column
from sqlmodel import Field, Relationship

from lab_manager.models.base import AuditMixin

if TYPE_CHECKING:
    from lab_manager.models.document import Document
    from lab_manager.models.inventory import InventoryItem
    from lab_manager.models.product import Product
    from lab_manager.models.vendor import Vendor


class OrderStatus(str, enum.Enum):
    pending = "pending"
    shipped = "shipped"
    received = "received"
    cancelled = "cancelled"
    deleted = "deleted"


class Order(AuditMixin, table=True):
    __tablename__ = "orders"
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('pending','shipped','received','cancelled','deleted')",
            name="ck_orders_status",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    po_number: Optional[str] = Field(default=None, max_length=100, index=True)
    vendor_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            sa.Integer, sa.ForeignKey("vendors.id", ondelete="RESTRICT"), index=True
        ),
    )
    order_date: Optional[date] = Field(default=None, index=True)
    ship_date: Optional[date] = Field(default=None)
    received_date: Optional[date] = Field(default=None)
    received_by: Optional[str] = Field(default=None, max_length=200)
    status: str = Field(default="pending", max_length=30, index=True)
    delivery_number: Optional[str] = Field(default=None, max_length=100)
    invoice_number: Optional[str] = Field(default=None, max_length=100)
    document_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            sa.Integer, sa.ForeignKey("documents.id", ondelete="SET NULL"), index=True
        ),
    )
    extra: dict = Field(default_factory=dict, sa_column=Column(sa.JSON))

    vendor: Optional["Vendor"] = Relationship(back_populates="orders")
    items: List["OrderItem"] = Relationship(back_populates="order")
    document: Optional["Document"] = Relationship(back_populates="orders")


class OrderItem(AuditMixin, table=True):
    __tablename__ = "order_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(
        sa_column=Column(
            sa.Integer,
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
    )
    catalog_number: Optional[str] = Field(default=None, max_length=100, index=True)
    description: Optional[str] = Field(default=None, max_length=1000)
    quantity: Decimal = Field(default=1, sa_column=Column(sa.Numeric(12, 4), default=1))
    unit: Optional[str] = Field(default=None, max_length=50)
    lot_number: Optional[str] = Field(default=None, max_length=100, index=True)
    batch_number: Optional[str] = Field(default=None, max_length=100)
    unit_price: Optional[Decimal] = Field(
        default=None, sa_column=Column(sa.Numeric(12, 4), nullable=True)
    )
    product_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            sa.Integer, sa.ForeignKey("products.id", ondelete="SET NULL"), index=True
        ),
    )
    extra: dict = Field(default_factory=dict, sa_column=Column(sa.JSON))

    order: Optional["Order"] = Relationship(back_populates="items")
    product: Optional["Product"] = Relationship(back_populates="order_items")
    inventory_items: List["InventoryItem"] = Relationship(back_populates="order_item")
