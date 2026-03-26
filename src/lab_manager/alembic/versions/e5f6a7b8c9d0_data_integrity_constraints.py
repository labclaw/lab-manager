"""data_integrity_constraints

Adds:
- Product (catalog_number, vendor_id) unique constraint
- Product min/max_stock_level, reorder_quantity: float -> Numeric(12,4)
- Product extra: JSON -> JSONB
- Product is_active column (default True)
- Inventory product_id NOT NULL (fixes orphan rows with _ORPHAN placeholder)
- Inventory quantity_on_hand >= 0 CHECK
- Vendor aliases: JSON -> JSONB

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-16 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Product unique constraint — check for duplicates first
    dupes = conn.execute(
        sa.text(
            "SELECT catalog_number, vendor_id, COUNT(*) AS cnt "
            "FROM products GROUP BY catalog_number, vendor_id HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if dupes:
        for row in dupes:
            cat, vid, _cnt = row
            ids = conn.execute(
                sa.text(
                    "SELECT id FROM products WHERE catalog_number = :cat "
                    "AND vendor_id IS NOT DISTINCT FROM :vid ORDER BY id"
                ),
                {"cat": cat, "vid": vid},
            ).fetchall()
            keep_id = ids[0][0]
            for dup_row in ids[1:]:
                dup_id = dup_row[0]
                # Reassign order_items and inventory to the kept product
                conn.execute(
                    sa.text(
                        "UPDATE order_items SET product_id = :keep WHERE product_id = :dup"
                    ),
                    {"keep": keep_id, "dup": dup_id},
                )
                conn.execute(
                    sa.text(
                        "UPDATE inventory SET product_id = :keep WHERE product_id = :dup"
                    ),
                    {"keep": keep_id, "dup": dup_id},
                )
                conn.execute(
                    sa.text("DELETE FROM products WHERE id = :dup"),
                    {"dup": dup_id},
                )

    op.create_unique_constraint(
        "uq_product_catalog_vendor", "products", ["catalog_number", "vendor_id"]
    )

    # 2. Product stock levels: float -> Numeric(12,4)
    op.alter_column(
        "products",
        "min_stock_level",
        type_=sa.Numeric(12, 4),
        existing_type=sa.Float,
    )
    op.alter_column(
        "products",
        "max_stock_level",
        type_=sa.Numeric(12, 4),
        existing_type=sa.Float,
    )
    op.alter_column(
        "products",
        "reorder_quantity",
        type_=sa.Numeric(12, 4),
        existing_type=sa.Float,
    )

    # 3. Inventory: product_id NOT NULL (fix orphan rows first)
    orphan_count = conn.execute(
        sa.text("SELECT COUNT(*) FROM inventory WHERE product_id IS NULL")
    ).scalar()
    if orphan_count > 0:
        # Create placeholder product for orphans
        conn.execute(
            sa.text(
                "INSERT INTO products (catalog_number, name, created_at, updated_at) "
                "VALUES ('_ORPHAN', 'Unknown Product (migration orphan)', NOW(), NOW())"
            )
        )
        placeholder_id = conn.execute(
            sa.text("SELECT id FROM products WHERE catalog_number = '_ORPHAN'")
        ).scalar()
        conn.execute(
            sa.text("UPDATE inventory SET product_id = :pid WHERE product_id IS NULL"),
            {"pid": placeholder_id},
        )

    op.alter_column("inventory", "product_id", nullable=False, existing_type=sa.Integer)

    # 4. Inventory: quantity >= 0 CHECK (fix existing negatives first)
    conn.execute(
        sa.text("UPDATE inventory SET quantity_on_hand = 0 WHERE quantity_on_hand < 0")
    )
    op.create_check_constraint(
        "ck_inventory_qty_nonneg", "inventory", "quantity_on_hand >= 0"
    )

    # 5. Vendor aliases: JSON -> JSONB
    op.execute(
        "ALTER TABLE vendors ALTER COLUMN aliases TYPE JSONB USING aliases::jsonb"
    )

    # 6. Product extra: JSON -> JSONB
    op.execute("ALTER TABLE products ALTER COLUMN extra TYPE JSONB USING extra::jsonb")

    # 7. Product is_active column
    op.add_column(
        "products",
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("products", "is_active")
    op.execute("ALTER TABLE products ALTER COLUMN extra TYPE JSON USING extra::json")
    op.execute("ALTER TABLE vendors ALTER COLUMN aliases TYPE JSON USING aliases::json")
    op.drop_constraint("ck_inventory_qty_nonneg", "inventory", type_="check")
    op.alter_column("inventory", "product_id", nullable=True, existing_type=sa.Integer)
    op.alter_column(
        "products",
        "reorder_quantity",
        type_=sa.Float,
        existing_type=sa.Numeric(12, 4),
    )
    op.alter_column(
        "products",
        "max_stock_level",
        type_=sa.Float,
        existing_type=sa.Numeric(12, 4),
    )
    op.alter_column(
        "products",
        "min_stock_level",
        type_=sa.Float,
        existing_type=sa.Numeric(12, 4),
    )
    op.drop_constraint("uq_product_catalog_vendor", "products", type_="unique")
