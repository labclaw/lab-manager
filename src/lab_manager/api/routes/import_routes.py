"""CSV bulk import endpoints for inventory, products, and vendors."""

from __future__ import annotations

import csv
import io
import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlmodel import Session

from lab_manager.api.auth import require_permission
from lab_manager.api.deps import get_db
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor

router = APIRouter()
logger = logging.getLogger(__name__)

# Maximum rows per import to prevent abuse.
_MAX_ROWS = 5000
# Maximum file size: 10 MB.
_MAX_FILE_BYTES = 10 * 1024 * 1024


def _parse_csv(content: bytes) -> tuple[list[dict], Optional[str]]:
    """Parse CSV bytes into a list of row dicts.

    Returns (rows, error).  On error, rows is empty.
    """
    try:
        text = content.decode("utf-8-sig")  # handle BOM from Excel
    except UnicodeDecodeError:
        return [], "File is not valid UTF-8 text"

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], "CSV file has no header row"

    rows: list[dict] = []
    for i, row in enumerate(reader, start=2):  # row 1 = header
        if i - 1 > _MAX_ROWS:
            return [], f"CSV exceeds maximum of {_MAX_ROWS} rows"
        rows.append(row)
    return rows, None


def _strip_cell(value: Optional[str]) -> Optional[str]:
    """Strip whitespace and Excel-injection single-quote prefix."""
    if value is None:
        return None
    v = value.strip()
    if v.startswith("'") and len(v) > 1:
        v = v[1:]
    return v if v else None


def _parse_bool(value: Optional[str]) -> bool:
    if not value:
        return False
    return value.strip().lower() in ("true", "1", "yes", "t")


def _parse_decimal(value: Optional[str]) -> Optional[Decimal]:
    v = _strip_cell(value)
    if not v:
        return None
    try:
        return Decimal(v)
    except InvalidOperation:
        return None


def _parse_int(value: Optional[str]) -> Optional[int]:
    v = _strip_cell(value)
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _parse_date(value: Optional[str]) -> Optional[date]:
    v = _strip_cell(value)
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Vendors
# ---------------------------------------------------------------------------

_VENDOR_REQUIRED = {"name"}
_VENDOR_FIELDS = {"name", "website", "phone", "email", "notes"}


def _validate_vendor_row(row: dict, row_num: int) -> tuple[Optional[dict], list[dict]]:
    errors: list[dict] = []
    name = _strip_cell(row.get("name"))
    if not name:
        errors.append({"row": row_num, "field": "name", "message": "name is required"})
        return None, errors

    data = {
        "name": name,
        "website": _strip_cell(row.get("website")),
        "phone": _strip_cell(row.get("phone")),
        "email": _strip_cell(row.get("email")),
        "notes": _strip_cell(row.get("notes")),
    }
    return data, errors


@router.post("/vendors", dependencies=[Depends(require_permission("manage_products"))])
def import_vendors(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = file.file.read()
    if len(content) > _MAX_FILE_BYTES:
        return {
            "imported": 0,
            "errors": [
                {"row": 0, "field": "", "message": "File too large (max 10 MB)"}
            ],
            "skipped": 0,
        }

    rows, parse_err = _parse_csv(content)
    if parse_err:
        return {
            "imported": 0,
            "errors": [{"row": 0, "field": "", "message": parse_err}],
            "skipped": 0,
        }
    if not rows:
        return {
            "imported": 0,
            "errors": [{"row": 0, "field": "", "message": "CSV file is empty"}],
            "skipped": 0,
        }

    # Check required columns
    headers = set(rows[0].keys())
    missing = _VENDOR_REQUIRED - headers
    if missing:
        return {
            "imported": 0,
            "errors": [
                {"row": 0, "field": f, "message": f"Missing required column: {f}"}
                for f in missing
            ],
            "skipped": 0,
        }

    # Build existing vendor name index for dedup
    existing_names: set[str] = set()
    for v in db.scalars(select(Vendor)):
        existing_names.add(v.name.lower())

    all_errors: list[dict] = []
    imported = 0
    skipped = 0
    new_vendors: list[Vendor] = []

    for i, row in enumerate(rows, start=2):
        data, errs = _validate_vendor_row(row, i)
        if errs:
            all_errors.extend(errs)
            continue
        assert data is not None

        if data["name"].lower() in existing_names:
            skipped += 1
            continue

        existing_names.add(data["name"].lower())
        new_vendors.append(Vendor(**data))
        imported += 1

    if all_errors:
        return {"imported": 0, "errors": all_errors, "skipped": skipped}

    for v in new_vendors:
        db.add(v)
    db.commit()

    return {"imported": imported, "errors": [], "skipped": skipped}


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

_PRODUCT_REQUIRED = {"catalog_number", "name"}
_PRODUCT_FIELDS = {
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
}


def _validate_product_row(
    row: dict, row_num: int, vendor_ids: set[int]
) -> tuple[Optional[dict], list[dict]]:
    errors: list[dict] = []

    catalog_number = _strip_cell(row.get("catalog_number"))
    if not catalog_number:
        errors.append(
            {
                "row": row_num,
                "field": "catalog_number",
                "message": "catalog_number is required",
            }
        )

    name = _strip_cell(row.get("name"))
    if not name:
        errors.append({"row": row_num, "field": "name", "message": "name is required"})

    if errors:
        return None, errors

    vendor_id = _parse_int(row.get("vendor_id"))
    if vendor_id is not None and vendor_id not in vendor_ids:
        errors.append(
            {
                "row": row_num,
                "field": "vendor_id",
                "message": f"vendor_id {vendor_id} does not exist",
            }
        )
        return None, errors

    data = {
        "catalog_number": catalog_number,
        "name": name,
        "vendor_id": vendor_id,
        "category": _strip_cell(row.get("category")),
        "cas_number": _strip_cell(row.get("cas_number")),
        "storage_temp": _strip_cell(row.get("storage_temp")),
        "unit": _strip_cell(row.get("unit")),
        "hazard_info": _strip_cell(row.get("hazard_info")),
        "min_stock_level": _parse_decimal(row.get("min_stock_level")),
        "is_hazardous": _parse_bool(row.get("is_hazardous")),
        "is_controlled": _parse_bool(row.get("is_controlled")),
    }
    return data, errors


@router.post("/products", dependencies=[Depends(require_permission("manage_products"))])
def import_products(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = file.file.read()
    if len(content) > _MAX_FILE_BYTES:
        return {
            "imported": 0,
            "errors": [
                {"row": 0, "field": "", "message": "File too large (max 10 MB)"}
            ],
            "skipped": 0,
        }

    rows, parse_err = _parse_csv(content)
    if parse_err:
        return {
            "imported": 0,
            "errors": [{"row": 0, "field": "", "message": parse_err}],
            "skipped": 0,
        }
    if not rows:
        return {
            "imported": 0,
            "errors": [{"row": 0, "field": "", "message": "CSV file is empty"}],
            "skipped": 0,
        }

    headers = set(rows[0].keys())
    missing = _PRODUCT_REQUIRED - headers
    if missing:
        return {
            "imported": 0,
            "errors": [
                {"row": 0, "field": f, "message": f"Missing required column: {f}"}
                for f in sorted(missing)
            ],
            "skipped": 0,
        }

    # Preload vendor IDs for FK validation
    vendor_ids: set[int] = set()
    for v in db.scalars(select(Vendor)):
        vendor_ids.add(v.id)

    # Preload existing (catalog_number, vendor_id) pairs for dedup
    existing_pairs: set[tuple[str, Optional[int]]] = set()
    for p in db.scalars(select(Product)):
        existing_pairs.add((p.catalog_number, p.vendor_id))

    all_errors: list[dict] = []
    imported = 0
    skipped = 0
    new_products: list[Product] = []

    for i, row in enumerate(rows, start=2):
        data, errs = _validate_product_row(row, i, vendor_ids)
        if errs:
            all_errors.extend(errs)
            continue
        assert data is not None

        pair = (data["catalog_number"], data["vendor_id"])
        if pair in existing_pairs:
            skipped += 1
            continue

        existing_pairs.add(pair)
        new_products.append(Product(**data))
        imported += 1

    if all_errors:
        return {"imported": 0, "errors": all_errors, "skipped": skipped}

    for p in new_products:
        db.add(p)
    db.commit()

    return {"imported": imported, "errors": [], "skipped": skipped}


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

_INVENTORY_REQUIRED = {"product_id", "quantity_on_hand"}


def _validate_inventory_row(
    row: dict, row_num: int, product_ids: set[int], location_ids: set[int]
) -> tuple[Optional[dict], list[dict]]:
    errors: list[dict] = []

    product_id = _parse_int(row.get("product_id"))
    if product_id is None:
        errors.append(
            {
                "row": row_num,
                "field": "product_id",
                "message": "product_id is required and must be an integer",
            }
        )
    elif product_id not in product_ids:
        errors.append(
            {
                "row": row_num,
                "field": "product_id",
                "message": f"product_id {product_id} does not exist",
            }
        )

    qty = _parse_decimal(row.get("quantity_on_hand"))
    if qty is None:
        errors.append(
            {
                "row": row_num,
                "field": "quantity_on_hand",
                "message": "quantity_on_hand is required and must be a number",
            }
        )
    elif qty < 0:
        errors.append(
            {
                "row": row_num,
                "field": "quantity_on_hand",
                "message": "quantity_on_hand must be >= 0",
            }
        )

    if errors:
        return None, errors

    location_id = _parse_int(row.get("location_id"))
    if location_id is not None and location_id not in location_ids:
        errors.append(
            {
                "row": row_num,
                "field": "location_id",
                "message": f"location_id {location_id} does not exist",
            }
        )
        return None, errors

    expiry = _parse_date(row.get("expiry_date"))
    raw_expiry = _strip_cell(row.get("expiry_date"))
    if raw_expiry and expiry is None:
        errors.append(
            {
                "row": row_num,
                "field": "expiry_date",
                "message": "expiry_date must be YYYY-MM-DD format",
            }
        )
        return None, errors

    opened = _parse_date(row.get("opened_date"))
    raw_opened = _strip_cell(row.get("opened_date"))
    if raw_opened and opened is None:
        errors.append(
            {
                "row": row_num,
                "field": "opened_date",
                "message": "opened_date must be YYYY-MM-DD format",
            }
        )
        return None, errors

    status = _strip_cell(row.get("status")) or "available"
    valid_statuses = {
        "available",
        "opened",
        "depleted",
        "disposed",
        "expired",
        "deleted",
    }
    if status not in valid_statuses:
        errors.append(
            {
                "row": row_num,
                "field": "status",
                "message": f"status must be one of: {', '.join(sorted(valid_statuses))}",
            }
        )
        return None, errors

    data = {
        "product_id": product_id,
        "location_id": location_id,
        "lot_number": _strip_cell(row.get("lot_number")),
        "quantity_on_hand": qty,
        "unit": _strip_cell(row.get("unit")),
        "expiry_date": expiry,
        "opened_date": opened,
        "status": status,
        "notes": _strip_cell(row.get("notes")),
        "received_by": _strip_cell(row.get("received_by")),
    }
    return data, errors


@router.post(
    "/inventory", dependencies=[Depends(require_permission("manage_products"))]
)
def import_inventory(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = file.file.read()
    if len(content) > _MAX_FILE_BYTES:
        return {
            "imported": 0,
            "errors": [
                {"row": 0, "field": "", "message": "File too large (max 10 MB)"}
            ],
            "skipped": 0,
        }

    rows, parse_err = _parse_csv(content)
    if parse_err:
        return {
            "imported": 0,
            "errors": [{"row": 0, "field": "", "message": parse_err}],
            "skipped": 0,
        }
    if not rows:
        return {
            "imported": 0,
            "errors": [{"row": 0, "field": "", "message": "CSV file is empty"}],
            "skipped": 0,
        }

    headers = set(rows[0].keys())
    missing = _INVENTORY_REQUIRED - headers
    if missing:
        return {
            "imported": 0,
            "errors": [
                {"row": 0, "field": f, "message": f"Missing required column: {f}"}
                for f in sorted(missing)
            ],
            "skipped": 0,
        }

    # Preload FK lookup sets
    product_ids: set[int] = set()
    for p in db.scalars(select(Product)):
        product_ids.add(p.id)

    from lab_manager.models.location import StorageLocation

    location_ids: set[int] = set()
    for loc in db.scalars(select(StorageLocation)):
        location_ids.add(loc.id)

    all_errors: list[dict] = []
    imported = 0
    new_items: list[InventoryItem] = []

    for i, row in enumerate(rows, start=2):
        data, errs = _validate_inventory_row(row, i, product_ids, location_ids)
        if errs:
            all_errors.extend(errs)
            continue
        assert data is not None

        new_items.append(InventoryItem(**data))
        imported += 1

    if all_errors:
        return {"imported": 0, "errors": all_errors, "skipped": 0}

    for item in new_items:
        db.add(item)
    db.commit()

    return {"imported": imported, "errors": [], "skipped": 0}
