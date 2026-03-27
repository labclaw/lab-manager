"""merge heads for reservation

Revision ID: 0c2125df7c3a
Revises: 15e78dfeed79, a1b2c3d4e5f6, 656b400b42d2, d1e2f3a4e5f6a7b8c9d0e1f2a3, b1c2d3e4f5a6, d4e5f6a7b8c9, b7c9d0e1f2a3, 9b2c4d6e8f10, c1d2e3f4a5b6, 4ecede3a6f58, d0e1f2a3b4c5, aa12d2df8f01, a0b1c2d3e4f5, c3f8a1b2d4e5, e5f6a7b8c9d0
Create Date: 2026-03-27

"""

from typing import Sequence, Union

from alembic import op

import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0c2125df7c3a"
down_revision: Union[str, None] = (
    "15e78dfeed79",
    "a1b2c3d4e5f6",
    "656b400b42d2",
    "d1e2f3a4e5f6a7b8c9d0e1f2a3",
    "b1c2d3e4f5a6",
    "d4e5f6a7b8c9",
    "b7c9d0e1f2a3",
    "9b2c4d6e8f10",
    "c1d2e3f4a5b6",
    "4ecede3a6f58",
    "d0e1f2a3b4c5",
    "aa12d2df8f01",
    "a0b1c2d3e4f5",
    "c3f8a1b2d4e5",
    "e5f6a7b8c9d0",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reservation",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "equipment_id", sa.Integer, sa.ForeignKey("equipment.id"), nullable=False
        ),
        sa.Column("staff_id", sa.Integer, sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("purpose", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), server_default="confirmed"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("created_by", sa.String(100), nullable=True),
    )
    op.create_index("ix_reservation_equipment_id", "reservation", ["equipment_id"])
    op.create_index("ix_reservation_start_time", "reservation", ["start_time"])


def downgrade() -> None:
    op.drop_table("reservation")
