"""CSV export endpoints."""

from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor
from lab_manager.services import analytics as svc

router = APIRouter()

_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")

_Db = Depends(get_db)
_ExportLocationId = Query(None)
_ExportDateFrom = Query(None)
_ExportDateTo = Query(None)


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
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/inventory.csv")
def export_inventory(
    location_id: int | None = _ExportLocationId,
    db: Session = _Db,
):
    rows = svc.inventory_report(db, location_id=location_id)
    return _csv_response(rows, "inventory.csv")


@router.get("/orders.csv")
def export_orders(
    vendor_id: int | None = _ExportLocationId,
    date_from: date | None = _ExportDateFrom,
    date_to: date | None = _ExportDateTo,
    db: Session = _Db,
):
    rows = svc.order_history(db, vendor_id=vendor_id, date_from=date_from, date_to=date_to)
    return _csv_response(rows, "orders.csv")


@router.get("/products.csv")
def export_products(db: Session = _Db):
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
    query = db.query(Product).order_by(Product.id).yield_per(100)

    def generate():
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        yield output.getvalue()
        output.truncate(0)
        output.seek(0)

        for product in query:
            row = _escape_row({f: getattr(product, f, None) for f in fieldnames})
            writer.writerow(row)
            yield output.getvalue()
            output.truncate(0)
            output.seek(0)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="products.csv"'},
    )


@router.get("/vendors.csv")
def export_vendors(db: Session = _Db):
    fieldnames = ["id", "name", "website", "phone", "email", "notes"]
    query = db.query(Vendor).order_by(Vendor.id).yield_per(100)

    def generate():
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        yield output.getvalue()
        output.truncate(0)
        output.seek(0)

        for vendor in query:
            row = _escape_row({f: getattr(vendor, f, None) for f in fieldnames})
            writer.writerow(row)
            yield output.getvalue()
            output.truncate(0)
            output.seek(0)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="vendors.csv"'},
    )
