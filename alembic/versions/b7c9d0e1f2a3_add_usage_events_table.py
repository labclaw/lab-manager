"""add usage_events table

Revision ID: b7c9d0e1f2a3
Revises: 4ecede3a6f58
Create Date: 2026-03-19 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = "b7c9d0e1f2a3"
down_revision: Union[str, None] = "4ecede3a6f58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "created_by", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "user_email", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False
        ),
        sa.Column(
            "event_type", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False
        ),
        sa.Column("page", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column(
            "timestamp", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_usage_events_user_timestamp",
        "usage_events",
        ["user_email", "timestamp"],
        unique=False,
    )
    op.create_index(
        "ix_usage_events_type_timestamp",
        "usage_events",
        ["event_type", "timestamp"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_usage_events_type_timestamp", table_name="usage_events")
    op.drop_index("ix_usage_events_user_timestamp", table_name="usage_events")
    op.drop_table("usage_events")
