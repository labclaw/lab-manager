"""Audit log query endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.api.pagination import paginate
from lab_manager.models.audit import AuditLog

router = APIRouter()


@router.get("/")
def list_audit_logs(
    table: Optional[str] = Query(None),
    record_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    changed_by: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Query the audit log with optional filters."""
    stmt = select(AuditLog)
    if table:
        stmt = stmt.where(AuditLog.table_name == table)
    if record_id is not None:
        stmt = stmt.where(AuditLog.record_id == record_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if changed_by:
        stmt = stmt.where(AuditLog.changed_by == changed_by)
    stmt = stmt.order_by(AuditLog.timestamp.desc())
    return paginate(db, stmt, page, page_size)


@router.get("/{table}/{record_id}")
def get_record_history(
    table: str,
    record_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Full change history for a specific record."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.table_name == table, AuditLog.record_id == record_id)
        .order_by(AuditLog.timestamp.asc())
    )
    return paginate(db, stmt, page, page_size)
