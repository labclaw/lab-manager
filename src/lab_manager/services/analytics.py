"""Analytics service — aggregate queries for dashboard and reports."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from lab_manager.models.document import Document, DocumentStatus
from lab_manager.models.inventory import InventoryItem, InventoryStatus
from lab_manager.models.location import StorageLocation
from lab_manager.models.order import Order, OrderItem
from lab_manager.models.product import Product
from lab_manager.models.staff import Staff
from lab_manager.models.vendor import Vendor
from lab_manager.services.serialization import serialize_value as _iso

# Statuses considered "active" for stock and expiry calculations.
_ACTIVE_STATUSES = [InventoryStatus.available, InventoryStatus.opened]


def _money(val) -> float:
    """Round a numeric value to 2 decimal places, treating None as 0."""
    if val is None:
        return 0.0
    return round(float(val), 2)


# ---------------------------------------------------------------------------
# 1. Dashboard summary
# ---------------------------------------------------------------------------


def dashboard_summary(db: Session) -> dict:
    total_products = db.query(func.count(Product.id)).scalar() or 0
    total_vendors = db.query(func.count(Vendor.id)).scalar() or 0
    total_orders = db.query(func.count(Order.id)).scalar() or 0
    total_inventory_items = db.query(func.count(InventoryItem.id)).scalar() or 0
    total_documents = db.query(func.count(Document.id)).scalar() or 0
    total_staff = db.query(func.count(Staff.id)).scalar() or 0

    documents_pending_review = (
        db.query(func.count(Document.id))
        .filter(
            Document.status.in_(
                [
                    DocumentStatus.pending,
                    DocumentStatus.needs_review,
                    DocumentStatus.extracted,
                ]
            )
        )
        .scalar()
        or 0
    )
    documents_approved = (
        db.query(func.count(Document.id))
        .filter(Document.status == DocumentStatus.approved)
        .scalar()
        or 0
    )

    orders_by_status = dict(
        db.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    )

    inventory_by_status = dict(
        db.query(InventoryItem.status, func.count(InventoryItem.id))
        .group_by(InventoryItem.status)
        .all()
    )

    # Recent 10 orders with vendor name
    recent_rows = (
        db.query(Order, Vendor.name)
        .outerjoin(Vendor, Order.vendor_id == Vendor.id)
        .order_by(Order.id.desc())
        .limit(10)
        .all()
    )
    recent_orders = []
    for order, vendor_name in recent_rows:
        recent_orders.append(
            {
                "id": order.id,
                "po_number": order.po_number,
                "vendor_name": vendor_name,
                "status": order.status,
                "order_date": _iso(order.order_date),
            }
        )

    # Items expiring within 30 days
    cutoff = date.today() + timedelta(days=30)
    expiring_rows = (
        db.query(InventoryItem, Product.name.label("product_name"))
        .outerjoin(Product, InventoryItem.product_id == Product.id)
        .filter(
            InventoryItem.expiry_date.isnot(None),
            InventoryItem.expiry_date <= cutoff,
            InventoryItem.status.in_(_ACTIVE_STATUSES),
        )
        .order_by(InventoryItem.expiry_date)
        .limit(100)
        .all()
    )
    expiring_soon = []
    for item, product_name in expiring_rows:
        expiring_soon.append(
            {
                "id": item.id,
                "product_name": product_name,
                "lot_number": item.lot_number,
                "quantity_on_hand": item.quantity_on_hand,
                "expiry_date": _iso(item.expiry_date),
            }
        )

    # Low stock: products where total stock is below min_stock_level
    # Only counts products that have min_stock_level explicitly set.
    stock_sub = (
        db.query(
            InventoryItem.product_id,
            func.sum(InventoryItem.quantity_on_hand).label("total"),
        )
        .filter(InventoryItem.status.in_(_ACTIVE_STATUSES))
        .group_by(InventoryItem.product_id)
        .subquery()
    )
    low_stock_count = (
        db.query(func.count(Product.id))
        .join(stock_sub, Product.id == stock_sub.c.product_id)
        .filter(
            Product.min_stock_level.isnot(None),
            stock_sub.c.total < Product.min_stock_level,
        )
        .scalar()
        or 0
    )

    return {
        "total_products": total_products,
        "total_vendors": total_vendors,
        "total_orders": total_orders,
        "total_inventory_items": total_inventory_items,
        "total_documents": total_documents,
        "total_staff": total_staff,
        "documents_pending_review": documents_pending_review,
        "documents_approved": documents_approved,
        "orders_by_status": orders_by_status,
        "inventory_by_status": inventory_by_status,
        "recent_orders": recent_orders,
        "expiring_soon": expiring_soon,
        "low_stock_count": low_stock_count,
    }


# ---------------------------------------------------------------------------
# 2. Spending by vendor
# ---------------------------------------------------------------------------


def spending_by_vendor(
    db: Session,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[dict]:
    q = (
        db.query(
            Vendor.name.label("vendor_name"),
            func.count(func.distinct(Order.id)).label("order_count"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("item_count"),
            func.coalesce(func.sum(OrderItem.unit_price * OrderItem.quantity), 0).label(
                "total_spend"
            ),
        )
        .join(Order, Order.vendor_id == Vendor.id)
        .join(OrderItem, OrderItem.order_id == Order.id)
    )
    if date_from:
        q = q.filter(Order.order_date >= date_from)
    if date_to:
        q = q.filter(Order.order_date <= date_to)
    q = q.group_by(Vendor.name).order_by(
        func.sum(OrderItem.unit_price * OrderItem.quantity).desc()
    )

    return [
        {
            "vendor_name": row.vendor_name,
            "order_count": int(row.order_count),
            "item_count": int(row.item_count),
            "total_spend": _money(row.total_spend),
        }
        for row in q.all()
    ]


# ---------------------------------------------------------------------------
# 3. Spending by month
# ---------------------------------------------------------------------------


def spending_by_month(db: Session, months: int = 12) -> list[dict]:
    cutoff = date.today() - timedelta(days=months * 30)
    from sqlalchemy import extract

    year_expr = extract("year", Order.order_date)
    month_expr = extract("month", Order.order_date)
    q = (
        db.query(
            year_expr.label("yr"),
            month_expr.label("mo"),
            func.count(func.distinct(Order.id)).label("order_count"),
            func.coalesce(func.sum(OrderItem.unit_price * OrderItem.quantity), 0).label(
                "total_spend"
            ),
        )
        .join(OrderItem, OrderItem.order_id == Order.id)
        .filter(Order.order_date.isnot(None), Order.order_date >= cutoff)
        .group_by(year_expr, month_expr)
        .order_by(year_expr, month_expr)
    )
    return [
        {
            "month": f"{int(row.yr)}-{int(row.mo):02d}",
            "order_count": int(row.order_count),
            "total_spend": _money(row.total_spend),
        }
        for row in q.all()
    ]


# ---------------------------------------------------------------------------
# 4. Inventory value
# ---------------------------------------------------------------------------


def inventory_value(db: Session) -> dict:
    total = (
        db.query(
            func.coalesce(
                func.sum(InventoryItem.quantity_on_hand * OrderItem.unit_price), 0
            )
        )
        .join(OrderItem, InventoryItem.order_item_id == OrderItem.id)
        .scalar()
    )
    item_count = db.query(func.count(InventoryItem.id)).scalar() or 0
    return {
        "total_value": _money(total),
        "item_count": item_count,
    }


# ---------------------------------------------------------------------------
# 5. Top products
# ---------------------------------------------------------------------------


def top_products(db: Session, limit: int = 20) -> list[dict]:
    rows = (
        db.query(
            OrderItem.catalog_number,
            OrderItem.description,
            Vendor.name.label("vendor"),
            func.count(OrderItem.id).label("times_ordered"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("total_quantity"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .outerjoin(Vendor, Order.vendor_id == Vendor.id)
        .filter(OrderItem.catalog_number.isnot(None))
        .group_by(OrderItem.catalog_number, OrderItem.description, Vendor.name)
        .order_by(func.count(OrderItem.id).desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "catalog_number": r.catalog_number,
            "name": r.description,
            "vendor": r.vendor,
            "times_ordered": int(r.times_ordered),
            "total_quantity": float(r.total_quantity),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 6. Order history
# ---------------------------------------------------------------------------


def order_history(
    db: Session,
    vendor_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[dict]:
    q = (
        db.query(
            Order,
            Vendor.name.label("vendor_name"),
            func.count(OrderItem.id).label("item_count"),
            func.coalesce(func.sum(OrderItem.unit_price * OrderItem.quantity), 0).label(
                "total_value"
            ),
        )
        .outerjoin(Vendor, Order.vendor_id == Vendor.id)
        .outerjoin(OrderItem, OrderItem.order_id == Order.id)
    )
    if vendor_id is not None:
        q = q.filter(Order.vendor_id == vendor_id)
    if date_from:
        q = q.filter(Order.order_date >= date_from)
    if date_to:
        q = q.filter(Order.order_date <= date_to)

    q = q.group_by(Order.id, Vendor.name).order_by(Order.id.desc()).limit(500)

    return [
        {
            "id": order.id,
            "po_number": order.po_number,
            "vendor_name": vendor_name,
            "order_date": _iso(order.order_date),
            "status": order.status,
            "item_count": int(item_count),
            "total_value": _money(total_value),
        }
        for order, vendor_name, item_count, total_value in q.all()
    ]


# ---------------------------------------------------------------------------
# 7. Staff activity
# ---------------------------------------------------------------------------


def staff_activity(db: Session) -> list[dict]:
    # Count orders received per person (by received_by field)
    rows = (
        db.query(
            Order.received_by,
            func.count(Order.id).label("orders_received"),
            func.max(Order.order_date).label("last_active"),
        )
        .filter(Order.received_by.isnot(None))
        .group_by(Order.received_by)
        .order_by(func.count(Order.id).desc())
        .all()
    )
    return [
        {
            "name": r.received_by,
            "orders_received": int(r.orders_received),
            "last_active": _iso(r.last_active),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 8. Vendor summary
# ---------------------------------------------------------------------------


def vendor_summary(db: Session, vendor_id: int) -> Optional[dict]:
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        return None

    products_supplied = (
        db.query(func.count(Product.id)).filter(Product.vendor_id == vendor_id).scalar()
        or 0
    )

    order_count = (
        db.query(func.count(Order.id)).filter(Order.vendor_id == vendor_id).scalar()
        or 0
    )

    total_spend_val = (
        db.query(func.coalesce(func.sum(OrderItem.unit_price * OrderItem.quantity), 0))
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Order.vendor_id == vendor_id)
        .scalar()
    )

    last_order_date = (
        db.query(func.max(Order.order_date))
        .filter(Order.vendor_id == vendor_id)
        .scalar()
    )

    return {
        "id": vendor.id,
        "name": vendor.name,
        "website": vendor.website,
        "phone": vendor.phone,
        "email": vendor.email,
        "products_supplied": products_supplied,
        "order_count": order_count,
        "total_spend": _money(total_spend_val),
        "last_order_date": _iso(last_order_date),
    }


# ---------------------------------------------------------------------------
# 9. Inventory report
# ---------------------------------------------------------------------------


def inventory_report(db: Session, location_id: Optional[int] = None) -> list[dict]:
    q = (
        db.query(
            InventoryItem,
            Product.name.label("product_name"),
            Product.catalog_number.label("catalog_number"),
            Vendor.name.label("vendor_name"),
            StorageLocation.name.label("location_name"),
        )
        .outerjoin(Product, InventoryItem.product_id == Product.id)
        .outerjoin(Vendor, Product.vendor_id == Vendor.id)
        .outerjoin(StorageLocation, InventoryItem.location_id == StorageLocation.id)
    )
    if location_id is not None:
        q = q.filter(InventoryItem.location_id == location_id)

    q = q.order_by(InventoryItem.id).limit(1000)

    return [
        {
            "id": item.id,
            "product_name": product_name,
            "catalog_number": catalog_number,
            "vendor_name": vendor_name,
            "location_name": location_name,
            "lot_number": item.lot_number,
            "quantity_on_hand": item.quantity_on_hand,
            "unit": item.unit,
            "expiry_date": _iso(item.expiry_date),
            "status": item.status,
        }
        for item, product_name, catalog_number, vendor_name, location_name in q.all()
    ]


# ---------------------------------------------------------------------------
# 10. Document processing stats
# ---------------------------------------------------------------------------


def document_processing_stats(db: Session) -> dict:
    total = db.query(func.count(Document.id)).scalar() or 0

    by_status = dict(
        db.query(Document.status, func.count(Document.id))
        .group_by(Document.status)
        .all()
    )

    by_type = dict(
        db.query(Document.document_type, func.count(Document.id))
        .group_by(Document.document_type)
        .all()
    )

    avg_confidence = (
        db.query(func.avg(Document.extraction_confidence))
        .filter(Document.extraction_confidence.isnot(None))
        .scalar()
    )

    rejected_count = by_status.get(DocumentStatus.rejected, 0)

    return {
        "total_documents": total,
        "by_status": by_status,
        "by_type": by_type,
        "average_confidence": _money(avg_confidence) if avg_confidence else None,
        "rejected_count": rejected_count,
        "rejection_rate": _money(rejected_count / total * 100) if total > 0 else 0.0,
    }
