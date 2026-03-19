"""Inventory CRUD and lifecycle endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

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

_Db = Depends(get_db)
_InvPage = Query(1, ge=1)
_InvPageSize = Query(50, ge=1, le=200)
_InvProductId = Query(None)
_InvLocationId = Query(None)
_InvStatus = Query(None)
_InvExpiringBefore = Query(None)
_InvSearch = Query(None)
_InvSortBy = Query("id")
_InvSortDir = Query("asc", pattern="^(asc|desc)$")
_InvDays = Query(30, ge=1)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class InventoryItemCreate(BaseModel):
    product_id: int | None = None
    location_id: int | None = None
    lot_number: str | None = None
    quantity_on_hand: float = 0
    unit: str | None = None
    expiry_date: date | None = None
    opened_date: date | None = None
    status: str = InventoryStatus.available
    notes: str | None = None
    received_by: str | None = None
    order_item_id: int | None = None


class InventoryItemUpdate(BaseModel):
    product_id: int | None = None
    location_id: int | None = None
    lot_number: str | None = None
    quantity_on_hand: float | None = None
    unit: str | None = None
    expiry_date: date | None = None
    opened_date: date | None = None
    status: str | None = None
    notes: str | None = None
    received_by: str | None = None
    order_item_id: int | None = None


class ConsumeBody(BaseModel):
    quantity: float
    consumed_by: str
    purpose: str | None = None


class TransferBody(BaseModel):
    location_id: int
    transferred_by: str


class AdjustBody(BaseModel):
    new_quantity: float
    reason: str
    adjusted_by: str


class DisposeBody(BaseModel):
    reason: str
    disposed_by: str


class OpenBody(BaseModel):
    opened_by: str


# ---------------------------------------------------------------------------
# Fixed-path routes MUST come before /{item_id} parameter routes
# ---------------------------------------------------------------------------


@router.get("/")
def list_inventory(
    page: int = _InvPage,
    page_size: int = _InvPageSize,
    product_id: int | None = _InvProductId,
    location_id: int | None = _InvLocationId,
    status: str | None = _InvStatus,
    expiring_before: date | None = _InvExpiringBefore,
    search: str | None = _InvSearch,
    sort_by: str = _InvSortBy,
    sort_dir: str = _InvSortDir,
    db: Session = _Db,
):
    q = db.query(InventoryItem)
    if product_id is not None:
        q = q.filter(InventoryItem.product_id == product_id)
    if location_id is not None:
        q = q.filter(InventoryItem.location_id == location_id)
    if status:
        q = q.filter(InventoryItem.status == status)
    if expiring_before:
        q = q.filter(InventoryItem.expiry_date <= expiring_before)
    if search:
        q = q.filter(ilike_col(InventoryItem.lot_number, search) | ilike_col(InventoryItem.notes, search))
    q = apply_sort(q, InventoryItem, sort_by, sort_dir, _INV_SORTABLE)
    return paginate(q, page, page_size)


@router.post("/", status_code=201)
def create_inventory_item(body: InventoryItemCreate, db: Session = _Db):
    item = InventoryItem(**body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/low-stock")
def low_stock(db: Session = _Db):
    """Products below their reorder level."""
    return inv_svc.get_low_stock(db)


@router.get("/expiring")
def expiring(days: int = _InvDays, db: Session = _Db):
    """Items expiring within N days."""
    return inv_svc.get_expiring(db, days=days)


# ---------------------------------------------------------------------------
# Parameterised item routes
# ---------------------------------------------------------------------------


@router.get("/{item_id}")
def get_inventory_item(item_id: int, db: Session = _Db):
    return get_or_404(db, InventoryItem, item_id, "Inventory item")


@router.patch("/{item_id}")
def update_inventory_item(item_id: int, body: InventoryItemUpdate, db: Session = _Db):
    item = get_or_404(db, InventoryItem, item_id, "Inventory item")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_inventory_item(item_id: int, db: Session = _Db):
    """Soft-delete: set status to 'deleted'."""
    item = get_or_404(db, InventoryItem, item_id, "Inventory item")
    item.status = InventoryStatus.deleted
    db.commit()
    return None


@router.get("/{item_id}/history")
def item_history(item_id: int, db: Session = _Db):
    """Consumption log for a specific inventory item."""
    return inv_svc.get_item_history(item_id, db)


@router.post("/{item_id}/consume")
def consume_item(item_id: int, body: ConsumeBody, db: Session = _Db):
    return inv_svc.consume(item_id, body.quantity, body.consumed_by, body.purpose, db)


@router.post("/{item_id}/transfer")
def transfer_item(item_id: int, body: TransferBody, db: Session = _Db):
    return inv_svc.transfer(item_id, body.location_id, body.transferred_by, db)


@router.post("/{item_id}/adjust")
def adjust_item(item_id: int, body: AdjustBody, db: Session = _Db):
    return inv_svc.adjust(item_id, body.new_quantity, body.reason, body.adjusted_by, db)


@router.post("/{item_id}/dispose")
def dispose_item(item_id: int, body: DisposeBody, db: Session = _Db):
    return inv_svc.dispose(item_id, body.reason, body.disposed_by, db)


@router.post("/{item_id}/open")
def open_item(item_id: int, body: OpenBody, db: Session = _Db):
    return inv_svc.open_item(item_id, body.opened_by, db)
