"""fix_decimal_relationships_enums

Revision ID: c3f8a1b2d4e5
Revises: aa12d2df8f01
Create Date: 2026-03-14 20:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "c3f8a1b2d4e5"
down_revision: Union[str, None] = "aa12d2df8f01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- float -> Numeric(12,4) for monetary/quantity columns --
    op.alter_column(
        "order_items",
        "quantity",
        type_=sa.Numeric(12, 4),
        existing_type=sa.Float(),
        existing_nullable=True,
    )
    op.alter_column(
        "order_items",
        "unit_price",
        type_=sa.Numeric(12, 4),
        existing_type=sa.Float(),
        existing_nullable=True,
    )
    op.alter_column(
        "inventory",
        "quantity_on_hand",
        type_=sa.Numeric(12, 4),
        existing_type=sa.Float(),
        existing_nullable=True,
    )
    op.alter_column(
        "consumption_log",
        "quantity_used",
        type_=sa.Numeric(12, 4),
        existing_type=sa.Float(),
        existing_nullable=False,
    )
    op.alter_column(
        "consumption_log",
        "quantity_remaining",
        type_=sa.Numeric(12, 4),
        existing_type=sa.Float(),
        existing_nullable=False,
    )

    # -- JSON -> JSONB for audit_log --
    op.alter_column(
        "audit_log",
        "changes",
        type_=JSONB(),
        existing_type=sa.JSON(),
        existing_nullable=True,
        postgresql_using="changes::jsonb",
    )

    # -- server_default for timestamps --
    op.alter_column(
        "vendors",
        "created_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "vendors",
        "updated_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "products",
        "created_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "products",
        "updated_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "orders",
        "created_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "orders",
        "updated_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "order_items",
        "created_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "order_items",
        "updated_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "inventory",
        "created_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "inventory",
        "updated_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "documents",
        "created_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "documents",
        "updated_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "consumption_log",
        "created_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "consumption_log",
        "updated_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "alerts",
        "created_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "alerts",
        "updated_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "staff",
        "created_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "staff",
        "updated_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "locations",
        "created_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )
    op.alter_column(
        "locations",
        "updated_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(),
    )

    # -- ON DELETE for foreign keys --
    # Products.vendor_id -> RESTRICT
    op.drop_constraint("products_vendor_id_fkey", "products", type_="foreignkey")
    op.create_foreign_key(
        "products_vendor_id_fkey",
        "products",
        "vendors",
        ["vendor_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # Orders.vendor_id -> RESTRICT
    op.drop_constraint("orders_vendor_id_fkey", "orders", type_="foreignkey")
    op.create_foreign_key(
        "orders_vendor_id_fkey",
        "orders",
        "vendors",
        ["vendor_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # Orders.document_id -> SET NULL
    op.drop_constraint("orders_document_id_fkey", "orders", type_="foreignkey")
    op.create_foreign_key(
        "orders_document_id_fkey",
        "orders",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # OrderItems.order_id -> CASCADE
    op.drop_constraint("order_items_order_id_fkey", "order_items", type_="foreignkey")
    op.create_foreign_key(
        "order_items_order_id_fkey",
        "order_items",
        "orders",
        ["order_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # OrderItems.product_id -> SET NULL
    op.drop_constraint("order_items_product_id_fkey", "order_items", type_="foreignkey")
    op.create_foreign_key(
        "order_items_product_id_fkey",
        "order_items",
        "products",
        ["product_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Inventory.product_id -> RESTRICT
    op.drop_constraint("inventory_product_id_fkey", "inventory", type_="foreignkey")
    op.create_foreign_key(
        "inventory_product_id_fkey",
        "inventory",
        "products",
        ["product_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # Inventory.location_id -> SET NULL
    op.drop_constraint("inventory_location_id_fkey", "inventory", type_="foreignkey")
    op.create_foreign_key(
        "inventory_location_id_fkey",
        "inventory",
        "locations",
        ["location_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Inventory.order_item_id -> SET NULL
    op.drop_constraint("inventory_order_item_id_fkey", "inventory", type_="foreignkey")
    op.create_foreign_key(
        "inventory_order_item_id_fkey",
        "inventory",
        "order_items",
        ["order_item_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ConsumptionLog.inventory_id -> CASCADE
    op.drop_constraint(
        "consumption_log_inventory_id_fkey", "consumption_log", type_="foreignkey"
    )
    op.create_foreign_key(
        "consumption_log_inventory_id_fkey",
        "consumption_log",
        "inventory",
        ["inventory_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ConsumptionLog.product_id -> SET NULL
    op.drop_constraint(
        "consumption_log_product_id_fkey", "consumption_log", type_="foreignkey"
    )
    op.create_foreign_key(
        "consumption_log_product_id_fkey",
        "consumption_log",
        "products",
        ["product_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # -- Check constraints for status/type/action enums --
    op.create_check_constraint(
        "ck_orders_status",
        "orders",
        "status IN ('pending','shipped','received','cancelled','deleted')",
    )
    op.create_check_constraint(
        "ck_inventory_status",
        "inventory",
        "status IN ('available','opened','depleted','disposed','expired','deleted')",
    )
    op.create_check_constraint(
        "ck_documents_status",
        "documents",
        "status IN ('pending','extracted','needs_review','approved','rejected','deleted')",
    )
    op.create_check_constraint(
        "ck_consumption_log_action",
        "consumption_log",
        "action IN ('receive','consume','transfer','adjust','dispose','open')",
    )
    op.create_check_constraint(
        "ck_alerts_alert_type",
        "alerts",
        "alert_type IN ('expired','expiring_soon','out_of_stock','low_stock','pending_review','stale_orders')",
    )
    op.create_check_constraint(
        "ck_alerts_severity",
        "alerts",
        "severity IN ('critical','warning','info')",
    )


def downgrade() -> None:
    # -- Drop check constraints --
    op.drop_constraint("ck_alerts_severity", "alerts", type_="check")
    op.drop_constraint("ck_alerts_alert_type", "alerts", type_="check")
    op.drop_constraint("ck_consumption_log_action", "consumption_log", type_="check")
    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.drop_constraint("ck_inventory_status", "inventory", type_="check")
    op.drop_constraint("ck_orders_status", "orders", type_="check")

    # -- Revert FK ondelete to default --
    op.drop_constraint(
        "consumption_log_product_id_fkey", "consumption_log", type_="foreignkey"
    )
    op.create_foreign_key(
        "consumption_log_product_id_fkey",
        "consumption_log",
        "products",
        ["product_id"],
        ["id"],
    )
    op.drop_constraint(
        "consumption_log_inventory_id_fkey", "consumption_log", type_="foreignkey"
    )
    op.create_foreign_key(
        "consumption_log_inventory_id_fkey",
        "consumption_log",
        "inventory",
        ["inventory_id"],
        ["id"],
    )
    op.drop_constraint("inventory_order_item_id_fkey", "inventory", type_="foreignkey")
    op.create_foreign_key(
        "inventory_order_item_id_fkey",
        "inventory",
        "order_items",
        ["order_item_id"],
        ["id"],
    )
    op.drop_constraint("inventory_location_id_fkey", "inventory", type_="foreignkey")
    op.create_foreign_key(
        "inventory_location_id_fkey",
        "inventory",
        "locations",
        ["location_id"],
        ["id"],
    )
    op.drop_constraint("inventory_product_id_fkey", "inventory", type_="foreignkey")
    op.create_foreign_key(
        "inventory_product_id_fkey",
        "inventory",
        "products",
        ["product_id"],
        ["id"],
    )
    op.drop_constraint("order_items_product_id_fkey", "order_items", type_="foreignkey")
    op.create_foreign_key(
        "order_items_product_id_fkey",
        "order_items",
        "products",
        ["product_id"],
        ["id"],
    )
    op.drop_constraint("order_items_order_id_fkey", "order_items", type_="foreignkey")
    op.create_foreign_key(
        "order_items_order_id_fkey",
        "order_items",
        "orders",
        ["order_id"],
        ["id"],
    )
    op.drop_constraint("orders_document_id_fkey", "orders", type_="foreignkey")
    op.create_foreign_key(
        "orders_document_id_fkey",
        "orders",
        "documents",
        ["document_id"],
        ["id"],
    )
    op.drop_constraint("orders_vendor_id_fkey", "orders", type_="foreignkey")
    op.create_foreign_key(
        "orders_vendor_id_fkey",
        "orders",
        "vendors",
        ["vendor_id"],
        ["id"],
    )
    op.drop_constraint("products_vendor_id_fkey", "products", type_="foreignkey")
    op.create_foreign_key(
        "products_vendor_id_fkey",
        "products",
        "vendors",
        ["vendor_id"],
        ["id"],
    )

    # -- Revert server_default (remove) --
    for table in [
        "vendors",
        "products",
        "orders",
        "order_items",
        "inventory",
        "documents",
        "consumption_log",
        "alerts",
        "staff",
        "locations",
    ]:
        op.alter_column(
            table, "created_at", server_default=None, existing_type=sa.DateTime()
        )
        op.alter_column(
            table, "updated_at", server_default=None, existing_type=sa.DateTime()
        )

    # -- Revert JSONB -> JSON --
    op.alter_column(
        "audit_log",
        "changes",
        type_=sa.JSON(),
        existing_type=JSONB(),
        existing_nullable=True,
    )

    # -- Revert Numeric -> Float --
    op.alter_column(
        "consumption_log",
        "quantity_remaining",
        type_=sa.Float(),
        existing_type=sa.Numeric(12, 4),
        existing_nullable=False,
    )
    op.alter_column(
        "consumption_log",
        "quantity_used",
        type_=sa.Float(),
        existing_type=sa.Numeric(12, 4),
        existing_nullable=False,
    )
    op.alter_column(
        "inventory",
        "quantity_on_hand",
        type_=sa.Float(),
        existing_type=sa.Numeric(12, 4),
        existing_nullable=True,
    )
    op.alter_column(
        "order_items",
        "unit_price",
        type_=sa.Float(),
        existing_type=sa.Numeric(12, 4),
        existing_nullable=True,
    )
    op.alter_column(
        "order_items",
        "quantity",
        type_=sa.Float(),
        existing_type=sa.Numeric(12, 4),
        existing_nullable=True,
    )
