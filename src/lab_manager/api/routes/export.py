"""CSV export endpoints."""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.api.auth import require_permission
from lab_manager.api.deps import get_db
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor
from lab_manager.services import analytics as svc

router = APIRouter(dependencies=[Depends(require_permission("export_data"))])

_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def _escape_cell(value):
    """Prefix formula-like cell values with a single quote to prevent Excel injection.

    Minus is only safe when followed by a digit (e.g., '-20C' freezer temps).
    '-cmd' style strings are still escaped as they could be formula injection.
    """
    if value is None:
        return ""
    if isinstance(value, str) and value:
        first = value[0]
        if first in ("=", "+", "@", "\t", "\r", "\n"):
            return "'" + value
        if first == "-" and len(value) > 1 and not value[1].isdigit():
            return "'" + value
    return value


def _escape_row(row: dict) -> dict:
    return {k: _escape_cell(v) for k, v in row.items()}


def _csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    """Build a StreamingResponse with CSV content from a list of dicts."""
    buf = io.StringIO()
    if not rows:
        buf.write("")
    else:
        writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows([_escape_row(r) for r in rows])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/inventory")
@router.get("/inventory.csv", include_in_schema=False)
@router.get("/inventory/csv", include_in_schema=False)
def export_inventory(
    location_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    rows = svc.inventory_report(db, location_id=location_id)
    return _csv_response(rows, "inventory.csv")


@router.get("/orders")
@router.get("/orders.csv", include_in_schema=False)
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


@router.get("/products")
@router.get("/products.csv", include_in_schema=False)
def export_products(db: Session = Depends(get_db)):
    fieldnames = [
        "id",
        "catalog_number",
        "name",
        "vendor_id",
        "category",
        "cas_number",
        "storage_temp",
        "unit",
        "hazard_info",
        "min_stock_level",
        "is_hazardous",
        "is_controlled",
    ]
    # Eagerly materialize all rows before returning StreamingResponse.
    # The get_db() middleware closes the session after the handler returns,
    # so lazy iteration via yield_per would fail with a closed-session error.
    products = db.scalars(select(Product).order_by(Product.id)).all()
    rows = [_escape_row({f: getattr(p, f, None) for f in fieldnames}) for p in products]
    return _csv_response(rows, "products.csv")


@router.get("/vendors")
@router.get("/vendors.csv", include_in_schema=False)
def export_vendors(db: Session = Depends(get_db)):
    fieldnames = ["id", "name", "website", "phone", "email", "notes"]
    # Eagerly materialize all rows before returning StreamingResponse.
    # The get_db() middleware closes the session after the handler returns,
    # so lazy iteration via yield_per would fail with a closed-session error.
    vendors = db.scalars(select(Vendor).order_by(Vendor.id)).all()
    rows = [_escape_row({f: getattr(v, f, None) for f in fieldnames}) for v in vendors]
    return _csv_response(rows, "vendors.csv")
