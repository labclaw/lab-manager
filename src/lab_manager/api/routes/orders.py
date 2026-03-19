"""Order CRUD endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import apply_sort, ilike_col, paginate
from lab_manager.exceptions import NotFoundError
from lab_manager.models.order import Order, OrderItem, OrderStatus

router = APIRouter()


def _get_order_item_or_raise(db: Session, order_id: int, item_id: int) -> OrderItem:
    item = db.query(OrderItem).filter(OrderItem.id == item_id, OrderItem.order_id == order_id).first()
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


# --- Order schemas ---


class OrderCreate(BaseModel):
    po_number: str | None = None
    vendor_id: int | None = None
    order_date: date | None = None
    ship_date: date | None = None
    received_date: date | None = None
    received_by: str | None = None
    status: str = OrderStatus.pending
    delivery_number: str | None = None
    invoice_number: str | None = None
    document_id: int | None = None
    extra: dict = {}


class OrderUpdate(BaseModel):
    po_number: str | None = None
    vendor_id: int | None = None
    order_date: date | None = None
    ship_date: date | None = None
    received_date: date | None = None
    received_by: str | None = None
    status: str | None = None
    delivery_number: str | None = None
    invoice_number: str | None = None
    document_id: int | None = None
    extra: dict | None = None


# --- OrderItem schemas ---


class OrderItemCreate(BaseModel):
    catalog_number: str | None = None
    description: str | None = None
    quantity: float = 1
    unit: str | None = None
    lot_number: str | None = None
    batch_number: str | None = None
    unit_price: float | None = None
    product_id: int | None = None
    extra: dict = {}


class OrderItemUpdate(BaseModel):
    catalog_number: str | None = None
    description: str | None = None
    quantity: float | None = None
    unit: str | None = None
    lot_number: str | None = None
    batch_number: str | None = None
    unit_price: float | None = None
    product_id: int | None = None
    extra: dict | None = None


# =====================
#  Order endpoints
# =====================


@router.get("/")
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    vendor_id: int | None = Query(None),
    status: str | None = Query(None),
    po_number: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    received_by: str | None = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    q = db.query(Order)
    if vendor_id is not None:
        q = q.filter(Order.vendor_id == vendor_id)
    if status:
        q = q.filter(Order.status == status)
    if po_number:
        q = q.filter(ilike_col(Order.po_number, po_number))
    if date_from:
        q = q.filter(Order.order_date >= date_from)
    if date_to:
        q = q.filter(Order.order_date <= date_to)
    if received_by:
        q = q.filter(ilike_col(Order.received_by, received_by))
    q = apply_sort(q, Order, sort_by, sort_dir, _ORDER_SORTABLE)
    return paginate(q, page, page_size)


@router.post("/", status_code=201)
def create_order(body: OrderCreate, db: Session = Depends(get_db)):
    order = Order(**body.model_dump())
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.get("/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Order, order_id, "Order")


@router.patch("/{order_id}")
def update_order(order_id: int, body: OrderUpdate, db: Session = Depends(get_db)):
    order = get_or_404(db, Order, order_id, "Order")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(order, key, value)
    db.commit()
    db.refresh(order)
    return order


@router.delete("/{order_id}", status_code=204)
def delete_order(order_id: int, db: Session = Depends(get_db)):
    """Soft-delete: set status to 'deleted'."""
    order = get_or_404(db, Order, order_id, "Order")
    order.status = OrderStatus.deleted
    db.commit()
    return None


# =====================
#  Order Items sub-endpoints
# =====================


@router.get("/{order_id}/items")
def list_order_items(
    order_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    catalog_number: str | None = Query(None),
    lot_number: str | None = Query(None),
    db: Session = Depends(get_db),
):
    get_or_404(db, Order, order_id, "Order")
    q = db.query(OrderItem).filter(OrderItem.order_id == order_id)
    if catalog_number:
        q = q.filter(ilike_col(OrderItem.catalog_number, catalog_number))
    if lot_number:
        q = q.filter(ilike_col(OrderItem.lot_number, lot_number))
    q = q.order_by(OrderItem.id)
    return paginate(q, page, page_size)


@router.post("/{order_id}/items", status_code=201)
def create_order_item(order_id: int, body: OrderItemCreate, db: Session = Depends(get_db)):
    get_or_404(db, Order, order_id, "Order")
    item = OrderItem(**body.model_dump())
    item.order_id = order_id
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{order_id}/items/{item_id}")
def get_order_item(order_id: int, item_id: int, db: Session = Depends(get_db)):
    return _get_order_item_or_raise(db, order_id, item_id)


@router.patch("/{order_id}/items/{item_id}")
def update_order_item(order_id: int, item_id: int, body: OrderItemUpdate, db: Session = Depends(get_db)):
    item = _get_order_item_or_raise(db, order_id, item_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{order_id}/items/{item_id}", status_code=204)
def delete_order_item(order_id: int, item_id: int, db: Session = Depends(get_db)):
    item = _get_order_item_or_raise(db, order_id, item_id)
    db.delete(item)
    db.commit()
    return None


# =====================
#  Receive shipment
# =====================


class ReceiveItemEntry(BaseModel):
    order_item_id: int | None = None
    product_id: int | None = None
    quantity: float = 1
    lot_number: str | None = None
    unit: str | None = None
    expiry_date: date | None = None


class ReceiveBody(BaseModel):
    items: list[ReceiveItemEntry]
    location_id: int
    received_by: str


@router.post("/{order_id}/receive", status_code=201)
def receive_order(order_id: int, body: ReceiveBody, db: Session = Depends(get_db)):
    """Receive a shipment — creates inventory records from order items."""
    from lab_manager.services import inventory as inv_svc

    items_dicts = [item.model_dump() for item in body.items]
    return inv_svc.receive_items(order_id, items_dicts, body.location_id, body.received_by, db)
