"""Equipment reservation model."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field

from lab_manager.models.base import AuditMixin


class ReservationStatus:
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"


VALID_RESERVATION_STATUSES = (
    ReservationStatus.confirmed,
    ReservationStatus.cancelled,
    ReservationStatus.completed,
)


class Reservation(AuditMixin, table=True):
    __tablename__ = "reservation"

    id: Optional[int] = Field(default=None, primary_key=True)
    equipment_id: int = Field(foreign_key="equipment.id", index=True)
    staff_id: int = Field(foreign_key="staff.id", index=True)
    start_time: datetime = Field(index=True)
    end_time: datetime = Field()
    purpose: Optional[str] = Field(default=None, max_length=500)
    status: str = Field(default=ReservationStatus.confirmed, max_length=20)
