"""Consumption forecast service — depletion prediction and reorder recommendations."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lab_manager.models.consumption import ConsumptionAction, ConsumptionLog
from lab_manager.models.inventory import ACTIVE_STATUSES, InventoryItem
from lab_manager.models.product import Product

logger = logging.getLogger(__name__)

# Confidence thresholds (days of consumption data).
_HIGH_CONFIDENCE_DAYS = 30
_MEDIUM_CONFIDENCE_DAYS = 14

# Reorder lead-time buffer in days.
_DEFAULT_LEAD_TIME_DAYS = 7


def predict_depletion(product_id: int, db: Session) -> dict:
    """Predict when a product will run out based on consumption history.

    Uses the last 90 days of consume-action logs to compute a mean daily
    consumption rate, then projects current inventory forward.

    Returns a dict with keys:
        product_id, current_qty, daily_rate, days_until_empty,
        predicted_empty_date, confidence
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=90)

    # Sum total consumed quantity for *consume* actions only.
    result = db.execute(
        select(
            func.coalesce(func.sum(ConsumptionLog.quantity_used), 0).label(
                "total_consumed"
            ),
            func.count(func.distinct(func.date(ConsumptionLog.created_at))).label(
                "days_with_data"
            ),
            func.min(ConsumptionLog.created_at).label("earliest"),
            func.max(ConsumptionLog.created_at).label("latest"),
        ).where(
            ConsumptionLog.product_id == product_id,
            ConsumptionLog.action == ConsumptionAction.consume,
            ConsumptionLog.created_at >= cutoff,
        )
    ).one()

    total_consumed = float(result.total_consumed)
    days_with_data = int(result.days_with_data)

    # Current inventory across all active items.
    current_qty_row = db.execute(
        select(func.coalesce(func.sum(InventoryItem.quantity_on_hand), 0)).where(
            InventoryItem.product_id == product_id,
            InventoryItem.status.in_(ACTIVE_STATUSES),
        )
    ).scalar()
    current_qty = float(current_qty_row)

    # No consumption data at all.
    if days_with_data == 0 or total_consumed == 0:
        return {
            "product_id": product_id,
            "current_qty": current_qty,
            "daily_rate": 0.0,
            "days_until_empty": None,
            "predicted_empty_date": None,
            "confidence": "no_data" if days_with_data == 0 else "zero_consumption",
        }

    daily_rate = total_consumed / days_with_data
    days_until_empty = current_qty / daily_rate if daily_rate > 0 else None

    # Confidence based on data coverage.
    if days_with_data >= _HIGH_CONFIDENCE_DAYS:
        confidence = "high"
    elif days_with_data >= _MEDIUM_CONFIDENCE_DAYS:
        confidence = "medium"
    else:
        confidence = "low"

    predicted_empty_date: Optional[str] = None
    if days_until_empty is not None:
        predicted_date = now.date() + timedelta(days=int(days_until_empty))
        predicted_empty_date = predicted_date.isoformat()

    return {
        "product_id": product_id,
        "current_qty": current_qty,
        "daily_rate": round(daily_rate, 4),
        "days_until_empty": round(days_until_empty, 1)
        if days_until_empty is not None
        else None,
        "predicted_empty_date": predicted_empty_date,
        "confidence": confidence,
    }


def predict_batch(product_ids: list[int], db: Session) -> list[dict]:
    """Run depletion prediction for multiple products, sorted by urgency."""
    results = [predict_depletion(pid, db) for pid in product_ids]
    # Sort: items with days_until_empty come first (ascending), nulls last.
    results.sort(
        key=lambda r: (
            r["days_until_empty"] if r["days_until_empty"] is not None else float("inf")
        )
    )
    return results


def get_reorder_recommendations(db: Session) -> list[dict]:
    """Identify products that need reordering.

    A product needs reorder when:
    - It has min_stock_level set AND
    - Current inventory is already below min_stock_level, OR
    - Predicted empty date is within the reorder lead-time window.
    """
    products = db.scalars(
        select(Product).where(
            Product.min_stock_level.isnot(None),
            Product.is_active.is_(True),
        )
    ).all()

    product_ids = [p.id for p in products]
    if not product_ids:
        return []

    predictions = predict_batch(product_ids, db)
    pred_by_id = {p["product_id"]: p for p in predictions}

    today = date.today()
    reorder_cutoff = today + timedelta(days=_DEFAULT_LEAD_TIME_DAYS)
    recommendations: list[dict] = []

    for prod in products:
        pred = pred_by_id.get(prod.id)
        if not pred:
            continue

        current_qty = pred["current_qty"]
        min_stock = float(prod.min_stock_level) if prod.min_stock_level else 0
        reorder_qty = float(prod.reorder_quantity) if prod.reorder_quantity else None

        needs_reorder = False
        reason = ""

        if current_qty <= min_stock:
            needs_reorder = True
            reason = "below_min_stock"
        elif pred["predicted_empty_date"]:
            empty_date = date.fromisoformat(pred["predicted_empty_date"])
            if empty_date <= reorder_cutoff:
                needs_reorder = True
                reason = "depleting_soon"

        if needs_reorder:
            recommendations.append(
                {
                    "product_id": prod.id,
                    "product_name": prod.name,
                    "catalog_number": prod.catalog_number,
                    "current_qty": current_qty,
                    "min_stock_level": min_stock,
                    "daily_rate": pred["daily_rate"],
                    "days_until_empty": pred["days_until_empty"],
                    "predicted_empty_date": pred["predicted_empty_date"],
                    "confidence": pred["confidence"],
                    "reason": reason,
                    "suggested_order_quantity": reorder_qty,
                }
            )

    return recommendations
