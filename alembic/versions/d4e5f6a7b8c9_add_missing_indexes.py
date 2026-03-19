"""add_missing_indexes

Revision ID: d4e5f6a7b8c9
Revises: c3f8a1b2d4e5
Create Date: 2026-03-14 22:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3f8a1b2d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES = [
    ("ix_orders_document_id", "orders", ["document_id"]),
    ("ix_orders_vendor_id", "orders", ["vendor_id"]),
    ("ix_inventory_status", "inventory", ["status"]),
    ("ix_inventory_product_id", "inventory", ["product_id"]),
    ("ix_inventory_order_item_id", "inventory", ["order_item_id"]),
    ("ix_order_items_order_id", "order_items", ["order_id"]),
    ("ix_order_items_product_id", "order_items", ["product_id"]),
]


def upgrade() -> None:
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns, if_not_exists=True)


def downgrade() -> None:
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table, if_exists=True)
