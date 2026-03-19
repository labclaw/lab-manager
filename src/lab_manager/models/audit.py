"""Audit log for tracking all data changes."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB as _JSONB
from sqlmodel import Column, Field, SQLModel

from lab_manager.models.base import utcnow


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"

    id: int | None = Field(default=None, primary_key=True)
    table_name: str = Field(max_length=100, index=True)
    record_id: int = Field(index=True)
    action: str = Field(max_length=20)  # create, update, delete
    changed_by: str | None = Field(default=None, max_length=100)
    changes: dict = Field(default_factory=dict, sa_column=Column(_JSONB().with_variant(JSON, "sqlite")))
    timestamp: datetime = Field(default_factory=utcnow)
