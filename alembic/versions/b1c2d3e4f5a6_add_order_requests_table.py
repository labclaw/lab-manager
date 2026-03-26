"""add order_requests table

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-03-25 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "order_requests",
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("vendor_id", sa.Integer(), nullable=True),
        sa.Column("catalog_number", sa.String(length=100), nullable=True),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 4), server_default="1", nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("estimated_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("justification", sa.String(length=2000), nullable=True),
        sa.Column(
            "urgency", sa.String(length=20), server_default="normal", nullable=True
        ),
        sa.Column(
            "status", sa.String(length=20), server_default="pending", nullable=True
        ),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("review_note", sa.String(length=2000), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["requested_by"], ["staff.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["staff.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','cancelled')",
            name="ck_order_requests_status",
        ),
        sa.CheckConstraint(
            "urgency IN ('normal','urgent')",
            name="ck_order_requests_urgency",
        ),
    )
    op.create_index(
        "ix_order_requests_requested_by", "order_requests", ["requested_by"]
    )
    op.create_index("ix_order_requests_status", "order_requests", ["status"])
    op.create_index("ix_order_requests_product_id", "order_requests", ["product_id"])
    op.create_index("ix_order_requests_vendor_id", "order_requests", ["vendor_id"])
    op.create_index("ix_order_requests_reviewed_by", "order_requests", ["reviewed_by"])
    op.create_index("ix_order_requests_order_id", "order_requests", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_order_requests_order_id", table_name="order_requests")
    op.drop_index("ix_order_requests_reviewed_by", table_name="order_requests")
    op.drop_index("ix_order_requests_vendor_id", table_name="order_requests")
    op.drop_index("ix_order_requests_product_id", table_name="order_requests")
    op.drop_index("ix_order_requests_status", table_name="order_requests")
    op.drop_index("ix_order_requests_requested_by", table_name="order_requests")
    op.drop_table("order_requests")
