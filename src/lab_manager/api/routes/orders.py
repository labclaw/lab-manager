"""Order CRUD endpoints."""

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
from lab_manager.exceptions import NotFoundError, ValidationError
from lab_manager.models.order import Order, OrderItem, OrderStatus
from lab_manager.services.orders import build_duplicate_warning, find_duplicate_po
from lab_manager.services.search import index_order_record

router = APIRouter()


def _get_order_item_or_raise(db: Session, order_id: int, item_id: int) -> OrderItem:
    item = db.scalars(
        select(OrderItem).where(OrderItem.id == item_id, OrderItem.order_id == order_id)
    ).first()
    if not item:
        raise NotFoundError("Order item", item_id)
    return item


_ORDER_SORTABLE = {
    "id",
    "created_at",
    "updated_at",
    "po_number",
    "order_date",
    "ship_date",
    "received_date",
    "status",
    "vendor_id",
}

_VALID_ORDER_STATUSES = {s.value for s in OrderStatus}
_MAX_ORDER_ITEM_QUANTITY = 1_000_000


# --- Order schemas ---


class OrderCreate(BaseModel):
    po_number: Optional[str] = Field(default=None, max_length=100)
    vendor_id: Optional[int] = None
    order_date: Optional[date] = None
    ship_date: Optional[date] = None
    received_date: Optional[date] = None
    received_by: Optional[str] = Field(default=None, max_length=200)
    status: str = OrderStatus.pending
    delivery_number: Optional[str] = Field(default=None, max_length=100)
    invoice_number: Optional[str] = Field(default=None, max_length=100)
    document_id: Optional[int] = None
    extra: dict = {}

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in _VALID_ORDER_STATUSES:
            raise ValueError(f"status must be one of {_VALID_ORDER_STATUSES}")
        return v


class OrderUpdate(BaseModel):
    po_number: Optional[str] = Field(default=None, max_length=100)
    vendor_id: Optional[int] = None
    order_date: Optional[date] = None
    ship_date: Optional[date] = None
    received_date: Optional[date] = None
    received_by: Optional[str] = Field(default=None, max_length=200)
    status: Optional[str] = None
    delivery_number: Optional[str] = Field(default=None, max_length=100)
    invoice_number: Optional[str] = Field(default=None, max_length=100)
    document_id: Optional[int] = None
    extra: Optional[dict] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_ORDER_STATUSES:
            raise ValueError(f"status must be one of {_VALID_ORDER_STATUSES}")
        return v


# --- OrderItem schemas ---


class OrderItemCreate(BaseModel):
    catalog_number: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)
    quantity: Decimal = Field(
        default=Decimal("1"), gt=0, le=Decimal(str(_MAX_ORDER_ITEM_QUANTITY))
    )
    unit: Optional[str] = Field(default=None, max_length=50)
    lot_number: Optional[str] = Field(default=None, max_length=100)
    batch_number: Optional[str] = Field(default=None, max_length=100)
    unit_price: Optional[Decimal] = Field(default=None, ge=0)
    product_id: Optional[int] = None
    extra: dict = {}


class OrderItemUpdate(BaseModel):
    catalog_number: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)
    quantity: Optional[Decimal] = Field(
        default=None, gt=0, le=Decimal(str(_MAX_ORDER_ITEM_QUANTITY))
    )
    unit: Optional[str] = Field(default=None, max_length=50)
    lot_number: Optional[str] = Field(default=None, max_length=100)
    batch_number: Optional[str] = Field(default=None, max_length=100)
    unit_price: Optional[Decimal] = Field(default=None, ge=0)
    product_id: Optional[int] = None
    extra: Optional[dict] = None


class OrderResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    po_number: Optional[str] = None
    vendor_id: Optional[int] = None
    order_date: Optional[date] = None
    ship_date: Optional[date] = None
    received_date: Optional[date] = None
    received_by: Optional[str] = None
    status: str
    delivery_number: Optional[str] = None
    invoice_number: Optional[str] = None
    document_id: Optional[int] = None
    extra: dict = {}
    created_at: datetime | None = None
    updated_at: datetime | None = None


# =====================
#  Order endpoints
# =====================


@router.get("/")
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    vendor_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    status_group: Optional[str] = Query(
        None, description="Filter by status group: 'active', 'past', or 'drafts'"
    ),
    po_number: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    received_by: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    q = select(Order).options(selectinload(Order.vendor))
    if vendor_id is not None:
        q = q.where(Order.vendor_id == vendor_id)
    if status:
        q = q.where(Order.status == status)
    elif status_group:
        # Map status_group to status filters
        if status_group == "active":
            q = q.where(Order.status.notin_(["received", "cancelled", "deleted"]))
        elif status_group == "past":
            q = q.where(Order.status.in_(["received", "cancelled"]))
        elif status_group == "drafts":
            q = q.where(Order.status == "draft")
    if po_number:
        q = q.where(ilike_col(Order.po_number, po_number))
    if date_from:
        q = q.where(Order.order_date >= date_from)
    if date_to:
        q = q.where(Order.order_date <= date_to)
    if received_by:
        q = q.where(ilike_col(Order.received_by, received_by))
    q = apply_sort(q, Order, sort_by, sort_dir, _ORDER_SORTABLE)
    return paginate(q, db, page, page_size)


@router.post(
    "/", status_code=201, dependencies=[Depends(require_permission("create_orders"))]
)
def create_order(body: OrderCreate, db: Session = Depends(get_db)):
    order = Order(**body.model_dump())
    db.add(order)
    db.flush()
    db.refresh(order)
    index_order_record(order)

    # Duplicate PO# check — warn but never block (OCR may re-scan same doc).
    # The warning is embedded in the response under _duplicate_warning so callers
    # (review UI, tests) can surface it without treating it as an error (409).
    duplicate_warning = None
    if body.po_number:
        dupes = find_duplicate_po(
            body.po_number,
            body.vendor_id,
            db,
            exclude_order_id=order.id,
        )
        if dupes:
            duplicate_warning = build_duplicate_warning(dupes)

    if duplicate_warning:
        return {"order": order, "_duplicate_warning": duplicate_warning}
    return order


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Order, order_id, "Order")


@router.patch(
    "/{order_id}", dependencies=[Depends(require_permission("approve_orders"))]
)
def update_order(order_id: int, body: OrderUpdate, db: Session = Depends(get_db)):
    order = get_or_404(db, Order, order_id, "Order")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(order, key, value)
    db.flush()
    db.refresh(order)
    index_order_record(order)
    return order


@router.delete(
    "/{order_id}",
    status_code=204,
    dependencies=[Depends(require_permission("delete_records"))],
)
def delete_order(order_id: int, db: Session = Depends(get_db)):
    """Soft-delete: set status to 'deleted'."""
    order = get_or_404(db, Order, order_id, "Order")
    order.status = OrderStatus.deleted
    db.flush()
    return None


# =====================
#  Order Items sub-endpoints
# =====================


@router.get("/{order_id}/items")
def list_order_items(
    order_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    catalog_number: Optional[str] = Query(None),
    lot_number: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    get_or_404(db, Order, order_id, "Order")
    q = select(OrderItem).where(OrderItem.order_id == order_id)
    if catalog_number:
        q = q.where(ilike_col(OrderItem.catalog_number, catalog_number))
    if lot_number:
        q = q.where(ilike_col(OrderItem.lot_number, lot_number))
    q = q.order_by(OrderItem.id)
    return paginate(q, db, page, page_size)


@router.post(
    "/{order_id}/items",
    status_code=201,
    dependencies=[Depends(require_permission("create_orders"))],
)
def create_order_item(
    order_id: int, body: OrderItemCreate, db: Session = Depends(get_db)
):
    get_or_404(db, Order, order_id, "Order")
    item = OrderItem(**body.model_dump())
    item.order_id = order_id
    db.add(item)
    db.flush()
    db.refresh(item)
    return item


@router.get("/{order_id}/items/{item_id}")
def get_order_item(order_id: int, item_id: int, db: Session = Depends(get_db)):
    return _get_order_item_or_raise(db, order_id, item_id)


@router.patch(
    "/{order_id}/items/{item_id}",
    dependencies=[Depends(require_permission("approve_orders"))],
)
def update_order_item(
    order_id: int, item_id: int, body: OrderItemUpdate, db: Session = Depends(get_db)
):
    item = _get_order_item_or_raise(db, order_id, item_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.flush()
    db.refresh(item)
    return item


@router.delete(
    "/{order_id}/items/{item_id}",
    status_code=204,
    dependencies=[Depends(require_permission("delete_records"))],
)
def delete_order_item(order_id: int, item_id: int, db: Session = Depends(get_db)):
    item = _get_order_item_or_raise(db, order_id, item_id)
    db.delete(item)
    db.flush()
    return None


# =====================
#  Receive shipment
# =====================


class ReceiveItemEntry(BaseModel):
    order_item_id: Optional[int] = None
    product_id: Optional[int] = None
    quantity: Decimal = Field(
        default=Decimal("1"), gt=0, le=Decimal(str(_MAX_ORDER_ITEM_QUANTITY))
    )
    lot_number: Optional[str] = Field(default=None, max_length=100)
    unit: Optional[str] = Field(default=None, max_length=50)
    expiry_date: Optional[date] = None


class ReceiveBody(BaseModel):
    items: list[ReceiveItemEntry]
    location_id: Optional[int] = None
    received_by: str = Field(max_length=200)


@router.post(
    "/{order_id}/receive",
    status_code=201,
    dependencies=[Depends(require_permission("receive_shipments"))],
)
def receive_order(order_id: int, body: ReceiveBody, db: Session = Depends(get_db)):
    """Receive a shipment — creates inventory records from order items."""
    from lab_manager.services import inventory as inv_svc

    items_dicts = [item.model_dump() for item in body.items]
    return inv_svc.receive_items(
        order_id, items_dicts, body.location_id, body.received_by, db
    )
