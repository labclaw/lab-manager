"""Persistent alert model for expiry/low-stock/review notifications."""

from __future__ import annotations

import enum
from datetime import datetime

import sqlalchemy as sa
from sqlmodel import Field

from lab_manager.models.base import AuditMixin


class AlertType(enum.StrEnum):
    expired = "expired"
    expiring_soon = "expiring_soon"
    out_of_stock = "out_of_stock"
    low_stock = "low_stock"
    pending_review = "pending_review"
    stale_orders = "stale_orders"


class AlertSeverity(enum.StrEnum):
    critical = "critical"
    warning = "warning"
    info = "info"


class Alert(AuditMixin, table=True):
    __tablename__ = "alerts"
    __table_args__ = (
        sa.CheckConstraint(
            "alert_type IN ('expired','expiring_soon','out_of_stock','low_stock','pending_review','stale_orders')",
            name="ck_alerts_alert_type",
        ),
        sa.CheckConstraint(
            "severity IN ('critical','warning','info')",
            name="ck_alerts_severity",
        ),
        sa.Index("ix_alert_entity", "entity_type", "entity_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    alert_type: str = Field(max_length=50, index=True)
    severity: str = Field(max_length=20, index=True)
    message: str = Field(max_length=1000)
    entity_type: str = Field(max_length=50)
    entity_id: int
    is_acknowledged: bool = Field(default=False)
    acknowledged_by: str | None = Field(default=None, max_length=200)
    acknowledged_at: datetime | None = Field(default=None)
    is_resolved: bool = Field(default=False)
