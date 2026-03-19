"""Vendor / supplier model."""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Column
from sqlmodel import Field, Relationship

from lab_manager.models.base import AuditMixin

if TYPE_CHECKING:
    from lab_manager.models.order import Order
    from lab_manager.models.product import Product


class Vendor(AuditMixin, table=True):
    __tablename__ = "vendors"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, index=True, unique=True)
    aliases: list[str] = Field(default_factory=list, sa_column=Column(sa.JSON))
    website: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None)

    products: list["Product"] = Relationship(back_populates="vendor")
    orders: list["Order"] = Relationship(back_populates="vendor")
