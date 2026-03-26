"""Add RBAC role check constraint with manager and viewer roles.

Revision ID: a2b3c4d5e6f7
Revises: f6a7b8c9d0e1
Create Date: 2026-03-26
"""

from alembic import op

revision = "a2b3c4d5e6f7"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_staff_role", "staff", type_="check")
    op.create_check_constraint(
        "ck_staff_role",
        "staff",
        "role IN ('admin','manager','member','viewer')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_staff_role", "staff", type_="check")
    op.create_check_constraint(
        "ck_staff_role",
        "staff",
        "role IN ('admin','member')",
    )
