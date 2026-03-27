"""Unified PI Decision Queue — aggregated view of items needing attention."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.models.alert import Alert
from lab_manager.models.document import Document
from lab_manager.models.order_request import OrderRequest

router = APIRouter()

_PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _priority_for_alert(alert: Alert) -> str:
    if alert.severity == "critical":
        return "HIGH"
    if alert.alert_type in ("expired", "out_of_stock"):
        return "HIGH"
    return "MEDIUM"


def _priority_for_request(req: OrderRequest) -> str:
    if req.urgency == "urgent":
        return "MEDIUM"
    return "MEDIUM"


def _priority_for_document(doc: Document) -> str:
    return "LOW"


def _build_queue_item(
    item_id: int,
    item_type: str,
    priority: str,
    title: str,
    description: str,
    created_at,
    action_url: str,
) -> dict:
    return {
        "id": item_id,
        "type": item_type,
        "priority": priority,
        "title": title,
        "description": description,
        "created_at": created_at.isoformat() if created_at else None,
        "action_url": action_url,
    }


@router.get("/")
def get_queue(
    item_type: Optional[str] = Query(
        None, description="Filter by type: order_request, document, alert"
    ),
    priority: Optional[str] = Query(
        None, description="Filter by priority: HIGH, MEDIUM, LOW"
    ),
    db: Session = Depends(get_db),
):
    """Return a unified queue combining pending requests, documents needing
    review, and unresolved alerts, ordered by priority (HIGH > MEDIUM > LOW).
    """
    items: list[dict] = []

    # Pending order requests
    if item_type is None or item_type == "order_request":
        rows = db.scalars(
            select(OrderRequest).where(OrderRequest.status == "pending")
        ).all()
        for req in rows:
            desc = req.description or req.catalog_number or "Supply request"
            if req.quantity:
                desc = f"{desc} (qty: {req.quantity})"
            items.append(
                _build_queue_item(
                    item_id=req.id,
                    item_type="order_request",
                    priority=_priority_for_request(req),
                    title=f"Approve request #{req.id}",
                    description=desc,
                    created_at=req.created_at,
                    action_url=f"/api/v1/requests/{req.id}",
                )
            )

    # Documents needing review
    if item_type is None or item_type == "document":
        rows = db.scalars(
            select(Document).where(Document.status == "needs_review")
        ).all()
        for doc in rows:
            items.append(
                _build_queue_item(
                    item_id=doc.id,
                    item_type="document",
                    priority=_priority_for_document(doc),
                    title=f"Review document #{doc.id}: {doc.file_name}",
                    description=doc.vendor_name
                    or doc.document_type
                    or "Awaiting review",
                    created_at=doc.created_at,
                    action_url=f"/api/v1/documents/{doc.id}",
                )
            )

    # Unresolved alerts
    if item_type is None or item_type == "alert":
        rows = db.scalars(select(Alert).where(Alert.is_resolved.is_(False))).all()
        for alert in rows:
            items.append(
                _build_queue_item(
                    item_id=alert.id,
                    item_type="alert",
                    priority=_priority_for_alert(alert),
                    title=f"Alert: {alert.alert_type.replace('_', ' ').title()}",
                    description=alert.message,
                    created_at=alert.created_at,
                    action_url=f"/api/v1/alerts/{alert.id}",
                )
            )

    # Sort by priority then by created_at descending
    items.sort(
        key=lambda x: (
            _PRIORITY_ORDER.get(x["priority"], 9),
            x["created_at"] or "",
        ),
    )

    # Apply priority filter after sort
    if priority:
        items = [i for i in items if i["priority"] == priority]

    return {
        "items": items,
        "total": len(items),
        "counts": {
            "order_requests": sum(1 for i in items if i["type"] == "order_request"),
            "documents": sum(1 for i in items if i["type"] == "document"),
            "alerts": sum(1 for i in items if i["type"] == "alert"),
        },
    }
