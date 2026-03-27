"""Alert management endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.api.auth import require_permission
from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import paginate
from lab_manager.models.alert import Alert
from lab_manager.models.base import utcnow
from lab_manager.services.alerts import get_alert_summary, persist_alerts
from lab_manager.services.notification_service import create_alert_notifications
from lab_manager.services.notifications import dispatch_alerts

router = APIRouter()


@router.get("/", dependencies=[Depends(require_permission("acknowledge_alerts"))])
def list_alerts(
    alert_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    acknowledged: Optional[bool] = Query(None),
    resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List alerts with optional filters. Defaults to unresolved."""
    q = select(Alert)
    if alert_type:
        q = q.where(Alert.alert_type == alert_type)
    if severity:
        q = q.where(Alert.severity == severity)
    if acknowledged is not None:
        q = q.where(Alert.is_acknowledged == acknowledged)
    if resolved is not None:
        q = q.where(Alert.is_resolved == resolved)
    else:
        # Default: only show unresolved alerts
        q = q.where(Alert.is_resolved.is_(False))
    q = q.order_by(Alert.created_at.desc())
    return paginate(q, db, page, page_size)


@router.get(
    "/summary", dependencies=[Depends(require_permission("acknowledge_alerts"))]
)
def alert_summary(db: Session = Depends(get_db)):
    """Return alert counts grouped by type and severity."""
    return get_alert_summary(db)


@router.post("/check", dependencies=[Depends(require_permission("manage_alerts"))])
def run_alert_check(request: Request, db: Session = Depends(get_db)):
    """Trigger alert checks, persist new alerts, return summary.

    Rate limited to 5 requests per minute via slowapi.
    """
    created, current = persist_alerts(db)
    create_alert_notifications(db, created)
    dispatch_alerts(created)
    summary = get_alert_summary(db, alerts=current)
    return {
        "new_alerts": len(created),
        "summary": summary,
    }


@router.post(
    "/{alert_id}/acknowledge",
    dependencies=[Depends(require_permission("acknowledge_alerts"))],
)
def acknowledge_alert(
    alert_id: int,
    acknowledged_by: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Mark an alert as acknowledged."""
    alert = get_or_404(db, Alert, alert_id, "Alert")
    alert.is_acknowledged = True
    alert.acknowledged_by = acknowledged_by
    alert.acknowledged_at = utcnow()
    db.flush()
    db.refresh(alert)
    return alert


@router.post(
    "/{alert_id}/resolve", dependencies=[Depends(require_permission("manage_alerts"))]
)
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
):
    """Mark an alert as resolved."""
    alert = get_or_404(db, Alert, alert_id, "Alert")
    alert.is_resolved = True
    if not alert.is_acknowledged:
        alert.is_acknowledged = True
        alert.acknowledged_at = utcnow()
    db.flush()
    db.refresh(alert)
    return alert
