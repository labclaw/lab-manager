"""Usage event model for tracking page views and user interactions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import Column
from sqlmodel import Field

from lab_manager.models.base import AuditMixin


class UsageEvent(AuditMixin, table=True):
    __tablename__ = "usage_events"
    __table_args__ = (
        sa.Index("ix_usage_events_user_timestamp", "user_email", "timestamp"),
        sa.Index("ix_usage_events_type_timestamp", "event_type", "timestamp"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_email: str = Field(max_length=255)
    event_type: str = Field(max_length=50)
    page: Optional[str] = Field(default=None, max_length=255)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"server_default": sa.func.now()},
    )
    metadata_: Optional[dict] = Field(
        default=None,
        sa_column=Column("metadata", sa.JSON),
    )
