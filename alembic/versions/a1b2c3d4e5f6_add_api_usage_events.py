"""Add api_usage_events table for AI cost tracking.

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_usage_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "endpoint", sa.String(100), nullable=False, server_default="'unknown'"
        ),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(100), nullable=True),
    )
    op.create_index("ix_api_usage_ts", "api_usage_events", ["timestamp"])
    op.create_index(
        "ix_api_usage_provider_ts", "api_usage_events", ["provider", "timestamp"]
    )
    op.create_index(
        "ix_api_usage_endpoint_ts", "api_usage_events", ["endpoint", "timestamp"]
    )


def downgrade() -> None:
    op.drop_index("ix_api_usage_endpoint_ts", table_name="api_usage_events")
    op.drop_index("ix_api_usage_provider_ts", table_name="api_usage_events")
    op.drop_index("ix_api_usage_ts", table_name="api_usage_events")
    op.drop_table("api_usage_events")
