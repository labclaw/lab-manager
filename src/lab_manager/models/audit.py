"""Audit log for tracking all data changes."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Session
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB as _JSONB

from lab_manager.models.base import utcnow


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    table_name: str = Field(max_length=100, index=True)
    record_id: int = Field(index=True)
    action: str = Field(max_length=20)  # create, update, delete
    changed_by: Optional[str] = Field(default=None, max_length=100)
    changes: dict = Field(
        default_factory=dict, sa_column=Column(_JSONB().with_variant(JSON, "sqlite"))
    )
    timestamp: datetime = Field(default_factory=utcnow)


def log_change(
    db: Session,
    table_name: str,
    record_id: int,
    action: str,  # "create", "update", "delete"
    changed_by: str | None = None,
    changes: dict | None = None,
):
    """Write an audit log entry."""
    entry = AuditLog(
        table_name=table_name,
        record_id=record_id,
        action=action,
        changed_by=changed_by,
        changes=changes or {},
    )
    db.add(entry)
