"""In-app notification models for RBAC workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field

from lab_manager.models.base import AuditMixin


class Notification(AuditMixin, table=True):
    __tablename__ = "notifications"
    __table_args__ = (sa.Index("ix_notifications_staff_unread", "staff_id", "is_read"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    staff_id: int = Field(foreign_key="staff.id", index=True)
    type: str = Field(max_length=50, index=True)
    title: str = Field(max_length=200)
    message: str = Field(max_length=1000)
    link: Optional[str] = Field(default=None, max_length=500)
    is_read: bool = Field(default=False)
    read_at: Optional[datetime] = Field(default=None)


class NotificationPreference(AuditMixin, table=True):
    __tablename__ = "notification_preferences"

    id: Optional[int] = Field(default=None, primary_key=True)
    staff_id: int = Field(foreign_key="staff.id", unique=True, index=True)
    in_app: bool = Field(default=True)
    email_weekly: bool = Field(default=False)
    order_requests: bool = Field(default=True)
    document_reviews: bool = Field(default=True)
    inventory_alerts: bool = Field(default=True)
    team_changes: bool = Field(default=True)
