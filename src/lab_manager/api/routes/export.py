"""CSV export endpoints."""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.services import analytics as svc
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor

router = APIRouter()


def _csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    """Build a StreamingResponse with CSV content from a list of dicts."""
    buf = io.StringIO()
    if not rows:
        buf.write("")
    else:
        writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/inventory.csv")
def export_inventory(
    location_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    rows = svc.inventory_report(db, location_id=location_id)
    return _csv_response(rows, "inventory.csv")


@router.get("/orders.csv")
def export_orders(
    vendor_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    rows = svc.order_history(
        db, vendor_id=vendor_id, date_from=date_from, date_to=date_to
    )
    return _csv_response(rows, "orders.csv")


@router.get("/products.csv")
def export_products(db: Session = Depends(get_db)):
    products = db.query(Product).order_by(Product.id).all()
    rows = [
        {
            "id": p.id,
            "catalog_number": p.catalog_number,
            "name": p.name,
            "vendor_id": p.vendor_id,
            "category": p.category,
            "cas_number": p.cas_number,
            "storage_temp": p.storage_temp,
            "unit": p.unit,
        }
        for p in products
    ]
    return _csv_response(rows, "products.csv")


@router.get("/vendors.csv")
def export_vendors(db: Session = Depends(get_db)):
    vendors = db.query(Vendor).order_by(Vendor.id).all()
    rows = [
        {
            "id": v.id,
            "name": v.name,
            "website": v.website,
            "phone": v.phone,
            "email": v.email,
        }
        for v in vendors
    ]
    return _csv_response(rows, "vendors.csv")
