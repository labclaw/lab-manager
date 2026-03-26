"""Audit log query endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.api.auth import require_permission
from lab_manager.api.deps import get_db
from lab_manager.api.pagination import paginate
from lab_manager.models.audit import AuditLog

router = APIRouter(dependencies=[Depends(require_permission("view_audit_log"))])


@router.get("")
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
    q = select(AuditLog)
    if table:
        q = q.where(AuditLog.table_name == table)
    if record_id is not None:
        q = q.where(AuditLog.record_id == record_id)
    if action:
        q = q.where(AuditLog.action == action)
    if changed_by:
        q = q.where(AuditLog.changed_by == changed_by)
    q = q.order_by(AuditLog.timestamp.desc())
    return paginate(q, db, page, page_size)


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
        select(AuditLog)
        .where(AuditLog.table_name == table, AuditLog.record_id == record_id)
        .order_by(AuditLog.timestamp.asc())
    )
    return paginate(q, db, page, page_size)
