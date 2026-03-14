"""Inventory CRUD and lifecycle endpoints."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.api.pagination import apply_sort, escape_like, paginate
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


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class InventoryItemCreate(BaseModel):
    product_id: Optional[int] = None
    location_id: Optional[int] = None
    lot_number: Optional[str] = None
    quantity_on_hand: float = 0
    unit: Optional[str] = None
    expiry_date: Optional[date] = None
    opened_date: Optional[date] = None
    status: str = InventoryStatus.available
    notes: Optional[str] = None
    received_by: Optional[str] = None
    order_item_id: Optional[int] = None


class InventoryItemUpdate(BaseModel):
    product_id: Optional[int] = None
    location_id: Optional[int] = None
    lot_number: Optional[str] = None
    quantity_on_hand: Optional[float] = None
    unit: Optional[str] = None
    expiry_date: Optional[date] = None
    opened_date: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    received_by: Optional[str] = None
    order_item_id: Optional[int] = None


class ConsumeBody(BaseModel):
    quantity: float
    consumed_by: str
    purpose: Optional[str] = None


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
        escaped = escape_like(search)
        q = q.filter(
            InventoryItem.lot_number.ilike(f"%{escaped}%")
            | InventoryItem.notes.ilike(f"%{escaped}%")
        )
    q = apply_sort(q, InventoryItem, sort_by, sort_dir, _INV_SORTABLE)
    return paginate(q, page, page_size)


@router.post("/", status_code=201)
def create_inventory_item(body: InventoryItemCreate, db: Session = Depends(get_db)):
    item = InventoryItem(**body.model_dump())
    db.add(item)
    db.commit()
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
    item = db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return item


@router.patch("/{item_id}")
def update_inventory_item(
    item_id: int, body: InventoryItemUpdate, db: Session = Depends(get_db)
):
    item = db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_inventory_item(item_id: int, db: Session = Depends(get_db)):
    """Soft-delete: set status to 'deleted'."""
    item = db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    item.status = InventoryStatus.deleted
    db.commit()
    return None


@router.get("/{item_id}/history")
def item_history(item_id: int, db: Session = Depends(get_db)):
    """Consumption log for a specific inventory item."""
    return inv_svc.get_item_history(item_id, db)


@router.post("/{item_id}/consume")
def consume_item(item_id: int, body: ConsumeBody, db: Session = Depends(get_db)):
    from lab_manager.services.inventory import InventoryError, NotFoundError

    try:
        return inv_svc.consume(
            item_id, body.quantity, body.consumed_by, body.purpose, db
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InventoryError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{item_id}/transfer")
def transfer_item(item_id: int, body: TransferBody, db: Session = Depends(get_db)):
    from lab_manager.services.inventory import NotFoundError

    try:
        return inv_svc.transfer(item_id, body.location_id, body.transferred_by, db)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{item_id}/adjust")
def adjust_item(item_id: int, body: AdjustBody, db: Session = Depends(get_db)):
    from lab_manager.services.inventory import NotFoundError

    try:
        return inv_svc.adjust(
            item_id, body.new_quantity, body.reason, body.adjusted_by, db
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{item_id}/dispose")
def dispose_item(item_id: int, body: DisposeBody, db: Session = Depends(get_db)):
    from lab_manager.services.inventory import NotFoundError

    try:
        return inv_svc.dispose(item_id, body.reason, body.disposed_by, db)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{item_id}/open")
def open_item(item_id: int, body: OpenBody, db: Session = Depends(get_db)):
    from lab_manager.services.inventory import InventoryError, NotFoundError

    try:
        return inv_svc.open_item(item_id, body.opened_by, db)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InventoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
