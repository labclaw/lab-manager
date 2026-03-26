"""Vendor / supplier model."""

from typing import TYPE_CHECKING, List, Optional

import sqlalchemy as sa
from sqlalchemy import Column
from sqlmodel import Field, Relationship

from lab_manager.models.base import AuditMixin

if TYPE_CHECKING:
    from lab_manager.models.order import Order
    from lab_manager.models.product import Product


class Vendor(AuditMixin, table=True):
    __tablename__ = "vendors"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, unique=True)
    aliases: list[str] = Field(
        default_factory=list, sa_column=Column(sa.dialects.postgresql.JSONB)
    )
    website: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None)

    products: List["Product"] = Relationship(back_populates="vendor")
    orders: List["Order"] = Relationship(back_populates="vendor")
