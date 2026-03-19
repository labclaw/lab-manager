"""Order service — business logic for order management."""

from __future__ import annotations

from sqlalchemy.orm import Session

from lab_manager.models.order import Order


def find_duplicate_po(
    po_number: str,
    vendor_id: int | None,
    db: Session,
    *,
    exclude_order_id: int | None = None,
) -> list[Order]:
    """Check whether a PO number already exists for the given vendor.

    Rules:
    - If vendor_id is provided, a duplicate is the same (po_number, vendor_id) pair.
    - If vendor_id is None, match only on po_number (vendor-agnostic).
    - Cancelled / deleted orders are excluded — they are no longer active.
    - exclude_order_id lets callers skip the order being updated (PATCH).

    Returns a list of conflicting Order objects (empty list = no duplicate).
    """
    if not po_number or not po_number.strip():
        return []

    q = db.query(Order).filter(
        Order.po_number == po_number.strip(),
        Order.status.notin_(["cancelled", "deleted"]),
    )

    if vendor_id is not None:
        q = q.filter(Order.vendor_id == vendor_id)

    if exclude_order_id is not None:
        q = q.filter(Order.id != exclude_order_id)

    return q.all()


def build_duplicate_warning(duplicates: list[Order]) -> dict:
    """Build a structured warning payload for duplicate PO numbers."""
    return {
        "warning": "duplicate_po_number",
        "message": (
            f"PO number already exists in {len(duplicates)} order(s). "
            "The order was created but may be a duplicate from OCR re-scan."
        ),
        "duplicate_order_ids": [o.id for o in duplicates],
    }
