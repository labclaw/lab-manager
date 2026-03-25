"""Bulk import endpoints for CSV/TSV data.

Scientists can import products, vendors, and inventory from spreadsheet exports
without manually entering each record one at a time.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.exceptions import ValidationError
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor

logger = logging.getLogger(__name__)

router = APIRouter()

# Maximum file size: 10 MB
MAX_IMPORT_SIZE = 10 * 1024 * 1024
MAX_ROWS = 5000


class ImportResult(BaseModel):
    """Result of a bulk import operation."""

    created: int = 0
    skipped: int = 0
    errors: list[str] = []
    total_rows: int = 0


def _parse_csv(content: bytes) -> list[dict[str, str]]:
    """Parse CSV or TSV content into list of dicts. Auto-detects delimiter."""
    text = content.decode("utf-8-sig")  # Handle BOM from Excel
    # Auto-detect delimiter
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(text[:4096])
    except csv.Error:
        dialect = csv.excel  # Default to comma

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = []
    for i, row in enumerate(reader):
        if i >= MAX_ROWS:
            break
        # Strip whitespace from keys and values
        cleaned = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        rows.append(cleaned)
    return rows


# Column name aliases — scientists may use various header names
_VENDOR_NAME_ALIASES = {"vendor", "vendor_name", "supplier", "company", "manufacturer"}
_CATALOG_ALIASES = {"catalog_number", "catalog", "cat_no", "cat#", "catalog#", "sku", "item_number", "item#", "part_number", "part#"}
_PRODUCT_NAME_ALIASES = {"name", "product_name", "product", "description", "item", "chemical", "reagent"}
_CATEGORY_ALIASES = {"category", "type", "group", "class"}
_CAS_ALIASES = {"cas_number", "cas", "cas#", "cas_no"}
_UNIT_ALIASES = {"unit", "uom", "units", "unit_of_measure"}
_WEBSITE_ALIASES = {"website", "url", "web", "site"}
_EMAIL_ALIASES = {"email", "e-mail", "contact_email"}
_PHONE_ALIASES = {"phone", "telephone", "tel", "contact_phone"}


def _find_column(row: dict, aliases: set[str]) -> Optional[str]:
    """Find a value from a row using multiple possible column name aliases."""
    for alias in aliases:
        if alias in row and row[alias]:
            return row[alias]
    return None


@router.post("/products", response_model=ImportResult)
async def import_products(
    file: UploadFile = File(...),
    skip_duplicates: bool = Query(True, description="Skip rows with existing catalog numbers"),
    db: Session = Depends(get_db),
):
    """Import products from a CSV/TSV file.

    Expected columns (flexible naming): catalog_number, name, vendor, category, cas_number, unit.
    Duplicates (same catalog_number + vendor) are skipped by default.
    """
    content = await file.read()
    if len(content) > MAX_IMPORT_SIZE:
        raise ValidationError(f"File too large ({len(content)} bytes). Maximum: 10 MB.")

    rows = _parse_csv(content)
    if not rows:
        raise ValidationError("No data rows found in the file. Check that the first row contains column headers.")

    result = ImportResult(total_rows=len(rows))

    # Pre-load existing products for duplicate detection
    existing = set()
    if skip_duplicates:
        stmt = select(Product.catalog_number, Product.vendor_id)
        for cat, vid in db.execute(stmt):
            existing.add((cat, vid))

    # Pre-load vendor name -> id mapping
    vendor_map: dict[str, int] = {}
    for v in db.execute(select(Vendor.id, Vendor.name)):
        vendor_map[v.name.lower()] = v.id

    for i, row in enumerate(rows, start=2):  # Start at 2 (row 1 = header)
        catalog = _find_column(row, _CATALOG_ALIASES)
        name = _find_column(row, _PRODUCT_NAME_ALIASES)

        if not catalog or not name:
            result.errors.append(f"Row {i}: Missing required field (catalog_number or name)")
            continue

        # Resolve vendor
        vendor_name = _find_column(row, _VENDOR_NAME_ALIASES)
        vendor_id = None
        if vendor_name:
            vendor_id = vendor_map.get(vendor_name.lower())
            if not vendor_id:
                # Auto-create vendor
                new_vendor = Vendor(name=vendor_name)
                db.add(new_vendor)
                db.flush()
                vendor_map[vendor_name.lower()] = new_vendor.id
                vendor_id = new_vendor.id

        # Check duplicate
        if skip_duplicates and (catalog, vendor_id) in existing:
            result.skipped += 1
            continue

        product = Product(
            catalog_number=catalog,
            name=name,
            vendor_id=vendor_id,
            category=_find_column(row, _CATEGORY_ALIASES),
            cas_number=_find_column(row, _CAS_ALIASES),
            unit=_find_column(row, _UNIT_ALIASES),
        )
        db.add(product)
        existing.add((catalog, vendor_id))
        result.created += 1

    if result.created > 0:
        db.flush()

    logger.info(
        "Bulk import products: %d created, %d skipped, %d errors from %d rows",
        result.created,
        result.skipped,
        len(result.errors),
        result.total_rows,
    )
    return result


@router.post("/vendors", response_model=ImportResult)
async def import_vendors(
    file: UploadFile = File(...),
    skip_duplicates: bool = Query(True, description="Skip rows with existing vendor names"),
    db: Session = Depends(get_db),
):
    """Import vendors from a CSV/TSV file.

    Expected columns (flexible naming): vendor/name, website, email, phone.
    Duplicate names are skipped by default.
    """
    content = await file.read()
    if len(content) > MAX_IMPORT_SIZE:
        raise ValidationError(f"File too large ({len(content)} bytes). Maximum: 10 MB.")

    rows = _parse_csv(content)
    if not rows:
        raise ValidationError("No data rows found in the file.")

    result = ImportResult(total_rows=len(rows))

    # Pre-load existing vendor names
    existing_names: set[str] = set()
    if skip_duplicates:
        for (name,) in db.execute(select(Vendor.name)):
            existing_names.add(name.lower())

    for i, row in enumerate(rows, start=2):
        name = _find_column(row, _VENDOR_NAME_ALIASES) or _find_column(row, _PRODUCT_NAME_ALIASES)
        if not name:
            result.errors.append(f"Row {i}: Missing vendor name")
            continue

        if skip_duplicates and name.lower() in existing_names:
            result.skipped += 1
            continue

        vendor = Vendor(
            name=name,
            website=_find_column(row, _WEBSITE_ALIASES),
            email=_find_column(row, _EMAIL_ALIASES),
            phone=_find_column(row, _PHONE_ALIASES),
        )
        db.add(vendor)
        existing_names.add(name.lower())
        result.created += 1

    if result.created > 0:
        db.flush()

    logger.info(
        "Bulk import vendors: %d created, %d skipped, %d errors from %d rows",
        result.created,
        result.skipped,
        len(result.errors),
        result.total_rows,
    )
    return result
