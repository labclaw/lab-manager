"""add digital staff fields to staff model

Revision ID: d1e2f3a4b5c6
Revises: 0c2125df7c3a
Create Date: 2026-03-27 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "0c2125df7c3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "staff",
        sa.Column(
            "staff_type",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
            server_default="human",
        ),
    )
    op.add_column(
        "staff",
        sa.Column("agent_config", sa.JSON(), nullable=True),
    )
    op.add_column(
        "staff",
        sa.Column(
            "avatar_emoji",
            sqlmodel.sql.sqltypes.AutoString(length=10),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("staff", "avatar_emoji")
    op.drop_column("staff", "agent_config")
    op.drop_column("staff", "staff_type")
