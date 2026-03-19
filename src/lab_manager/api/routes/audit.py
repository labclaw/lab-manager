"""Audit log query endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.api.pagination import paginate
from lab_manager.models.audit import AuditLog

router = APIRouter()

_Table = Query(None)
_RecordId = Query(None)
_Action = Query(None)
_ChangedBy = Query(None)
_Page = Query(1, ge=1)
_PageSize = Query(100, ge=1, le=500)
_Db = Depends(get_db)


@router.get("/")
def list_audit_logs(
    table: str | None = _Table,
    record_id: int | None = _RecordId,
    action: str | None = _Action,
    changed_by: str | None = _ChangedBy,
    page: int = _Page,
    page_size: int = _PageSize,
    db: Session = _Db,
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
    page: int = _Page,
    page_size: int = _PageSize,
    db: Session = _Db,
):
    """Full change history for a specific record."""
    q = (
        db.query(AuditLog)
        .filter(AuditLog.table_name == table, AuditLog.record_id == record_id)
        .order_by(AuditLog.timestamp.asc())
    )
    return paginate(q, page, page_size)
