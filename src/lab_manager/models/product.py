"""Product / catalog item model."""

from decimal import Decimal  # noqa: F401 — used in Field type annotations
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy import Column
from sqlmodel import Field, Relationship

from lab_manager.models.base import AuditMixin

if TYPE_CHECKING:
    from lab_manager.models.consumption import ConsumptionLog
    from lab_manager.models.inventory import InventoryItem
    from lab_manager.models.order import OrderItem
    from lab_manager.models.vendor import Vendor


class Product(AuditMixin, table=True):
    __tablename__ = "products"
    __table_args__ = (sa.UniqueConstraint("catalog_number", "vendor_id", name="uq_product_catalog_vendor"),)

    id: int | None = Field(default=None, primary_key=True)
    catalog_number: str = Field(max_length=100, index=True)
    name: str = Field(max_length=500)
    vendor_id: int | None = Field(
        default=None,
        sa_column=Column(sa.Integer, sa.ForeignKey("vendors.id", ondelete="RESTRICT"), index=True),
    )
    category: str | None = Field(default=None, max_length=100, index=True)
    cas_number: str | None = Field(default=None, max_length=30)
    storage_temp: str | None = Field(default=None, max_length=50)
    unit: str | None = Field(default=None, max_length=50)
    hazard_info: str | None = Field(default=None, max_length=255)
    extra: dict = Field(default_factory=dict, sa_column=Column(sa.JSON))

    min_stock_level: Decimal | None = Field(default=None, sa_column=Column(sa.Numeric(12, 4), nullable=True))
    max_stock_level: Decimal | None = Field(default=None, sa_column=Column(sa.Numeric(12, 4), nullable=True))
    reorder_quantity: Decimal | None = Field(default=None, sa_column=Column(sa.Numeric(12, 4), nullable=True))
    shelf_life_days: int | None = Field(default=None)
    storage_requirements: str | None = Field(default=None, max_length=500)
    is_hazardous: bool = Field(default=False)
    is_controlled: bool = Field(default=False)
    is_active: bool = Field(default=True)

    vendor: Optional["Vendor"] = Relationship(back_populates="products")
    order_items: list["OrderItem"] = Relationship(back_populates="product")
    inventory_items: list["InventoryItem"] = Relationship(back_populates="product")
    consumption_logs: list["ConsumptionLog"] = Relationship(back_populates="product")
