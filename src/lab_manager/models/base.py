"""Shared base for all models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditMixin(SQLModel):
    """Mixin adding audit timestamp fields to any model."""

    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column_kwargs={"server_default": func.now()},
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column_kwargs={"onupdate": utcnow, "server_default": func.now()},
    )
    created_by: Optional[str] = Field(default=None, max_length=100)
