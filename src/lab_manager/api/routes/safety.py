"""Safety endpoints — PPE requirements and inventory safety scanning."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db, get_or_404
from lab_manager.models.product import Product
from lab_manager.services.safety import (
    get_product_safety_info,
    get_waste_disposal_guide,
)

router = APIRouter()


@router.get("/ppe/{product_id}")
def get_product_ppe(product_id: int, db: Session = Depends(get_db)):
    """Return PPE requirements for a product based on its hazard codes."""
    product = get_or_404(db, Product, product_id, "Product")
    return get_product_safety_info(product)


@router.get("/disposal/{hazard_code}")
def get_disposal_guide(hazard_code: str):
    """Return waste disposal instructions for a GHS hazard code."""
    return {
        "hazard_code": hazard_code.upper(),
        "disposal_guide": get_waste_disposal_guide(hazard_code),
    }


@router.get("/inventory-scan")
def inventory_safety_scan(db: Session = Depends(get_db)):
    """Scan inventory for hazardous items without proper safety data."""
    from lab_manager.services.safety import check_inventory_safety

    return {"warnings": check_inventory_safety(db)}
