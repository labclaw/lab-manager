"""Add RBAC role check, location hierarchy (parent_id, level, path).

Revision ID: a2b3c4d5e6f7
Revises: f6a7b8c9d0e1
Create Date: 2026-03-26
"""

from alembic import op
import sqlalchemy as sa

revision = "a2b3c4d5e6f7"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- Staff: update role check constraint to enforce enum --
    op.drop_constraint("ck_staff_role", "staff", type_="check")
    op.create_check_constraint(
        "ck_staff_role",
        "staff",
        "role IN ('admin','manager','member','viewer')",
    )

    # -- Locations: add hierarchy columns --
    op.add_column("locations", sa.Column("parent_id", sa.Integer(), nullable=True))
    op.add_column(
        "locations", sa.Column("level", sa.String(50), server_default="room", nullable=False)
    )
    op.add_column("locations", sa.Column("path", sa.String(1000), nullable=True))

    op.create_foreign_key(
        "fk_locations_parent_id",
        "locations",
        "locations",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_locations_parent_id", "locations", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_locations_parent_id", table_name="locations")
    op.drop_constraint("fk_locations_parent_id", "locations", type_="foreignkey")
    op.drop_column("locations", "path")
    op.drop_column("locations", "level")
    op.drop_column("locations", "parent_id")

    op.drop_constraint("ck_staff_role", "staff", type_="check")
    op.create_check_constraint(
        "ck_staff_role",
        "staff",
        "role IN ('admin','member')",
    )
