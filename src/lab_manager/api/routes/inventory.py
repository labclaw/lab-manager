"""Inventory CRUD and lifecycle endpoints."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from lab_manager.api.auth import require_permission
from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import apply_sort, ilike_col, paginate
from lab_manager.models.inventory import InventoryItem, InventoryStatus
from lab_manager.models.product import Product
from lab_manager.services import inventory as inv_svc
from lab_manager.services.search import index_inventory_record
from lab_manager.services.vendor_urls import get_reorder_url

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
    quantity_on_hand: Decimal = Field(default=Decimal("0"), ge=0)
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
    quantity_on_hand: Optional[Decimal] = None
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
    quantity: Decimal = Field(gt=0)
    consumed_by: str = Field(max_length=200)
    purpose: Optional[str] = Field(default=None, max_length=500)


class TransferBody(BaseModel):
    location_id: int
    transferred_by: str = Field(max_length=200)


class AdjustBody(BaseModel):
    new_quantity: Decimal = Field(ge=0)
    reason: str = Field(max_length=500)
    adjusted_by: str = Field(max_length=200)


class DisposeBody(BaseModel):
    reason: str = Field(max_length=500)
    disposed_by: str = Field(max_length=200)


class OpenBody(BaseModel):
    opened_by: str = Field(max_length=200)


class InventoryItemResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    product_id: int
    location_id: Optional[int] = None
    lot_number: Optional[str] = None
    quantity_on_hand: Decimal
    unit: Optional[str] = None
    expiry_date: Optional[date] = None
    opened_date: Optional[date] = None
    status: str
    notes: Optional[str] = None
    received_by: Optional[str] = None
    order_item_id: Optional[int] = None
    extra: dict = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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
    q = select(InventoryItem).options(
        selectinload(InventoryItem.product).selectinload(Product.vendor)
    )
    if product_id is not None:
        q = q.where(InventoryItem.product_id == product_id)
    if location_id is not None:
        q = q.where(InventoryItem.location_id == location_id)
    if status:
        q = q.where(InventoryItem.status == status)
    if expiring_before:
        q = q.where(InventoryItem.expiry_date <= expiring_before)
    if search:
        q = q.where(
            ilike_col(InventoryItem.lot_number, search)
            | ilike_col(InventoryItem.notes, search)
        )
    q = apply_sort(q, InventoryItem, sort_by, sort_dir, _INV_SORTABLE)
    return paginate(q, db, page, page_size)


@router.post(
    "/",
    status_code=201,
    dependencies=[Depends(require_permission("receive_shipments"))],
)
def create_inventory_item(body: InventoryItemCreate, db: Session = Depends(get_db)):
    item = InventoryItem(**body.model_dump())
    db.add(item)
    db.flush()
    db.refresh(item)
    index_inventory_record(item)
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


@router.get("/{item_id}", response_model=InventoryItemResponse)
def get_inventory_item(item_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, InventoryItem, item_id, "Inventory item")


@router.patch(
    "/{item_id}", dependencies=[Depends(require_permission("receive_shipments"))]
)
def update_inventory_item(
    item_id: int, body: InventoryItemUpdate, db: Session = Depends(get_db)
):
    item = get_or_404(db, InventoryItem, item_id, "Inventory item")
    if item.status in (
        InventoryStatus.deleted,
        InventoryStatus.disposed,
        InventoryStatus.depleted,
    ):
        raise ValidationError(
            f"Cannot modify inventory item with status '{item.status.value}'"
        )
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.flush()
    db.refresh(item)
    index_inventory_record(item)
    return item


@router.delete(
    "/{item_id}",
    status_code=204,
    dependencies=[Depends(require_permission("delete_records"))],
)
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


@router.post(
    "/{item_id}/consume", dependencies=[Depends(require_permission("log_consumption"))]
)
def consume_item(item_id: int, body: ConsumeBody, db: Session = Depends(get_db)):
    return inv_svc.consume(item_id, body.quantity, body.consumed_by, body.purpose, db)


@router.post(
    "/{item_id}/transfer", dependencies=[Depends(require_permission("log_consumption"))]
)
def transfer_item(item_id: int, body: TransferBody, db: Session = Depends(get_db)):
    return inv_svc.transfer(item_id, body.location_id, body.transferred_by, db)


@router.post(
    "/{item_id}/adjust", dependencies=[Depends(require_permission("log_consumption"))]
)
def adjust_item(item_id: int, body: AdjustBody, db: Session = Depends(get_db)):
    return inv_svc.adjust(item_id, body.new_quantity, body.reason, body.adjusted_by, db)


@router.post(
    "/{item_id}/dispose", dependencies=[Depends(require_permission("log_consumption"))]
)
def dispose_item(item_id: int, body: DisposeBody, db: Session = Depends(get_db)):
    return inv_svc.dispose(item_id, body.reason, body.disposed_by, db)


@router.post(
    "/{item_id}/open", dependencies=[Depends(require_permission("log_consumption"))]
)
def open_item(item_id: int, body: OpenBody, db: Session = Depends(get_db)):
    return inv_svc.open_item(item_id, body.opened_by, db)


@router.get("/{item_id}/reorder-url")
def get_reorder_url_endpoint(item_id: int, db: Session = Depends(get_db)):
    """Generate a vendor website URL for reordering this item's product."""
    item = get_or_404(db, InventoryItem, item_id, "Inventory item")
    product = item.product
    vendor_name = getattr(product, "vendor", None)
    vendor_name = getattr(vendor_name, "name", None) if vendor_name else None
    catalog = getattr(product, "catalog_number", None) if product else None
    url = get_reorder_url(vendor_name or "", catalog or "")
    return {
        "url": url,
        "vendor": vendor_name,
        "catalog_number": catalog,
    }
