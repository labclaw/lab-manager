"""In-app notification CRUD service for RBAC workflows."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlmodel import Session

from lab_manager.models.notification import Notification, NotificationPreference

log = logging.getLogger(__name__)


def create_notification(
    db: Session,
    staff_id: int,
    type: str,
    title: str,
    message: str,
    link: Optional[str] = None,
) -> Notification:
    """Create and persist a new in-app notification."""
    notif = Notification(
        staff_id=staff_id,
        type=type,
        title=title,
        message=message,
        link=link,
    )
    db.add(notif)
    db.flush()
    db.refresh(notif)
    log.info(
        "Created notification id=%s for staff_id=%s type=%s", notif.id, staff_id, type
    )
    return notif


def get_unread_count(db: Session, staff_id: int) -> int:
    """Return number of unread notifications for a staff member."""
    stmt = select(Notification).where(
        Notification.staff_id == staff_id,
        Notification.is_read.is_(False),
    )
    # Use a count subquery for efficiency
    from sqlalchemy import func

    count_stmt = select(func.count()).select_from(stmt.subquery())
    return db.execute(count_stmt).scalar() or 0


def mark_read(
    db: Session, notification_id: int, staff_id: int
) -> Optional[Notification]:
    """Mark a single notification as read. Returns the notification or None."""
    notif = db.scalars(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.staff_id == staff_id,
        )
    ).first()
    if notif and not notif.is_read:
        notif.is_read = True
        notif.read_at = datetime.now(timezone.utc)
        db.flush()
        db.refresh(notif)
    return notif


def mark_all_read(db: Session, staff_id: int) -> int:
    """Mark all unread notifications as read for a staff member. Returns count updated."""
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(Notification)
        .where(
            Notification.staff_id == staff_id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=now)
    )
    db.flush()
    return result.rowcount


def get_preferences(db: Session, staff_id: int) -> NotificationPreference:
    """Get or create notification preferences for a staff member."""
    pref = db.scalars(
        select(NotificationPreference).where(
            NotificationPreference.staff_id == staff_id,
        )
    ).first()
    if not pref:
        pref = NotificationPreference(staff_id=staff_id)
        db.add(pref)
        db.flush()
        db.refresh(pref)
    return pref


def update_preferences(
    db: Session,
    staff_id: int,
    updates: dict,
) -> NotificationPreference:
    """Update notification preferences for a staff member."""
    pref = get_preferences(db, staff_id)
    for key, value in updates.items():
        if hasattr(pref, key) and key not in ("id", "staff_id"):
            setattr(pref, key, value)
    db.flush()
    db.refresh(pref)
    return pref
