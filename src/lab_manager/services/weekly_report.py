"""Weekly report service — aggregate queries for the past 7 days."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lab_manager.models.alert import Alert
from lab_manager.models.consumption import ConsumptionLog
from lab_manager.models.document import Document, DocumentStatus
from lab_manager.models.equipment import Equipment
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.order import Order, OrderItem
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor
from lab_manager.services.serialization import serialize_value as _iso


def _money(val) -> float:
    """Round a numeric value to 2 decimal places, treating None as 0."""
    if val is None:
        return 0.0
    return round(float(val), 2)


def _default_week_start() -> date:
    """Return the most recent Monday as the default week start."""
    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=today.weekday())


# ---------------------------------------------------------------------------
# 1. New orders received this week
# ---------------------------------------------------------------------------


def _new_orders(db: Session, week_start: date, week_end: date) -> dict:
    rows = db.execute(
        select(
            Order.id,
            Order.po_number,
            Vendor.name.label("vendor_name"),
            Order.order_date,
            Order.status,
            func.coalesce(func.sum(OrderItem.quantity), 0).label("total_quantity"),
            func.coalesce(func.sum(OrderItem.unit_price * OrderItem.quantity), 0).label(
                "total_value"
            ),
        )
        .outerjoin(Vendor, Order.vendor_id == Vendor.id)
        .outerjoin(OrderItem, OrderItem.order_id == Order.id)
        .where(
            Order.created_at
            >= datetime(
                week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc
            )
        )
        .where(
            Order.created_at
            < datetime(week_end.year, week_end.month, week_end.day, tzinfo=timezone.utc)
        )
        .where(Order.status != "deleted")
        .group_by(
            Order.id, Order.po_number, Vendor.name, Order.order_date, Order.status
        )
        .order_by(Order.created_at.desc())
    ).all()

    total_value = sum(_money(r.total_value) for r in rows)
    return {
        "count": len(rows),
        "total_value": total_value,
        "orders": [
            {
                "id": r.id,
                "po_number": r.po_number,
                "vendor_name": r.vendor_name,
                "order_date": _iso(r.order_date),
                "status": r.status,
                "total_value": _money(r.total_value),
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# 2. Inventory consumed (top 10 products)
# ---------------------------------------------------------------------------


def _inventory_consumed(db: Session, week_start: date, week_end: date) -> dict:
    rows = db.execute(
        select(
            Product.name.label("product_name"),
            Product.catalog_number,
            func.coalesce(func.sum(ConsumptionLog.quantity_used), 0).label(
                "total_consumed"
            ),
            InventoryItem.unit.label("unit"),
        )
        .join(InventoryItem, ConsumptionLog.inventory_id == InventoryItem.id)
        .join(Product, ConsumptionLog.product_id == Product.id)
        .where(ConsumptionLog.action == "consume")
        .where(
            ConsumptionLog.created_at
            >= datetime(
                week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc
            )
        )
        .where(
            ConsumptionLog.created_at
            < datetime(week_end.year, week_end.month, week_end.day, tzinfo=timezone.utc)
        )
        .group_by(Product.name, Product.catalog_number, InventoryItem.unit)
        .order_by(func.sum(ConsumptionLog.quantity_used).desc())
        .limit(10)
    ).all()

    total_consumed = sum(float(r.total_consumed) for r in rows)
    return {
        "total_consumed": total_consumed,
        "top_products": [
            {
                "product_name": r.product_name,
                "catalog_number": r.catalog_number,
                "quantity_consumed": float(r.total_consumed),
                "unit": r.unit,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# 3. Documents processed (approved/rejected/pending)
# ---------------------------------------------------------------------------


def _documents_processed(db: Session, week_start: date, week_end: date) -> dict:
    week_start_dt = datetime(
        week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc
    )
    week_end_dt = datetime(
        week_end.year, week_end.month, week_end.day, tzinfo=timezone.utc
    )

    total = (
        db.execute(
            select(func.count(Document.id)).where(
                Document.created_at >= week_start_dt,
                Document.created_at < week_end_dt,
            )
        ).scalar()
        or 0
    )

    by_status_rows = db.execute(
        select(Document.status, func.count(Document.id))
        .where(
            Document.created_at >= week_start_dt,
            Document.created_at < week_end_dt,
        )
        .group_by(Document.status)
    ).all()

    by_status = {row[0]: int(row[1]) for row in by_status_rows}

    return {
        "total": total,
        "approved": by_status.get(DocumentStatus.approved, 0),
        "rejected": by_status.get(DocumentStatus.rejected, 0),
        "pending": by_status.get(DocumentStatus.pending, 0)
        + by_status.get(DocumentStatus.processing, 0)
        + by_status.get(DocumentStatus.needs_review, 0),
        "by_status": by_status,
    }


# ---------------------------------------------------------------------------
# 4. Spending by vendor
# ---------------------------------------------------------------------------


def _spending_by_vendor(db: Session, week_start: date, week_end: date) -> dict:
    week_start_dt = datetime(
        week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc
    )
    week_end_dt = datetime(
        week_end.year, week_end.month, week_end.day, tzinfo=timezone.utc
    )

    rows = db.execute(
        select(
            Vendor.name.label("vendor_name"),
            func.count(func.distinct(Order.id)).label("order_count"),
            func.coalesce(func.sum(OrderItem.unit_price * OrderItem.quantity), 0).label(
                "total_spend"
            ),
        )
        .join(Order, Order.vendor_id == Vendor.id)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(Order.created_at >= week_start_dt)
        .where(Order.created_at < week_end_dt)
        .where(Order.status != "deleted")
        .group_by(Vendor.name)
        .order_by(func.sum(OrderItem.unit_price * OrderItem.quantity).desc())
    ).all()

    total_spend = sum(_money(r.total_spend) for r in rows)
    return {
        "total_spend": total_spend,
        "vendors": [
            {
                "vendor_name": r.vendor_name,
                "order_count": int(r.order_count),
                "total_spend": _money(r.total_spend),
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# 5. Alerts triggered
# ---------------------------------------------------------------------------


def _alerts_triggered(db: Session, week_start: date, week_end: date) -> dict:
    week_start_dt = datetime(
        week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc
    )
    week_end_dt = datetime(
        week_end.year, week_end.month, week_end.day, tzinfo=timezone.utc
    )

    total = (
        db.execute(
            select(func.count(Alert.id)).where(
                Alert.created_at >= week_start_dt,
                Alert.created_at < week_end_dt,
            )
        ).scalar()
        or 0
    )

    by_severity_rows = db.execute(
        select(Alert.severity, func.count(Alert.id))
        .where(
            Alert.created_at >= week_start_dt,
            Alert.created_at < week_end_dt,
        )
        .group_by(Alert.severity)
    ).all()

    by_severity = {row[0]: int(row[1]) for row in by_severity_rows}

    by_type_rows = db.execute(
        select(Alert.alert_type, func.count(Alert.id))
        .where(
            Alert.created_at >= week_start_dt,
            Alert.created_at < week_end_dt,
        )
        .group_by(Alert.alert_type)
    ).all()

    by_type = {row[0]: int(row[1]) for row in by_type_rows}

    unacknowledged = (
        db.execute(
            select(func.count(Alert.id)).where(
                Alert.created_at >= week_start_dt,
                Alert.created_at < week_end_dt,
                Alert.is_acknowledged.is_(False),
            )
        ).scalar()
        or 0
    )

    return {
        "total": total,
        "by_severity": by_severity,
        "by_type": by_type,
        "unacknowledged": unacknowledged,
    }


# ---------------------------------------------------------------------------
# 6. Equipment status changes
# ---------------------------------------------------------------------------


def _equipment_status_changes(db: Session, week_start: date, week_end: date) -> dict:
    week_start_dt = datetime(
        week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc
    )
    week_end_dt = datetime(
        week_end.year, week_end.month, week_end.day, tzinfo=timezone.utc
    )

    # Equipment updated this week (status likely changed)
    updated_rows = db.scalars(
        select(Equipment)
        .where(
            Equipment.updated_at >= week_start_dt,
            Equipment.updated_at < week_end_dt,
        )
        .order_by(Equipment.updated_at.desc())
    ).all()

    by_status_rows = db.execute(
        select(Equipment.status, func.count(Equipment.id))
        .where(
            Equipment.updated_at >= week_start_dt,
            Equipment.updated_at < week_end_dt,
        )
        .group_by(Equipment.status)
    ).all()

    by_status = {row[0]: int(row[1]) for row in by_status_rows}

    changes = [
        {
            "id": eq.id,
            "name": eq.name,
            "status": eq.status,
            "category": eq.category,
            "room": eq.room,
            "updated_at": _iso(eq.updated_at),
        }
        for eq in updated_rows
    ]

    return {
        "total_changed": len(changes),
        "by_status": by_status,
        "changes": changes,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_weekly_report(db: Session, week_start: Optional[date] = None) -> dict:
    """Generate a weekly summary report for the 7-day window starting at *week_start*.

    If *week_start* is None, defaults to the most recent Monday.
    """
    if week_start is None:
        week_start = _default_week_start()
    week_end = week_start + timedelta(days=7)

    return {
        "report_period": {
            "week_start": _iso(week_start),
            "week_end": _iso(week_end),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "new_orders": _new_orders(db, week_start, week_end),
        "inventory_consumed": _inventory_consumed(db, week_start, week_end),
        "documents_processed": _documents_processed(db, week_start, week_end),
        "spending_by_vendor": _spending_by_vendor(db, week_start, week_end),
        "alerts_triggered": _alerts_triggered(db, week_start, week_end),
        "equipment_status_changes": _equipment_status_changes(db, week_start, week_end),
    }
