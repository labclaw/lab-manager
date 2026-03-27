"""Proactive AI feed endpoint — combines alerts, activity, and AI suggestions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.models.alert import Alert
from lab_manager.models.audit import AuditLog
from lab_manager.services.alerts import check_all_alerts

router = APIRouter()


def _severity_to_priority(severity: str) -> str:
    """Map alert severity to feed priority."""
    return {"critical": "high", "warning": "medium", "info": "low"}.get(severity, "low")


def _build_alert_items(db: Session) -> list[dict]:
    """Convert active alerts into feed items."""
    alerts = db.scalars(
        select(Alert)
        .where(Alert.is_resolved.is_(False))
        .order_by(Alert.created_at.desc())
        .limit(50)
    ).all()

    items = []
    for a in alerts:
        action_url = None
        if a.entity_type == "inventory":
            action_url = "#inventory"
        elif a.entity_type == "document":
            action_url = "#review"
        elif a.entity_type == "order":
            action_url = "#orders"
        elif a.entity_type == "product":
            action_url = "#inventory"

        items.append(
            {
                "id": f"alert-{a.id}",
                "type": "alert",
                "priority": _severity_to_priority(a.severity),
                "title": a.alert_type.replace("_", " ").title(),
                "description": a.message,
                "timestamp": a.created_at.isoformat() if a.created_at else None,
                "action_url": action_url,
                "is_read": a.is_acknowledged,
            }
        )
    return items


def _build_activity_items(db: Session) -> list[dict]:
    """Convert recent audit log entries into feed items."""
    entries = db.scalars(
        select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(50)
    ).all()

    items = []
    for e in entries:
        action_label = {
            "create": "Created",
            "update": "Updated",
            "delete": "Deleted",
        }.get(e.action, e.action.title())

        action_url = None
        if e.table_name == "documents":
            action_url = "#documents"
        elif e.table_name == "inventory_items":
            action_url = "#inventory"
        elif e.table_name == "orders":
            action_url = "#orders"
        elif e.table_name in ("vendors", "products"):
            action_url = "#dashboard"

        items.append(
            {
                "id": f"activity-{e.id}",
                "type": "activity",
                "priority": "low",
                "title": f"{action_label} {e.table_name.replace('_', ' ')}",
                "description": f"Record #{e.record_id} was {e.action}d"
                + (f" by {e.changed_by}" if e.changed_by else ""),
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "action_url": action_url,
                "is_read": True,
            }
        )
    return items


def _build_suggestion_items(db: Session) -> list[dict]:
    """Generate AI-suggested actions from current alert state."""
    alerts = check_all_alerts(db)
    suggestions = []
    seen: set[str] = set()

    for a in alerts:
        key = a["type"]
        if key in seen:
            continue
        seen.add(key)

        title = ""
        description = ""
        action_url = None

        if key == "expired":
            title = "Remove expired items"
            description = "Some inventory items have expired. Consider disposing them."
            action_url = "#inventory"
        elif key == "expiring_soon":
            title = "Review expiring items"
            description = (
                "Items are approaching their expiry date. Plan usage or reorder."
            )
            action_url = "#inventory"
        elif key == "low_stock":
            title = "Reorder low-stock items"
            description = "Products are below minimum stock levels. Place orders soon."
            action_url = "#orders"
        elif key == "out_of_stock":
            title = "Order out-of-stock products"
            description = "Some products have zero inventory. Reorder immediately."
            action_url = "#orders"
        elif key == "pending_review":
            title = "Review pending documents"
            description = "Documents are awaiting your review and approval."
            action_url = "#review"
        elif key == "stale_orders":
            title = "Follow up on stale orders"
            description = "Some orders have been pending for over 30 days."
            action_url = "#orders"

        if title:
            suggestions.append(
                {
                    "id": f"suggestion-{uuid.uuid4().hex[:12]}",
                    "type": "suggestion",
                    "priority": "high"
                    if key in ("expired", "out_of_stock")
                    else "medium",
                    "title": title,
                    "description": description,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action_url": action_url,
                    "is_read": False,
                }
            )

    return suggestions


@router.get("/")
def get_feed(
    item_type: Optional[str] = Query(
        None, description="Filter by type: alert, activity, suggestion"
    ),
    priority: Optional[str] = Query(
        None, description="Filter by priority: high, medium, low"
    ),
    db: Session = Depends(get_db),
):
    """Return combined feed items from alerts, activity log, and AI suggestions."""
    items: list[dict] = []
    items.extend(_build_alert_items(db))
    items.extend(_build_activity_items(db))
    items.extend(_build_suggestion_items(db))

    if item_type:
        items = [i for i in items if i["type"] == item_type]
    if priority:
        items = [i for i in items if i["priority"] == priority]

    items.sort(key=lambda i: i.get("timestamp") or "", reverse=True)

    return {
        "items": items,
        "total": len(items),
    }


@router.post("/{item_id}/read")
def mark_feed_item_read(item_id: str, db: Session = Depends(get_db)):
    """Mark a feed item as read. For alert items, acknowledges the underlying alert."""
    if item_id.startswith("alert-"):
        try:
            alert_id = int(item_id.split("-", 1)[1])
        except (ValueError, IndexError):
            return {"status": "ok"}
        alert = db.get(Alert, alert_id)
        if alert and not alert.is_acknowledged:
            alert.is_acknowledged = True
            alert.acknowledged_at = datetime.now(timezone.utc)
            db.flush()
    return {"status": "ok"}
