"""Inventory CRUD and lifecycle endpoints."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import apply_sort, ilike_col, paginate
from lab_manager.models.inventory import InventoryItem, InventoryStatus
from lab_manager.services import inventory as inv_svc

router = APIRouter()

_INV_SORTABLE = {
    "id",
    "created_at",
    "updated_at",
    "product_id",
    "location_id",
    "quantity_on_hand",
    "expiry_date",
    "status",
}

_VALID_INV_STATUSES = {s.value for s in InventoryStatus}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class InventoryItemCreate(BaseModel):
    product_id: int
    location_id: Optional[int] = None
    lot_number: Optional[str] = Field(default=None, max_length=100)
    quantity_on_hand: float = Field(default=0, ge=0)
    unit: Optional[str] = Field(default=None, max_length=50)
    expiry_date: Optional[date] = None
    opened_date: Optional[date] = None
    status: str = InventoryStatus.available
    notes: Optional[str] = Field(default=None, max_length=2000)
    received_by: Optional[str] = Field(default=None, max_length=200)
    order_item_id: Optional[int] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in _VALID_INV_STATUSES:
            raise ValueError(f"status must be one of {_VALID_INV_STATUSES}")
        return v


class InventoryItemUpdate(BaseModel):
    product_id: Optional[int] = None
    location_id: Optional[int] = None
    lot_number: Optional[str] = Field(default=None, max_length=100)
    quantity_on_hand: Optional[float] = None
    unit: Optional[str] = Field(default=None, max_length=50)
    expiry_date: Optional[date] = None
    opened_date: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    received_by: Optional[str] = Field(default=None, max_length=200)
    order_item_id: Optional[int] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_INV_STATUSES:
            raise ValueError(f"status must be one of {_VALID_INV_STATUSES}")
        return v


class ConsumeBody(BaseModel):
    quantity: float = Field(gt=0)
    consumed_by: str = Field(max_length=200)
    purpose: Optional[str] = Field(default=None, max_length=500)


class TransferBody(BaseModel):
    location_id: int
    transferred_by: str = Field(max_length=200)


class AdjustBody(BaseModel):
    new_quantity: float = Field(ge=0)
    reason: str = Field(max_length=500)
    adjusted_by: str = Field(max_length=200)


class DisposeBody(BaseModel):
    reason: str = Field(max_length=500)
    disposed_by: str = Field(max_length=200)


class OpenBody(BaseModel):
    opened_by: str = Field(max_length=200)


# ---------------------------------------------------------------------------
# Fixed-path routes MUST come before /{item_id} parameter routes
# ---------------------------------------------------------------------------


@router.get("/")
def list_inventory(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    product_id: Optional[int] = Query(None),
    location_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    expiring_before: Optional[date] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    stmt = select(InventoryItem).options(selectinload(InventoryItem.product))
    if product_id is not None:
        stmt = stmt.where(InventoryItem.product_id == product_id)
    if location_id is not None:
        stmt = stmt.where(InventoryItem.location_id == location_id)
    if status:
        stmt = stmt.where(InventoryItem.status == status)
    if expiring_before:
        stmt = stmt.where(InventoryItem.expiry_date <= expiring_before)
    if search:
        stmt = stmt.where(
            ilike_col(InventoryItem.lot_number, search)
            | ilike_col(InventoryItem.notes, search)
        )
    stmt = apply_sort(stmt, InventoryItem, sort_by, sort_dir, _INV_SORTABLE)
    return paginate(db, stmt, page, page_size)


@router.post("/", status_code=201)
def create_inventory_item(body: InventoryItemCreate, db: Session = Depends(get_db)):
    item = InventoryItem(**body.model_dump())
    db.add(item)
    db.flush()
    db.refresh(item)
    return item


@router.get("/low-stock")
def low_stock(db: Session = Depends(get_db)):
    """Products below their reorder level."""
    return inv_svc.get_low_stock(db)


@router.get("/expiring")
def expiring(days: int = Query(30, ge=1), db: Session = Depends(get_db)):
    """Items expiring within N days."""
    return inv_svc.get_expiring(db, days=days)


# ---------------------------------------------------------------------------
# Parameterised item routes
# ---------------------------------------------------------------------------


@router.get("/{item_id}")
def get_inventory_item(item_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, InventoryItem, item_id, "Inventory item")


@router.patch("/{item_id}")
def update_inventory_item(
    item_id: int, body: InventoryItemUpdate, db: Session = Depends(get_db)
):
    item = get_or_404(db, InventoryItem, item_id, "Inventory item")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.flush()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_inventory_item(item_id: int, db: Session = Depends(get_db)):
    """Soft-delete: set status to 'deleted'."""
    item = get_or_404(db, InventoryItem, item_id, "Inventory item")
    item.status = InventoryStatus.deleted
    db.flush()
    return None


@router.get("/{item_id}/history")
def item_history(item_id: int, db: Session = Depends(get_db)):
    """Consumption log for a specific inventory item."""
    return inv_svc.get_item_history(item_id, db)


@router.post("/{item_id}/consume")
def consume_item(item_id: int, body: ConsumeBody, db: Session = Depends(get_db)):
    return inv_svc.consume(item_id, body.quantity, body.consumed_by, body.purpose, db)


@router.post("/{item_id}/transfer")
def transfer_item(item_id: int, body: TransferBody, db: Session = Depends(get_db)):
    return inv_svc.transfer(item_id, body.location_id, body.transferred_by, db)


@router.post("/{item_id}/adjust")
def adjust_item(item_id: int, body: AdjustBody, db: Session = Depends(get_db)):
    return inv_svc.adjust(item_id, body.new_quantity, body.reason, body.adjusted_by, db)


@router.post("/{item_id}/dispose")
def dispose_item(item_id: int, body: DisposeBody, db: Session = Depends(get_db)):
    return inv_svc.dispose(item_id, body.reason, body.disposed_by, db)


@router.post("/{item_id}/open")
def open_item(item_id: int, body: OpenBody, db: Session = Depends(get_db)):
    return inv_svc.open_item(item_id, body.opened_by, db)
