"""Inventory stock model."""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlmodel import Field

from lab_manager.models.base import AuditMixin


class InventoryItem(AuditMixin, table=True):
    __tablename__ = "inventory"

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: Optional[int] = Field(
        default=None, foreign_key="products.id", index=True
    )
    location_id: Optional[int] = Field(
        default=None, foreign_key="locations.id", index=True
    )
    lot_number: Optional[str] = Field(default=None, max_length=100)
    quantity_on_hand: float = Field(default=0)
    unit: Optional[str] = Field(default=None, max_length=50)
    expiry_date: Optional[date] = Field(default=None, index=True)
    opened_date: Optional[date] = Field(default=None)
    status: str = Field(default="available", max_length=30)
    notes: Optional[str] = Field(default=None)
    received_by: Optional[str] = Field(default=None, max_length=200)
    order_item_id: Optional[int] = Field(default=None, foreign_key="order_items.id")
