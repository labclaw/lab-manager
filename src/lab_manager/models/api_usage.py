"""API usage event model for tracking AI/LLM costs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field

from lab_manager.models.base import AuditMixin


class ApiUsageEvent(AuditMixin, table=True):
    """Records each LLM/AI API call with token counts and cost."""

    __tablename__ = "api_usage_events"
    __table_args__ = (
        sa.Index("ix_api_usage_ts", "timestamp"),
        sa.Index("ix_api_usage_provider_ts", "provider", "timestamp"),
        sa.Index("ix_api_usage_endpoint_ts", "endpoint", "timestamp"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"server_default": sa.func.now()},
    )
    provider: str = Field(max_length=50)
    model: str = Field(max_length=100)
    tokens_in: int = Field(default=0)
    tokens_out: int = Field(default=0)
    cost_usd: float = Field(default=0.0)
    endpoint: str = Field(default="unknown", max_length=100)
    request_id: Optional[str] = Field(default=None, max_length=100)
