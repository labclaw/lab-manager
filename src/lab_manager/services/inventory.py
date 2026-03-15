"""Inventory lifecycle service — core lab operations."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from lab_manager.models.consumption import ConsumptionAction, ConsumptionLog
from lab_manager.models.inventory import InventoryItem, InventoryStatus
from lab_manager.models.order import Order, OrderItem, OrderStatus
from lab_manager.models.product import Product


class InventoryError(Exception):
    pass


class NotFoundError(InventoryError):
    pass


def _log_consumption(
    db: Session,
    *,
    inventory_id: int,
    product_id: Optional[int],
    quantity_used: float,
    quantity_remaining: float,
    consumed_by: str,
    action: str,
    purpose: Optional[str] = None,
) -> ConsumptionLog:
    """Write an entry to the consumption log."""
    entry = ConsumptionLog(
        inventory_id=inventory_id,
        product_id=product_id,
        quantity_used=quantity_used,
        quantity_remaining=quantity_remaining,
        consumed_by=consumed_by,
        action=action,
        purpose=purpose,
    )
    db.add(entry)
    return entry


def _get_inventory_or_404(db: Session, inventory_id: int) -> InventoryItem:
    item = db.get(InventoryItem, inventory_id)
    if not item:
        raise NotFoundError("Inventory item not found")
    return item


# ---------------------------------------------------------------------------
# Receive shipment
# ---------------------------------------------------------------------------


def receive_items(
    order_id: int,
    items_received: list[dict],
    location_id: int,
    received_by: str,
    db: Session,
) -> list[InventoryItem]:
    """Create inventory records from a received order.

    items_received: list of dicts with keys:
        order_item_id, quantity, lot_number (optional), expiry_date (optional)
    """
    order = db.get(Order, order_id)
    if not order:
        raise NotFoundError("Order not found")

    created = []
    today = date.today()

    for ri in items_received:
        order_item_id = ri.get("order_item_id")
        order_item = db.get(OrderItem, order_item_id) if order_item_id else None
        if order_item and order_item.order_id != order_id:
            raise InventoryError(
                f"Order item {order_item_id} belongs to order {order_item.order_id}, not {order_id}"
            )

        inv = InventoryItem(
            product_id=order_item.product_id if order_item else ri.get("product_id"),
            location_id=location_id,
            lot_number=ri.get("lot_number")
            or (order_item.lot_number if order_item else None),
            quantity_on_hand=ri.get("quantity", 1),
            unit=ri.get("unit") or (order_item.unit if order_item else None),
            expiry_date=ri.get("expiry_date"),
            status=InventoryStatus.available,
            received_by=received_by,
            order_item_id=order_item_id,
        )
        db.add(inv)
        db.flush()  # get inv.id

        _log_consumption(
            db,
            inventory_id=inv.id,
            product_id=inv.product_id,
            quantity_used=0,
            quantity_remaining=inv.quantity_on_hand,
            consumed_by=received_by,
            action=ConsumptionAction.receive,
            purpose=f"Received from order #{order_id}",
        )
        created.append(inv)

    order.status = OrderStatus.received
    order.received_date = today
    order.received_by = received_by
    db.commit()

    for inv in created:
        db.refresh(inv)
    return created


# ---------------------------------------------------------------------------
# Consume
# ---------------------------------------------------------------------------


def consume(
    inventory_id: int,
    quantity: float,
    consumed_by: str,
    purpose: Optional[str],
    db: Session,
) -> InventoryItem:
    """Reduce quantity on hand. Mark depleted if 0."""
    quantity = Decimal(str(quantity))
    item = _get_inventory_or_404(db, inventory_id)

    if item.status in (InventoryStatus.disposed, InventoryStatus.depleted):
        raise InventoryError(f"Cannot consume from {item.status} item")
    if quantity <= 0:
        raise InventoryError("Quantity must be positive")
    if quantity > item.quantity_on_hand:
        raise InventoryError(
            f"Insufficient stock: {item.quantity_on_hand} available, {quantity} requested"
        )

    item.quantity_on_hand -= quantity
    if item.quantity_on_hand <= Decimal("0.0001"):
        item.status = InventoryStatus.depleted

    _log_consumption(
        db,
        inventory_id=item.id,
        product_id=item.product_id,
        quantity_used=quantity,
        quantity_remaining=item.quantity_on_hand,
        consumed_by=consumed_by,
        action=ConsumptionAction.consume,
        purpose=purpose,
    )
    db.commit()
    db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# Transfer
# ---------------------------------------------------------------------------


def transfer(
    inventory_id: int,
    new_location_id: int,
    transferred_by: str,
    db: Session,
) -> InventoryItem:
    """Move item to a different location."""
    item = _get_inventory_or_404(db, inventory_id)
    old_location_id = item.location_id
    item.location_id = new_location_id

    _log_consumption(
        db,
        inventory_id=item.id,
        product_id=item.product_id,
        quantity_used=0,
        quantity_remaining=item.quantity_on_hand,
        consumed_by=transferred_by,
        action=ConsumptionAction.transfer,
        purpose=f"Moved from location {old_location_id} to {new_location_id}",
    )
    db.commit()
    db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# Adjust (cycle count)
# ---------------------------------------------------------------------------


def adjust(
    inventory_id: int,
    new_quantity: float,
    reason: str,
    adjusted_by: str,
    db: Session,
) -> InventoryItem:
    """Physical count adjustment."""
    new_quantity = Decimal(str(new_quantity))
    item = _get_inventory_or_404(db, inventory_id)
    old_quantity = item.quantity_on_hand
    delta = new_quantity - old_quantity

    item.quantity_on_hand = new_quantity
    if new_quantity <= Decimal("0.0001"):
        item.status = InventoryStatus.depleted
    elif item.status == InventoryStatus.depleted and new_quantity > 0:
        item.status = InventoryStatus.available

    _log_consumption(
        db,
        inventory_id=item.id,
        product_id=item.product_id,
        quantity_used=-delta,  # negative means stock added
        quantity_remaining=new_quantity,
        consumed_by=adjusted_by,
        action=ConsumptionAction.adjust,
        purpose=f"Cycle count: {old_quantity} -> {new_quantity}. Reason: {reason}",
    )
    db.commit()
    db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# Dispose
# ---------------------------------------------------------------------------


def dispose(
    inventory_id: int,
    reason: str,
    disposed_by: str,
    db: Session,
) -> InventoryItem:
    """Mark item as disposed (expired, contaminated, etc)."""
    item = _get_inventory_or_404(db, inventory_id)

    remaining = item.quantity_on_hand
    item.quantity_on_hand = Decimal(0)
    item.status = InventoryStatus.disposed

    _log_consumption(
        db,
        inventory_id=item.id,
        product_id=item.product_id,
        quantity_used=remaining,
        quantity_remaining=0,
        consumed_by=disposed_by,
        action=ConsumptionAction.dispose,
        purpose=reason,
    )
    db.commit()
    db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# Open item
# ---------------------------------------------------------------------------


def open_item(
    inventory_id: int,
    opened_by: str,
    db: Session,
) -> InventoryItem:
    """Mark item as opened (track opened_date for stability)."""
    item = _get_inventory_or_404(db, inventory_id)

    if item.opened_date is not None:
        raise InventoryError("Item is already opened")

    item.opened_date = date.today()
    item.status = InventoryStatus.opened

    _log_consumption(
        db,
        inventory_id=item.id,
        product_id=item.product_id,
        quantity_used=0,
        quantity_remaining=item.quantity_on_hand,
        consumed_by=opened_by,
        action=ConsumptionAction.open,
        purpose="Item opened",
    )
    db.commit()
    db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def get_stock_level(product_id: int, db: Session) -> dict:
    """Total quantity on hand for a product across all locations."""
    result = (
        db.query(func.sum(InventoryItem.quantity_on_hand))
        .filter(
            InventoryItem.product_id == product_id,
            InventoryItem.status.notin_([InventoryStatus.disposed]),
        )
        .scalar()
    )
    return {"product_id": product_id, "total_quantity": result or 0}


def get_low_stock(db: Session) -> list[dict]:
    """Products where total stock is below min_stock_level."""
    rows = (
        db.query(
            Product.id,
            Product.name,
            Product.catalog_number,
            Product.min_stock_level,
            func.coalesce(func.sum(InventoryItem.quantity_on_hand), 0).label(
                "total_qty"
            ),
        )
        .outerjoin(
            InventoryItem,
            (InventoryItem.product_id == Product.id)
            & (InventoryItem.status.notin_([InventoryStatus.disposed])),
        )
        .filter(Product.min_stock_level.isnot(None))
        .group_by(
            Product.id, Product.name, Product.catalog_number, Product.min_stock_level
        )
        .all()
    )
    return [
        {
            "product_id": r.id,
            "name": r.name,
            "catalog_number": r.catalog_number,
            "min_stock_level": r.min_stock_level,
            "total_quantity": float(r.total_qty),
        }
        for r in rows
        if float(r.total_qty) < r.min_stock_level
    ]


def get_expiring(db: Session, days: int = 30) -> list[InventoryItem]:
    """Items expiring within N days."""
    cutoff = date.today() + timedelta(days=days)
    return (
        db.query(InventoryItem)
        .filter(
            InventoryItem.expiry_date.isnot(None),
            InventoryItem.expiry_date <= cutoff,
            InventoryItem.status.notin_(
                [InventoryStatus.disposed, InventoryStatus.depleted]
            ),
        )
        .all()
    )


def get_consumption_history(
    product_id: int,
    db: Session,
    days: int = 90,
) -> list[ConsumptionLog]:
    """Consumption log entries for a product within the last N days."""
    from lab_manager.models.base import utcnow

    cutoff = utcnow() - timedelta(days=days)
    return (
        db.query(ConsumptionLog)
        .filter(
            ConsumptionLog.product_id == product_id,
            ConsumptionLog.created_at >= cutoff,
        )
        .order_by(ConsumptionLog.created_at.desc())
        .all()
    )


def get_item_history(
    inventory_id: int,
    db: Session,
) -> list[ConsumptionLog]:
    """All consumption log entries for a specific inventory item."""
    return (
        db.query(ConsumptionLog)
        .filter(ConsumptionLog.inventory_id == inventory_id)
        .order_by(ConsumptionLog.created_at.desc())
        .all()
    )
