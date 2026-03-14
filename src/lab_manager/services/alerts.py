"""Expiry and low-stock alert checks."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from lab_manager.models.inventory import InventoryItem


def get_expiring_items(db: Session, days_ahead: int = 30) -> list[InventoryItem]:
    """Find inventory items expiring within the given number of days."""
    cutoff = date.today() + timedelta(days=days_ahead)
    return (
        db.query(InventoryItem)
        .filter(
            InventoryItem.expiry_date.isnot(None),
            InventoryItem.expiry_date <= cutoff,
            InventoryItem.status == "available",
        )
        .all()
    )


def get_low_stock_items(db: Session, threshold: float = 1) -> list[InventoryItem]:
    """Find items at or below minimum stock level."""
    return (
        db.query(InventoryItem)
        .filter(
            InventoryItem.quantity_on_hand <= threshold,
            InventoryItem.status == "available",
        )
        .all()
    )
