"""Barcode lookup endpoint — search inventory by scanned barcode value."""

from __future__ import annotations


from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from lab_manager.api.auth import require_permission
from lab_manager.api.deps import get_db
from lab_manager.api.pagination import ilike_col, paginate
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.product import Product

router = APIRouter()


@router.get("/lookup", dependencies=[Depends(require_permission("view_inventory"))])
def barcode_lookup(
    value: str = Query(..., min_length=1, description="Scanned barcode or QR value"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Search inventory items by barcode value.

    Matches against product catalog_number (exact first, then partial),
    product name, lot_number, and CAS number.
    """
    # Exact catalog_number match (highest priority)
    exact_q = (
        select(InventoryItem)
        .join(Product, InventoryItem.product_id == Product.id)
        .options(selectinload(InventoryItem.product).selectinload(Product.vendor))
        .where(Product.catalog_number == value)
    )
    exact_result = paginate(exact_q, db, page, page_size)
    if exact_result["total"] > 0:
        return {**exact_result, "match_type": "catalog_number_exact"}

    # Partial / fuzzy match across multiple fields
    fuzzy_q = (
        select(InventoryItem)
        .join(Product, InventoryItem.product_id == Product.id)
        .options(selectinload(InventoryItem.product).selectinload(Product.vendor))
        .where(
            ilike_col(Product.catalog_number, value)
            | ilike_col(Product.name, value)
            | ilike_col(Product.cas_number, value)
            | ilike_col(InventoryItem.lot_number, value)
        )
    )
    fuzzy_result = paginate(fuzzy_q, db, page, page_size)
    if fuzzy_result["total"] > 0:
        return {**fuzzy_result, "match_type": "partial"}

    return {
        "items": [],
        "total": 0,
        "page": page,
        "page_size": page_size,
        "pages": 0,
        "match_type": "none",
    }
