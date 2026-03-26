"""Supply request and approval model."""

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy import Column
from sqlmodel import Field, Relationship

from lab_manager.models.base import AuditMixin

if TYPE_CHECKING:
    from lab_manager.models.order import Order
    from lab_manager.models.product import Product
    from lab_manager.models.staff import Staff
    from lab_manager.models.vendor import Vendor


class RequestUrgency(str, enum.Enum):
    normal = "normal"
    urgent = "urgent"


class RequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class OrderRequest(AuditMixin, table=True):
    __tablename__ = "order_requests"
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','cancelled')",
            name="ck_order_requests_status",
        ),
        sa.CheckConstraint(
            "urgency IN ('normal','urgent')",
            name="ck_order_requests_urgency",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    requested_by: int = Field(
        sa_column=Column(
            sa.Integer,
            sa.ForeignKey("staff.id", ondelete="RESTRICT"),
            index=True,
            nullable=False,
        ),
    )

    product_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            sa.Integer,
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            index=True,
        ),
    )

    vendor_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            sa.Integer,
            sa.ForeignKey("vendors.id", ondelete="SET NULL"),
            index=True,
        ),
    )

    catalog_number: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)
    quantity: Decimal = Field(default=1, sa_column=Column(sa.Numeric(12, 4), default=1))
    unit: Optional[str] = Field(default=None, max_length=50)
    estimated_price: Optional[Decimal] = Field(
        default=None, sa_column=Column(sa.Numeric(12, 4), nullable=True)
    )
    justification: Optional[str] = Field(default=None, max_length=2000)
    urgency: str = Field(default="normal", max_length=20)
    status: str = Field(default="pending", max_length=20, index=True)

    reviewed_by: Optional[int] = Field(
        default=None,
        sa_column=Column(
            sa.Integer,
            sa.ForeignKey("staff.id", ondelete="SET NULL"),
            index=True,
        ),
    )

    review_note: Optional[str] = Field(default=None, max_length=2000)

    order_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            sa.Integer,
            sa.ForeignKey("orders.id", ondelete="SET NULL"),
            index=True,
        ),
    )

    reviewed_at: Optional[datetime] = Field(default=None)

    # Relationships
    requester: Optional["Staff"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[OrderRequest.requested_by]"},
    )
    reviewer: Optional["Staff"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[OrderRequest.reviewed_by]"},
    )
    product: Optional["Product"] = Relationship()
    vendor: Optional["Vendor"] = Relationship()
    order: Optional["Order"] = Relationship()
