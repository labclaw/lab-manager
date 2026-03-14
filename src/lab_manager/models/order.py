"""Order and order line item models."""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlmodel import Field, Column
from sqlalchemy import JSON

from lab_manager.models.base import AuditMixin


class Order(AuditMixin, table=True):
    __tablename__ = "orders"

    id: Optional[int] = Field(default=None, primary_key=True)
    po_number: Optional[str] = Field(default=None, max_length=100, index=True)
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendors.id", index=True)
    order_date: Optional[date] = Field(default=None)
    ship_date: Optional[date] = Field(default=None)
    received_date: Optional[date] = Field(default=None)
    received_by: Optional[str] = Field(default=None, max_length=200)
    status: str = Field(default="pending", max_length=30, index=True)
    delivery_number: Optional[str] = Field(default=None, max_length=100)
    invoice_number: Optional[str] = Field(default=None, max_length=100)
    document_id: Optional[int] = Field(default=None, foreign_key="documents.id")
    extra: dict = Field(default_factory=dict, sa_column=Column(JSON))


class OrderItem(AuditMixin, table=True):
    __tablename__ = "order_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    catalog_number: Optional[str] = Field(default=None, max_length=100, index=True)
    description: Optional[str] = Field(default=None, max_length=1000)
    quantity: float = Field(default=1)
    unit: Optional[str] = Field(default=None, max_length=50)
    lot_number: Optional[str] = Field(default=None, max_length=100, index=True)
    batch_number: Optional[str] = Field(default=None, max_length=100)
    unit_price: Optional[float] = Field(default=None)
    product_id: Optional[int] = Field(default=None, foreign_key="products.id")
    extra: dict = Field(default_factory=dict, sa_column=Column(JSON))
