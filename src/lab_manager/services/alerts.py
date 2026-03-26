"""Expiry, low-stock, and operational alert checks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lab_manager.models.alert import Alert
from lab_manager.models.document import Document, DocumentStatus
from lab_manager.models.inventory import ACTIVE_STATUSES, InventoryItem
from lab_manager.models.order import Order, OrderStatus
from lab_manager.models.product import Product


# ---------------------------------------------------------------------------
# Raw query helpers (kept for backward compat)
# ---------------------------------------------------------------------------


def get_expiring_items(db: Session, days_ahead: int = 30) -> list[InventoryItem]:
    """Find inventory items expiring within the given number of days."""
    cutoff = datetime.now(timezone.utc).date() + timedelta(days=days_ahead)
    return db.scalars(
        select(InventoryItem).where(
            InventoryItem.expiry_date.isnot(None),
            InventoryItem.expiry_date <= cutoff,
            InventoryItem.status.in_(ACTIVE_STATUSES),
        )
    ).all()


def get_low_stock_items(db: Session, threshold: float = 1) -> list[InventoryItem]:
    """Find items at or below minimum stock level."""
    return db.scalars(
        select(InventoryItem).where(
            InventoryItem.quantity_on_hand <= threshold,
            InventoryItem.status.in_(ACTIVE_STATUSES),
        )
    ).all()


# ---------------------------------------------------------------------------
# Full alert check — returns structured alert dicts
# ---------------------------------------------------------------------------


def _check_expired(db: Session) -> list[dict]:
    """Items past their expiry_date (critical)."""
    today = datetime.now(timezone.utc).date()
    items = db.scalars(
        select(InventoryItem)
        .where(
            InventoryItem.expiry_date.isnot(None),
            InventoryItem.expiry_date < today,
            InventoryItem.status.in_(ACTIVE_STATUSES),
        )
        .limit(500)
    ).all()
    return [
        {
            "type": "expired",
            "severity": "critical",
            "message": f"Inventory item {it.id} (lot {it.lot_number}) expired on {it.expiry_date}",
            "entity_type": "inventory",
            "entity_id": it.id,
            "details": {
                "expiry_date": it.expiry_date.isoformat(),
                "lot_number": it.lot_number,
                "product_id": it.product_id,
            },
        }
        for it in items
    ]


def _check_expiring_soon(db: Session, days: int = 30) -> list[dict]:
    """Items expiring within *days* but NOT yet expired (warning)."""
    today = datetime.now(timezone.utc).date()
    cutoff = today + timedelta(days=days)
    items = db.scalars(
        select(InventoryItem)
        .where(
            InventoryItem.expiry_date.isnot(None),
            InventoryItem.expiry_date >= today,
            InventoryItem.expiry_date <= cutoff,
            InventoryItem.status.in_(ACTIVE_STATUSES),
        )
        .limit(500)
    ).all()
    return [
        {
            "type": "expiring_soon",
            "severity": "warning",
            "message": (
                f"Inventory item {it.id} (lot {it.lot_number}) expires on {it.expiry_date}"
            ),
            "entity_type": "inventory",
            "entity_id": it.id,
            "details": {
                "expiry_date": it.expiry_date.isoformat(),
                "days_remaining": (it.expiry_date - today).days,
                "lot_number": it.lot_number,
                "product_id": it.product_id,
            },
        }
        for it in items
    ]


def _check_out_of_stock(db: Session) -> list[dict]:
    """Products with zero total inventory that have min_stock_level set (critical)."""
    # Sub-query: sum of quantity_on_hand per product for available items.
    stock = (
        select(
            InventoryItem.product_id,
            func.coalesce(func.sum(InventoryItem.quantity_on_hand), 0).label("total"),
        )
        .where(InventoryItem.status.in_(ACTIVE_STATUSES))
        .group_by(InventoryItem.product_id)
        .subquery()
    )
    # Products that either have zero stock or no inventory rows at all.
    # Only alert for products with min_stock_level set (tracked products).
    products_with_stock = db.execute(
        select(Product, stock.c.total)
        .outerjoin(stock, Product.id == stock.c.product_id)
        .where(Product.min_stock_level.isnot(None))
        .where((stock.c.total == 0) | (stock.c.total.is_(None)))
    ).all()
    return [
        {
            "type": "out_of_stock",
            "severity": "critical",
            "message": f"Product {p.id} ({p.catalog_number}) is out of stock",
            "entity_type": "product",
            "entity_id": p.id,
            "details": {
                "catalog_number": p.catalog_number,
                "name": p.name,
            },
        }
        for p, _ in products_with_stock
    ]


def _check_low_stock(db: Session) -> list[dict]:
    """Products with total inventory below their min_stock_level (warning).

    Only checks products that have min_stock_level explicitly set.
    """
    stock = (
        select(
            InventoryItem.product_id,
            func.sum(InventoryItem.quantity_on_hand).label("total"),
        )
        .where(InventoryItem.status.in_(ACTIVE_STATUSES))
        .group_by(InventoryItem.product_id)
        .subquery()
    )
    rows = db.execute(
        select(Product, stock.c.total)
        .join(stock, Product.id == stock.c.product_id)
        .where(
            Product.min_stock_level.isnot(None),
            stock.c.total > 0,
            stock.c.total <= Product.min_stock_level,
        )
    ).all()
    return [
        {
            "type": "low_stock",
            "severity": "warning",
            "message": (
                f"Product {p.id} ({p.catalog_number}) has low stock: {float(total)}"
            ),
            "entity_type": "product",
            "entity_id": p.id,
            "details": {
                "catalog_number": p.catalog_number,
                "name": p.name,
                "total_stock": float(total),
            },
        }
        for p, total in rows
    ]


def _check_pending_review(db: Session) -> list[dict]:
    """Documents not yet approved awaiting human review (info)."""
    docs = db.scalars(
        select(Document)
        .where(
            Document.status.in_(
                [
                    DocumentStatus.pending,
                    DocumentStatus.needs_review,
                    DocumentStatus.extracted,
                ]
            )
        )
        .limit(200)
    ).all()
    return [
        {
            "type": "pending_review",
            "severity": "info",
            "message": f"Document {d.id} ({d.file_name}) is pending review",
            "entity_type": "document",
            "entity_id": d.id,
            "details": {
                "file_name": d.file_name,
                "document_type": d.document_type,
                "vendor_name": d.vendor_name,
            },
        }
        for d in docs
    ]


def _check_stale_orders(db: Session, stale_days: int = 30) -> list[dict]:
    """Orders stuck in 'pending' for more than *stale_days* (warning)."""
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=stale_days)
    orders = db.scalars(
        select(Order)
        .where(
            Order.status == OrderStatus.pending,
            Order.created_at
            <= datetime(cutoff.year, cutoff.month, cutoff.day, tzinfo=timezone.utc),
        )
        .limit(500)
    ).all()
    return [
        {
            "type": "stale_orders",
            "severity": "warning",
            "message": f"Order {o.id} (PO {o.po_number}) has been pending for over {stale_days} days",
            "entity_type": "order",
            "entity_id": o.id,
            "details": {
                "po_number": o.po_number,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            },
        }
        for o in orders
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_all_alerts(db: Session) -> list[dict]:
    """Run all alert checks and return a flat list of alert dicts."""
    alerts: list[dict] = []
    alerts.extend(_check_expired(db))
    alerts.extend(_check_expiring_soon(db))
    alerts.extend(_check_out_of_stock(db))
    alerts.extend(_check_low_stock(db))
    alerts.extend(_check_pending_review(db))
    alerts.extend(_check_stale_orders(db))
    return alerts


def get_alert_summary(db: Session, alerts: list[dict] | None = None) -> dict:
    """Return counts grouped by type and severity."""
    if alerts is None:
        alerts = check_all_alerts(db)
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {"critical": 0, "warning": 0, "info": 0}
    for a in alerts:
        by_type[a["type"]] = by_type.get(a["type"], 0) + 1
        by_severity[a["severity"]] = by_severity.get(a["severity"], 0) + 1
    return {
        "total": len(alerts),
        "critical": by_severity["critical"],
        "warning": by_severity["warning"],
        "info": by_severity["info"],
        "by_type": by_type,
    }


def persist_alerts(db: Session) -> tuple[list[Alert], list[dict]]:
    """Run checks and create Alert rows for any new (unresolved) conditions.

    Returns (newly_created_alerts, all_current_alert_dicts).
    """
    current = check_all_alerts(db)
    # Build a set of (entity_type, entity_id, alert_type) for existing unresolved alerts.
    existing = db.execute(
        select(Alert.entity_type, Alert.entity_id, Alert.alert_type).where(
            Alert.is_resolved.is_(False)
        )
    ).all()
    existing_keys = {(e[0], e[1], e[2]) for e in existing}

    created: list[Alert] = []
    for a in current:
        key = (a["entity_type"], a["entity_id"], a["type"])
        if key in existing_keys:
            continue
        alert = Alert(
            alert_type=a["type"],
            severity=a["severity"],
            message=a["message"],
            entity_type=a["entity_type"],
            entity_id=a["entity_id"],
        )
        db.add(alert)
        created.append(alert)

    if created:
        db.flush()
        for a in created:
            db.refresh(a)
    return created, current
