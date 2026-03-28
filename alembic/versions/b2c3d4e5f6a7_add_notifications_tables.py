"""add notifications tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-25 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str]] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column(
            "title", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False
        ),
        sa.Column(
            "message", sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=False
        ),
        sa.Column("link", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "created_by", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_staff_id", "notifications", ["staff_id"])
    op.create_index("ix_notifications_type", "notifications", ["type"])
    op.create_index(
        "ix_notifications_staff_unread", "notifications", ["staff_id", "is_read"]
    )

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.Column("in_app", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("email_weekly", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "order_requests", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column(
            "document_reviews", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column(
            "inventory_alerts", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column("team_changes", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "created_by", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("staff_id"),
    )
    op.create_index(
        "ix_notification_preferences_staff_id",
        "notification_preferences",
        ["staff_id"],
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_table("notifications")
