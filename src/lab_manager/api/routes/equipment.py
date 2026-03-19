"""Equipment CRUD endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

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


class EquipmentCreate(BaseModel):
    name: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    system_id: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    location_id: Optional[int] = None
    room: Optional[str] = None
    estimated_value: Optional[float] = None
    status: str = EquipmentStatus.active
    is_api_controllable: bool = False
    api_interface: Optional[str] = None
    notes: Optional[str] = None
    photos: list = []
    extracted_data: Optional[dict] = None
    extra: dict = {}


class EquipmentUpdate(BaseModel):
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    system_id: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    location_id: Optional[int] = None
    room: Optional[str] = None
    estimated_value: Optional[float] = None
    status: Optional[str] = None
    is_api_controllable: Optional[bool] = None
    api_interface: Optional[str] = None
    notes: Optional[str] = None
    photos: Optional[list] = None
    extracted_data: Optional[dict] = None
    extra: Optional[dict] = None


@router.get("/")
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
    q = db.query(Equipment).filter(Equipment.status != EquipmentStatus.deleted)
    if category:
        q = q.filter(Equipment.category == category)
    if status:
        q = q.filter(Equipment.status == status)
    if manufacturer:
        q = q.filter(ilike_col(Equipment.manufacturer, manufacturer))
    if search:
        q = q.filter(
            ilike_col(Equipment.name, search)
            | ilike_col(Equipment.manufacturer, search)
            | ilike_col(Equipment.serial_number, search)
            | ilike_col(Equipment.system_id, search)
        )
    q = apply_sort(q, Equipment, sort_by, sort_dir, _SORTABLE)
    return paginate(q, page, page_size)


@router.post("/", status_code=201)
def create_equipment(body: EquipmentCreate, db: Session = Depends(get_db)):
    equip = Equipment(**body.model_dump())
    db.add(equip)
    db.flush()
    db.refresh(equip)
    return equip


@router.get("/{equipment_id}")
def get_equipment(equipment_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Equipment, equipment_id, "Equipment")


@router.patch("/{equipment_id}")
def update_equipment(
    equipment_id: int, body: EquipmentUpdate, db: Session = Depends(get_db)
):
    equip = get_or_404(db, Equipment, equipment_id, "Equipment")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(equip, key, value)
    db.flush()
    db.refresh(equip)
    return equip


@router.delete("/{equipment_id}")
def delete_equipment(equipment_id: int, db: Session = Depends(get_db)):
    equip = get_or_404(db, Equipment, equipment_id, "Equipment")
    equip.status = EquipmentStatus.deleted
    db.flush()
    db.refresh(equip)
    return equip
