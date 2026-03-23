"""add non-negative CHECK for equipment.estimated_value

Revision ID: 9b2c4d6e8f10
Revises: 15e78dfeed79
Create Date: 2026-03-23 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "9b2c4d6e8f10"
down_revision: Union[str, None] = "15e78dfeed79"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE equipment SET estimated_value = 0 WHERE estimated_value < 0")
    )
    op.create_check_constraint(
        "ck_equipment_estimated_value_nonneg",
        "equipment",
        "estimated_value IS NULL OR estimated_value >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_equipment_estimated_value_nonneg",
        "equipment",
        type_="check",
    )
