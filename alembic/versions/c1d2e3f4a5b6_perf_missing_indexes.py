"""perf: add missing composite indexes for audit, inventory, orders, alerts

Merge heads b7c9d0e1f2a3 and f1a2b3c4d5e6, then add performance indexes
identified in review:

- audit_log(timestamp) — ORDER BY in audit queries
- audit_log(table_name, record_id) — composite for record history lookups
- inventory(status, product_id) — composite for active inventory queries
- orders(status, created_at) — composite for order listing with status filter
- orders(order_date) — model declares index=True but no migration creates it
- alerts(entity_type, entity_id) — model __table_args__ declares it but no migration

Revision ID: c1d2e3f4a5b6
Revises: b7c9d0e1f2a3, f1a2b3c4d5e6
Create Date: 2026-03-20 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str]] = ("b7c9d0e1f2a3", "f1a2b3c4d5e6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = [
    # audit_log: timestamp for ORDER BY
    ("ix_audit_log_timestamp", "audit_log", ["timestamp"]),
    # audit_log: composite for record history lookups
    ("ix_audit_log_table_record", "audit_log", ["table_name", "record_id"]),
    # inventory: composite for active inventory queries (status + product_id)
    ("ix_inventory_status_product", "inventory", ["status", "product_id"]),
    # orders: composite for order listing with status filter
    ("ix_orders_status_created_at", "orders", ["status", "created_at"]),
    # orders: order_date — model declares index=True but no migration creates it
    ("ix_orders_order_date", "orders", ["order_date"]),
    # alerts: composite for entity lookups (model __table_args__ declares it)
    ("ix_alert_entity", "alerts", ["entity_type", "entity_id"]),
]


def upgrade() -> None:
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns, if_not_exists=True)


def downgrade() -> None:
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table, if_exists=True)
