"""Audit log query endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.api.pagination import paginate
from lab_manager.models.audit import AuditLog

router = APIRouter()


@router.get("/")
def list_audit_logs(
    table: str | None = Query(None),
    record_id: int | None = Query(None),
    action: str | None = Query(None),
    changed_by: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Query the audit log with optional filters."""
    q = db.query(AuditLog)
    if table:
        q = q.filter(AuditLog.table_name == table)
    if record_id is not None:
        q = q.filter(AuditLog.record_id == record_id)
    if action:
        q = q.filter(AuditLog.action == action)
    if changed_by:
        q = q.filter(AuditLog.changed_by == changed_by)
    q = q.order_by(AuditLog.timestamp.desc())
    return paginate(q, page, page_size)


@router.get("/{table}/{record_id}")
def get_record_history(
    table: str,
    record_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Full change history for a specific record."""
    q = (
        db.query(AuditLog)
        .filter(AuditLog.table_name == table, AuditLog.record_id == record_id)
        .order_by(AuditLog.timestamp.asc())
    )
    return paginate(q, page, page_size)
