"""Equipment reservation CRUD endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import apply_sort, paginate
from lab_manager.exceptions import ConflictError
from lab_manager.models.equipment import Equipment
from lab_manager.models.reservation import Reservation, ReservationStatus
from lab_manager.models.staff import Staff

router = APIRouter()

_SORTABLE = {
    "id",
    "created_at",
    "updated_at",
    "start_time",
    "end_time",
    "status",
}


class ReservationCreate(BaseModel):
    equipment_id: int
    staff_id: int
    start_time: datetime
    end_time: datetime
    purpose: Optional[str] = Field(default=None, max_length=500)

    @field_validator("end_time")
    @classmethod
    def validate_end_after_start(cls, v: datetime, info) -> datetime:
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError("end_time must be after start_time")
        return v


@router.get("/")
def list_reservations(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    equipment_id: Optional[int] = Query(None),
    staff_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start_after: Optional[datetime] = Query(None),
    start_before: Optional[datetime] = Query(None),
    sort_by: str = Query("start_time"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    q = select(Reservation)
    if equipment_id is not None:
        q = q.where(Reservation.equipment_id == equipment_id)
    if staff_id is not None:
        q = q.where(Reservation.staff_id == staff_id)
    if status:
        q = q.where(Reservation.status == status)
    if start_after:
        q = q.where(Reservation.start_time >= start_after)
    if start_before:
        q = q.where(Reservation.start_time < start_before)
    q = apply_sort(q, Reservation, sort_by, sort_dir, _SORTABLE)
    return paginate(q, db, page, page_size)


@router.post("/", status_code=201)
def create_reservation(body: ReservationCreate, db: Session = Depends(get_db)):
    # Validate foreign keys exist
    get_or_404(db, Equipment, body.equipment_id, "Equipment")
    get_or_404(db, Staff, body.staff_id, "Staff")

    # Conflict detection: check for overlapping confirmed reservations
    conflict = db.scalars(
        select(Reservation).where(
            and_(
                Reservation.equipment_id == body.equipment_id,
                Reservation.status == ReservationStatus.confirmed,
                Reservation.start_time < body.end_time,
                Reservation.end_time > body.start_time,
            )
        )
    ).first()
    if conflict:
        raise ConflictError(
            f"Equipment {body.equipment_id} is already reserved from "
            f"{conflict.start_time.isoformat()} to {conflict.end_time.isoformat()}"
        )

    reservation = Reservation(**body.model_dump())
    db.add(reservation)
    db.flush()
    db.refresh(reservation)
    return reservation


@router.delete("/{reservation_id}", status_code=200)
def cancel_reservation(reservation_id: int, db: Session = Depends(get_db)):
    reservation = get_or_404(db, Reservation, reservation_id, "Reservation")
    if reservation.status != ReservationStatus.confirmed:
        raise ConflictError(
            f"Reservation {reservation_id} is '{reservation.status}', cannot cancel"
        )
    reservation.status = ReservationStatus.cancelled
    db.flush()
    db.refresh(reservation)
    return reservation


@router.get("/equipment/{equipment_id}/availability")
def check_availability(
    equipment_id: int,
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    db: Session = Depends(get_db),
):
    get_or_404(db, Equipment, equipment_id, "Equipment")

    overlapping = db.scalars(
        select(Reservation)
        .where(
            and_(
                Reservation.equipment_id == equipment_id,
                Reservation.status == ReservationStatus.confirmed,
                Reservation.start_time < end_time,
                Reservation.end_time > start_time,
            )
        )
        .order_by(Reservation.start_time)
    ).all()

    return {
        "equipment_id": equipment_id,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "available": len(overlapping) == 0,
        "conflicting_reservations": [
            {
                "id": r.id,
                "start_time": r.start_time.isoformat(),
                "end_time": r.end_time.isoformat(),
                "staff_id": r.staff_id,
                "purpose": r.purpose,
            }
            for r in overlapping
        ],
    }
