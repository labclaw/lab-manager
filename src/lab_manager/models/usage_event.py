"""Usage event model for tracking logins, page views, and user actions."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from lab_manager.models.base import utcnow


class UsageEvent(SQLModel, table=True):
    __tablename__ = "usage_events"
    __table_args__ = (
        sa.Index("ix_usage_events_user_ts", "user_email", "timestamp"),
        sa.Index("ix_usage_events_type_ts", "event_type", "timestamp"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_email: str = Field(max_length=255, index=True)
    event_type: str = Field(max_length=50, index=True)
    page: Optional[str] = Field(default=None, max_length=500)
    timestamp: datetime = Field(
        default_factory=utcnow,
        sa_column_kwargs={"server_default": sa.func.now()},
    )
    metadata_json: Optional[str] = Field(default=None, sa_column=sa.Column(sa.Text))
