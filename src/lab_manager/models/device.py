"""Lab device model for Tailscale-connected PCs and instruments."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import Column
from sqlmodel import Field

from lab_manager.models.base import AuditMixin, utcnow


class DeviceStatus:
    online = "online"
    offline = "offline"
    error = "error"


VALID_DEVICE_STATUSES = (
    DeviceStatus.online,
    DeviceStatus.offline,
    DeviceStatus.error,
)


class Device(AuditMixin, table=True):
    __tablename__ = "devices"
    __table_args__ = (
        sa.CheckConstraint(
            f"status IN ({','.join(repr(v) for v in VALID_DEVICE_STATUSES)})",
            name="ck_device_status",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str = Field(unique=True, index=True, max_length=100)
    hostname: str = Field(index=True, max_length=255)
    ip_address: Optional[str] = Field(default=None, max_length=45)
    tailscale_ip: Optional[str] = Field(default=None, max_length=45)
    platform: Optional[str] = Field(default=None, max_length=50)
    os_version: Optional[str] = Field(default=None, max_length=100)

    status: str = Field(default=DeviceStatus.online, max_length=30, index=True)
    last_heartbeat_at: Optional[datetime] = None
    first_seen_at: datetime = Field(default_factory=utcnow)

    # System metrics (from psutil)
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    memory_total_mb: Optional[float] = None
    disk_percent: Optional[float] = None
    disk_total_gb: Optional[float] = None

    # Tailscale info
    tailscale_online: bool = Field(default=False)
    tailscale_exit_node: bool = Field(default=False)

    # Metadata
    notes: Optional[str] = Field(default=None, sa_column=Column(sa.Text))
    extra: dict = Field(default_factory=dict, sa_column=Column(sa.JSON))
