"""add notifications tables and staff digital-staff columns

Revision ID: a1b2c3d4e5f6
Revises: 9b2c4d6e8f10
Create Date: 2026-03-29

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9b2c4d6e8f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- notifications table --
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("link", sa.String(500), nullable=True),
        sa.Column(
            "is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.String(100), nullable=True),
    )
    op.create_index("ix_notifications_staff_id", "notifications", ["staff_id"])
    op.create_index("ix_notifications_type", "notifications", ["type"])
    op.create_index(
        "ix_notifications_staff_unread", "notifications", ["staff_id", "is_read"]
    )

    # -- notification_preferences table --
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column(
            "in_app", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "email_weekly",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "order_requests",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "document_reviews",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "inventory_alerts",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "team_changes", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.String(100), nullable=True),
    )
    op.create_index(
        "ix_notification_preferences_staff_id",
        "notification_preferences",
        ["staff_id"],
        unique=True,
    )

    # -- staff table: add digital-staff columns --
    op.add_column(
        "staff",
        sa.Column("staff_type", sa.String(20), nullable=False, server_default="human"),
    )
    op.add_column(
        "staff",
        sa.Column("agent_config", sa.JSON(), nullable=True),
    )
    op.add_column(
        "staff",
        sa.Column("avatar_emoji", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("staff", "avatar_emoji")
    op.drop_column("staff", "agent_config")
    op.drop_column("staff", "staff_type")
    op.drop_table("notification_preferences")
    op.drop_table("notifications")
