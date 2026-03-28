"""Equipment CRUD endpoints."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.api.auth import require_permission
from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import apply_sort, ilike_col, paginate
from lab_manager.models.equipment import Equipment, EquipmentStatus

router = APIRouter()

_SORTABLE = {
    "id",
    "created_at",
    "updated_at",
    "name",
    "manufacturer",
    "category",
    "status",
}

_VALID_EQUIPMENT_STATUSES = {
    EquipmentStatus.active,
    EquipmentStatus.maintenance,
    EquipmentStatus.broken,
    EquipmentStatus.retired,
    EquipmentStatus.decommissioned,
    EquipmentStatus.deleted,
}


class EquipmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    manufacturer: Optional[str] = Field(default=None, max_length=255)
    model: Optional[str] = Field(default=None, max_length=255)
    serial_number: Optional[str] = Field(default=None, max_length=255)
    system_id: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=5000)
    location_id: Optional[int] = None
    room: Optional[str] = Field(default=None, max_length=100)
    estimated_value: Optional[Decimal] = Field(default=None, ge=0)
    status: str = EquipmentStatus.active
    is_api_controllable: bool = False
    api_interface: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=5000)
    photos: list = []
    extracted_data: Optional[dict] = None
    extra: dict = {}

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in _VALID_EQUIPMENT_STATUSES:
            raise ValueError(f"status must be one of {_VALID_EQUIPMENT_STATUSES}")
        return v


class EquipmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=500)
    manufacturer: Optional[str] = Field(default=None, max_length=255)
    model: Optional[str] = Field(default=None, max_length=255)
    serial_number: Optional[str] = Field(default=None, max_length=255)
    system_id: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=5000)
    location_id: Optional[int] = None
    room: Optional[str] = Field(default=None, max_length=100)
    estimated_value: Optional[Decimal] = Field(default=None, ge=0)
    status: Optional[str] = None
    is_api_controllable: Optional[bool] = None
    api_interface: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=5000)
    photos: Optional[list] = None
    extracted_data: Optional[dict] = None
    extra: Optional[dict] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_EQUIPMENT_STATUSES:
            raise ValueError(f"status must be one of {_VALID_EQUIPMENT_STATUSES}")
        return v


@router.get("/", dependencies=[Depends(require_permission("view_equipment"))])
def list_equipment(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    manufacturer: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    q = select(Equipment).where(Equipment.status != EquipmentStatus.deleted)
    if category:
        q = q.where(Equipment.category == category)
    if status:
        q = q.where(Equipment.status == status)
    if manufacturer:
        q = q.where(ilike_col(Equipment.manufacturer, manufacturer))
    if search:
        q = q.where(
            ilike_col(Equipment.name, search)
            | ilike_col(Equipment.manufacturer, search)
            | ilike_col(Equipment.serial_number, search)
            | ilike_col(Equipment.system_id, search)
        )
    q = apply_sort(q, Equipment, sort_by, sort_dir, _SORTABLE)
    return paginate(q, db, page, page_size)


@router.post(
    "/",
    status_code=201,
    dependencies=[Depends(require_permission("log_equipment_usage"))],
)
def create_equipment(body: EquipmentCreate, db: Session = Depends(get_db)):
    equip = Equipment(**body.model_dump())
    db.add(equip)
    db.flush()
    db.refresh(equip)
    return equip


@router.get("/{equipment_id}", dependencies=[Depends(require_permission("view_equipment"))])
def get_equipment(equipment_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Equipment, equipment_id, "Equipment")


@router.patch(
    "/{equipment_id}", dependencies=[Depends(require_permission("log_equipment_usage"))]
)
def update_equipment(
    equipment_id: int, body: EquipmentUpdate, db: Session = Depends(get_db)
):
    equip = get_or_404(db, Equipment, equipment_id, "Equipment")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(equip, key, value)
    db.flush()
    db.refresh(equip)
    return equip


@router.delete(
    "/{equipment_id}",
    status_code=204,
    dependencies=[Depends(require_permission("delete_records"))],
)
def delete_equipment(equipment_id: int, db: Session = Depends(get_db)):
    equip = get_or_404(db, Equipment, equipment_id, "Equipment")
    equip.status = EquipmentStatus.deleted
    db.flush()
    return None
