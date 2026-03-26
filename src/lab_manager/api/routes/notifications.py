"""In-app notification endpoints for RBAC workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.api.pagination import paginate
from lab_manager.models.notification import Notification
from lab_manager.services import notification_service as svc

router = APIRouter()

# TODO: Replace with real auth dependency when RBAC is wired up.
# For now, staff_id is passed as a query param for testability.

NOTIFICATION_SORTABLE = {"id", "created_at", "type", "is_read"}


# --- Schemas ---


class NotificationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    staff_id: int
    type: str
    title: str
    message: str
    link: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkAllReadResponse(BaseModel):
    marked: int


class PreferenceResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    staff_id: int
    in_app: bool
    email_weekly: bool
    order_requests: bool
    document_reviews: bool
    inventory_alerts: bool
    team_changes: bool


class PreferenceUpdate(BaseModel):
    in_app: Optional[bool] = None
    email_weekly: Optional[bool] = None
    order_requests: Optional[bool] = None
    document_reviews: Optional[bool] = None
    inventory_alerts: Optional[bool] = None
    team_changes: Optional[bool] = None


# --- Endpoints ---


@router.get("/")
def list_notifications(
    staff_id: int = Query(..., description="Staff member ID"),
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    stmt = select(Notification).where(Notification.staff_id == staff_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc())
    return paginate(stmt, db, page, page_size)


@router.get("/count", response_model=UnreadCountResponse)
def unread_count(
    staff_id: int = Query(..., description="Staff member ID"),
    db: Session = Depends(get_db),
):
    return UnreadCountResponse(unread_count=svc.get_unread_count(db, staff_id))


@router.post("/read-all", response_model=MarkAllReadResponse)
def mark_all_notifications_read(
    staff_id: int = Query(..., description="Staff member ID"),
    db: Session = Depends(get_db),
):
    count = svc.mark_all_read(db, staff_id)
    return MarkAllReadResponse(marked=count)


@router.get("/preferences", response_model=PreferenceResponse)
def get_preferences(
    staff_id: int = Query(..., description="Staff member ID"),
    db: Session = Depends(get_db),
):
    return svc.get_preferences(db, staff_id)


@router.patch("/preferences", response_model=PreferenceResponse)
def update_preferences(
    body: PreferenceUpdate,
    staff_id: int = Query(..., description="Staff member ID"),
    db: Session = Depends(get_db),
):
    updates = body.model_dump(exclude_unset=True)
    return svc.update_preferences(db, staff_id, updates)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    staff_id: int = Query(..., description="Staff member ID"),
    db: Session = Depends(get_db),
):
    notif = svc.mark_read(db, notification_id, staff_id)
    if not notif:
        from lab_manager.exceptions import NotFoundError

        raise NotFoundError("Notification", notification_id)
    return notif
