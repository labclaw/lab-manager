"""Product / catalog item model."""

from decimal import Decimal  # noqa: F401 — used in Field type annotations
from typing import TYPE_CHECKING, List, Optional

import sqlalchemy as sa
from sqlalchemy import JSON, Column  # noqa: F401
from sqlalchemy.dialects.postgresql import JSONB as _JSONB  # noqa: F401
from sqlmodel import Field, Relationship

from lab_manager.models.base import AuditMixin

if TYPE_CHECKING:
    from lab_manager.models.consumption import ConsumptionLog
    from lab_manager.models.inventory import InventoryItem
    from lab_manager.models.order import OrderItem
    from lab_manager.models.vendor import Vendor


class Product(AuditMixin, table=True):
    __tablename__ = "products"
    __table_args__ = (
        sa.UniqueConstraint(
            "catalog_number", "vendor_id", name="uq_product_catalog_vendor"
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    catalog_number: str = Field(max_length=100, index=True)
    name: str = Field(max_length=500)
    vendor_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            sa.Integer, sa.ForeignKey("vendors.id", ondelete="RESTRICT"), index=True
        ),
    )
    category: Optional[str] = Field(default=None, max_length=100, index=True)
    cas_number: Optional[str] = Field(default=None, max_length=30)
    molecular_weight: Optional[float] = Field(default=None)
    molecular_formula: Optional[str] = Field(default=None, max_length=200)
    smiles: Optional[str] = Field(default=None, max_length=2000)
    pubchem_cid: Optional[int] = Field(default=None, index=True)
    storage_temp: Optional[str] = Field(default=None, max_length=50)
    unit: Optional[str] = Field(default=None, max_length=50)
    hazard_info: Optional[str] = Field(default=None, max_length=255)
    extra: dict = Field(
        default_factory=dict, sa_column=Column(_JSONB().with_variant(JSON, "sqlite"))
    )

    min_stock_level: Optional[Decimal] = Field(
        default=None, sa_column=Column(sa.Numeric(12, 4), nullable=True)
    )
    max_stock_level: Optional[Decimal] = Field(
        default=None, sa_column=Column(sa.Numeric(12, 4), nullable=True)
    )
    reorder_quantity: Optional[Decimal] = Field(
        default=None, sa_column=Column(sa.Numeric(12, 4), nullable=True)
    )
    shelf_life_days: Optional[int] = Field(default=None)
    storage_requirements: Optional[str] = Field(default=None, max_length=500)
    is_hazardous: bool = Field(default=False)
    is_controlled: bool = Field(default=False)
    is_active: bool = Field(default=True)

    # MSDS / safety data
    hazard_class: Optional[str] = Field(default=None, max_length=100)
    msds_url: Optional[str] = Field(default=None, max_length=500)
    requires_safety_review: bool = Field(default=False)

    vendor: Optional["Vendor"] = Relationship(back_populates="products")
    order_items: List["OrderItem"] = Relationship(back_populates="product")
    inventory_items: List["InventoryItem"] = Relationship(back_populates="product")
    consumption_logs: List["ConsumptionLog"] = Relationship(back_populates="product")
