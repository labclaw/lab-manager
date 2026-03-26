"""In-app notification endpoints for RBAC workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.api.auth import get_current_staff
from lab_manager.api.deps import get_db
from lab_manager.api.pagination import paginate
from lab_manager.models.notification import Notification
from lab_manager.services import notification_service as svc

router = APIRouter()

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
    request: Request,
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    staff: dict = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    staff_id = staff["id"]
    stmt = select(Notification).where(Notification.staff_id == staff_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc())
    return paginate(stmt, db, page, page_size)


@router.get("/count", response_model=UnreadCountResponse)
def unread_count(
    request: Request,
    staff: dict = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return UnreadCountResponse(unread_count=svc.get_unread_count(db, staff["id"]))


@router.post("/read-all", response_model=MarkAllReadResponse)
def mark_all_notifications_read(
    request: Request,
    staff: dict = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    count = svc.mark_all_read(db, staff["id"])
    return MarkAllReadResponse(marked=count)


@router.get("/preferences", response_model=PreferenceResponse)
def get_preferences(
    request: Request,
    staff: dict = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    return svc.get_preferences(db, staff["id"])


@router.patch("/preferences", response_model=PreferenceResponse)
def update_preferences(
    request: Request,
    body: PreferenceUpdate,
    staff: dict = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    updates = body.model_dump(exclude_unset=True)
    return svc.update_preferences(db, staff["id"], updates)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    request: Request,
    staff: dict = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    notif = svc.mark_read(db, notification_id, staff["id"])
    if not notif:
        from lab_manager.exceptions import NotFoundError

        raise NotFoundError("Notification", notification_id)
    return notif
