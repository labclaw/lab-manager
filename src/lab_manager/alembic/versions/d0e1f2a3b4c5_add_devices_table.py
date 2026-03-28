"""add devices table

Revision ID: d0e1f2a3b4c5
Revises: b1c2d3e4f5a6, a2b3c4d5e6f7, a0b1c2d3e4f5
Create Date: 2026-03-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = (
    "b1c2d3e4f5a6",
    "a2b3c4d5e6f7",
    "a0b1c2d3e4f5",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "devices",
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
            "device_id", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False
        ),
        sa.Column(
            "hostname", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False
        ),
        sa.Column(
            "ip_address", sqlmodel.sql.sqltypes.AutoString(length=45), nullable=True
        ),
        sa.Column(
            "tailscale_ip", sqlmodel.sql.sqltypes.AutoString(length=45), nullable=True
        ),
        sa.Column(
            "platform", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True
        ),
        sa.Column(
            "os_version", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.Column(
            "status",
            sqlmodel.sql.sqltypes.AutoString(length=30),
            nullable=False,
            server_default="online",
        ),
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("cpu_percent", sa.Float(), nullable=True),
        sa.Column("memory_percent", sa.Float(), nullable=True),
        sa.Column("memory_total_mb", sa.Float(), nullable=True),
        sa.Column("disk_percent", sa.Float(), nullable=True),
        sa.Column("disk_total_gb", sa.Float(), nullable=True),
        sa.Column(
            "tailscale_online", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "tailscale_exit_node", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "status IN ('online','offline','error')",
            name="ck_device_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", name="uq_device_device_id"),
    )
    op.create_index("ix_devices_device_id", "devices", ["device_id"], unique=True)
    op.create_index("ix_devices_hostname", "devices", ["hostname"], unique=False)
    op.create_index("ix_devices_status", "devices", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_devices_status", table_name="devices")
    op.drop_index("ix_devices_hostname", table_name="devices")
    op.drop_index("ix_devices_device_id", table_name="devices")
    op.drop_table("devices")
