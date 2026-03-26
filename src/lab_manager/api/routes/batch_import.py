"""Batch CSV import endpoints for products and inventory."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.exceptions import ValidationError
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor

router = APIRouter()

_MAX_ROWS = 5000
_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


def _parse_csv(content: bytes) -> list[dict[str, str]]:
    """Parse CSV bytes into a list of dicts. Raises on format errors."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValidationError("CSV file has no header row")

    rows = []
    for i, row in enumerate(reader, start=2):
        if i > _MAX_ROWS + 1:
            raise ValidationError(f"CSV exceeds maximum of {_MAX_ROWS} rows")
        rows.append(row)
    return rows


def _clean(value: str | None) -> str | None:
    """Strip whitespace, return None for empty strings."""
    if value is None:
        return None
    v = value.strip()
    return v if v else None


def _parse_decimal(value: str | None) -> Decimal | None:
    if not value or not value.strip():
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation:
        return None


def _parse_date(value: str | None) -> date | None:
    if not value or not value.strip():
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


@router.post("/products")
def import_products(
    file: UploadFile,
    db: Session = Depends(get_db),
):
    """Import products from CSV.

    Required columns: catalog_number, name
    Optional columns: vendor_name, category, cas_number, unit, storage_temp,
                      min_stock_level, max_stock_level, reorder_quantity,
                      shelf_life_days, hazard_info, is_hazardous, is_controlled
    """
    content = file.file.read()
    if len(content) > _MAX_FILE_BYTES:
        raise ValidationError(f"File exceeds {_MAX_FILE_BYTES // 1024 // 1024}MB limit")

    rows = _parse_csv(content)
    if not rows:
        raise ValidationError("CSV file is empty")

    created = 0
    skipped = 0
    errors: list[dict] = []

    # Cache vendor lookups
    vendor_cache: dict[str, int | None] = {}

    for i, row in enumerate(rows, start=2):
        catalog = _clean(row.get("catalog_number"))
        name = _clean(row.get("name"))

        if not catalog or not name:
            errors.append({"row": i, "error": "Missing catalog_number or name"})
            continue

        # Resolve vendor
        vendor_id = None
        vendor_name = _clean(row.get("vendor_name"))
        if vendor_name:
            if vendor_name not in vendor_cache:
                vendor = db.execute(
                    select(Vendor).where(Vendor.name == vendor_name)
                ).scalar_one_or_none()
                vendor_cache[vendor_name] = vendor.id if vendor else None
            vendor_id = vendor_cache[vendor_name]

        # Check for duplicate
        existing = db.execute(
            select(Product).where(
                Product.catalog_number == catalog,
                Product.vendor_id == vendor_id,
            )
        ).scalar_one_or_none()
        if existing:
            skipped += 1
            continue

        product = Product(
            catalog_number=catalog,
            name=name,
            vendor_id=vendor_id,
            category=_clean(row.get("category")),
            cas_number=_clean(row.get("cas_number")),
            unit=_clean(row.get("unit")),
            storage_temp=_clean(row.get("storage_temp")),
            min_stock_level=_parse_decimal(row.get("min_stock_level")),
            max_stock_level=_parse_decimal(row.get("max_stock_level")),
            reorder_quantity=_parse_decimal(row.get("reorder_quantity")),
            shelf_life_days=int(row["shelf_life_days"])
            if _clean(row.get("shelf_life_days"))
            else None,
            hazard_info=_clean(row.get("hazard_info")),
            is_hazardous=row.get("is_hazardous", "").strip().lower() in ("true", "1", "yes"),
            is_controlled=row.get("is_controlled", "").strip().lower()
            in ("true", "1", "yes"),
        )
        db.add(product)
        created += 1

    db.flush()
    return {
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "total_rows": len(rows),
    }


@router.post("/inventory")
def import_inventory(
    file: UploadFile,
    db: Session = Depends(get_db),
):
    """Import inventory items from CSV.

    Required columns: product_catalog_number, quantity
    Optional columns: vendor_name, lot_number, unit, expiry_date,
                      location_name, notes, received_by
    """
    content = file.file.read()
    if len(content) > _MAX_FILE_BYTES:
        raise ValidationError(f"File exceeds {_MAX_FILE_BYTES // 1024 // 1024}MB limit")

    rows = _parse_csv(content)
    if not rows:
        raise ValidationError("CSV file is empty")

    created = 0
    errors: list[dict] = []

    for i, row in enumerate(rows, start=2):
        catalog = _clean(row.get("product_catalog_number"))
        qty_str = _clean(row.get("quantity"))

        if not catalog:
            errors.append({"row": i, "error": "Missing product_catalog_number"})
            continue

        qty = _parse_decimal(qty_str)
        if qty is None or qty < 0:
            errors.append({"row": i, "error": f"Invalid quantity: {qty_str}"})
            continue

        # Resolve product
        product_q = select(Product).where(Product.catalog_number == catalog)
        vendor_name = _clean(row.get("vendor_name"))
        if vendor_name:
            vendor = db.execute(
                select(Vendor).where(Vendor.name == vendor_name)
            ).scalar_one_or_none()
            if vendor:
                product_q = product_q.where(Product.vendor_id == vendor.id)

        product = db.execute(product_q).scalar_one_or_none()
        if not product:
            errors.append({"row": i, "error": f"Product not found: {catalog}"})
            continue

        # Resolve location
        location_id = None
        loc_name = _clean(row.get("location_name"))
        if loc_name:
            from lab_manager.models.location import StorageLocation

            loc = db.execute(
                select(StorageLocation).where(StorageLocation.name == loc_name)
            ).scalar_one_or_none()
            if loc:
                location_id = loc.id

        item = InventoryItem(
            product_id=product.id,
            location_id=location_id,
            lot_number=_clean(row.get("lot_number")),
            quantity_on_hand=qty,
            unit=_clean(row.get("unit")) or product.unit,
            expiry_date=_parse_date(row.get("expiry_date")),
            notes=_clean(row.get("notes")),
            received_by=_clean(row.get("received_by")),
            status="available",
        )
        db.add(item)
        created += 1

    db.flush()
    return {
        "created": created,
        "errors": errors,
        "total_rows": len(rows),
    }
