"""Audit log for tracking all data changes."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Session
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON, func
from sqlalchemy.dialects.postgresql import JSONB as _JSONB

from lab_manager.models.base import utcnow

VALID_AUDIT_ACTIONS = ("create", "update", "delete")


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"
    __table_args__ = (
        sa.Index(
            "ix_audit_log_table_record_ts", "table_name", "record_id", "timestamp"
        ),
        sa.CheckConstraint(
            "action IN ('create','update','delete')",
            name="ck_audit_log_action",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    table_name: str = Field(max_length=100)
    record_id: int
    action: str = Field(
        max_length=20,
        sa_column_kwargs={
            "nullable": False,
        },
    )
    changed_by: Optional[str] = Field(default=None, max_length=100)
    changes: dict = Field(
        default_factory=dict, sa_column=Column(_JSONB().with_variant(JSON, "sqlite"))
    )
    timestamp: datetime = Field(
        default_factory=utcnow,
        sa_column_kwargs={"server_default": func.now()},
        index=True,
    )


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
