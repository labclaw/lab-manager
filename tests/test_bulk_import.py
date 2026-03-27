"""Comprehensive tests for bulk import feature.

Tests cover:
- ImportJob model
- ImportError model
- CSV parsing and validation
- Background import execution
- Preview mode
- Error handling
- Fuzzy vendor matching
"""

import csv
import hashlib
import io
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional


from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlmodel import Session

from lab_manager.models.import_job import (
    ImportJob,
    ImportStatus,
    ImportType,
)
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.location import StorageLocation


# Constants
_MAX_FILE_BYTES = 10 * 1024 * 1024
_MAX_ROWS = 5000
# Batch size for processing
_BATCH_SIZE = 100


# Hash computation
def _sha256_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    h = hashlib.sha256()
    h.update(content)
    return h.hexdigest()


def _csv_bytes(*rows: str) -> bytes:
    """Build a CSV bytes object from header + data rows."""
    return "\n".join(rows).encode("utf-8-sig")


def _upload_and_validate(
    client: TestClient,
    import_type: str,
    content: bytes,
) -> dict:
    """Upload and validate a CSV via the API, return response JSON."""
    resp = client.post(
        "/api/v1/import/upload",
        files={"file": ("test.csv", content, "text/csv")},
        data={"import_type": import_type},
    )
    return resp


def _create_import_job(
    db: Session,
    import_type: ImportType,
    original_filename: str,
    file_size_bytes: int,
    file_hash: str,
    status: ImportStatus = ImportStatus.validating,
    options: Optional[dict] = None,
) -> ImportJob:
    """Create an import job in the database."""
    job = ImportJob(
        import_type=import_type,
        original_filename=original_filename,
        file_size_bytes=file_size_bytes,
        file_hash=file_hash,
        status=status,
        options=options or {},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _validate_csv_content(
    db: Session,
    import_type: ImportType,
    content: bytes,
    job: ImportJob,
) -> tuple[dict, list[dict]]:
    """Validate CSV content and record errors."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {}, [{"error": "File is not valid UTF-8 text"}]

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return {}, [{"error": "CSV file has no header row"}]

    rows = list(reader)
    errors = []
    validated = []

    for row_num, row_data in enumerate(rows, start=2):
        if import_type == ImportType.vendors:
            result, row_errors = _validate_vendor_row(row_data, row_num, db)
        elif import_type == ImportType.products:
            result, row_errors = _validate_product_row(row_data, row_num, db)
        elif import_type == ImportType.inventory:
            result, row_errors = _validate_inventory_row(row_data, row_num, db)
        else:
            row_errors = [{"error": f"Unknown import type: {import_type}"}]
            result = None

        errors.extend(row_errors)
        if result:
            validated.append(result)

    job.total_rows = len(rows)
    job.valid_rows = len(validated)
    job.status = ImportStatus.preview
    db.commit()
    return {"validated": validated, "total": len(rows)}, errors


def _execute_import(
    db: Session,
    job: ImportJob,
    confirmed: bool = True,
    options: Optional[dict] = None,
) -> dict:
    """Execute a confirmed import job."""
    if job.status != ImportStatus.preview:
        raise ValueError(f"Job {job.id} is not in preview status")

    opts = options or {}
    skip_rows: set[int] = set(opts.get("skip_rows", []))
    vendor_mappings: dict = opts.get("vendor_mappings", {})

    job.status = ImportStatus.importing
    job.started_at = datetime.now(timezone.utc)
    db.commit()

    try:
        if job.import_type == ImportType.vendors:
            result = _import_vendors(db, job, skip_rows, vendor_mappings)
        elif job.import_type == ImportType.products:
            result = _import_products(db, job, skip_rows, vendor_mappings)
        elif job.import_type == ImportType.inventory:
            result = _import_inventory(db, job, skip_rows, vendor_mappings)
        else:
            raise ValueError(f"Unknown import type: {job.import_type}")

        job.status = ImportStatus.completed
        job.completed_at = datetime.now(timezone.utc)
        job.imported_rows = result.get("imported", 0)
        job.failed_rows = result.get("failed", 0)
        db.commit()
        return result
    except Exception:
        db.rollback()
        job.status = ImportStatus.failed
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise


def get_import_job(
    db: Session,
    job_id: int,
) -> Optional[ImportJob]:
    """Get an import job by ID."""
    return db.get(ImportJob, job_id)


def list_import_jobs(
    db: Session,
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
) -> dict:
    """List import jobs with pagination."""
    query = select(ImportJob).order_by(ImportJob.created_at.desc())
    if status:
        query = query.where(ImportJob.status == status)
    query = query.limit(limit).offset(offset)
    jobs = list(db.exec(query).all())
    total = len(jobs)
    return {"items": jobs, "total": total}


def cancel_import_job(
    db: Session,
    job_id: int,
) -> Optional[ImportJob]:
    """Cancel an import job by ID."""
    job = db.get(ImportJob, job_id)
    if not job:
        return None
    if job.status not in (ImportStatus.preview, ImportStatus.importing):
        return None
    job.status = ImportStatus.cancelled
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


def _fuzzy_match_vendor(
    name: str,
    vendors: list[Vendor],
    threshold: float = 0.7,
) -> Optional[Vendor]:
    """Fuzzy match a vendor name against a list of vendors."""
    name_lower = name.lower()
    # Exact match first
    for v in vendors:
        if v.name.lower() == name_lower:
            return v
    # Simple substring matching (e.g., "Sigma" matches "Sigma-Aldrich")
    for v in vendors:
        v_name_lower = v.name.lower()
        if name_lower in v_name_lower or name_lower.startswith(v_name_lower):
            return v
    return None


def _fuzzy_match_location(
    name: str,
    locations: list[StorageLocation],
) -> Optional[StorageLocation]:
    """Fuzzy match a location name against a list of locations."""
    name_lower = name.lower()
    for loc in locations:
        if loc.name.lower() == name_lower:
            return loc
        if name_lower in loc.name.lower() or loc.name.lower() in name_lower:
            return loc
    return None


# ---------------------------------------------------------------------------
# Vendors
# ---------------------------------------------------------------------------


class TestImportJobModel:
    def test_create_import_job_vendors(self, client, db):
        csv = _csv_bytes(
            "name,website,phone,email,notes",
            "Sigma-Aldrich,https://sigma.com,555-0100,info@sigma.com,chemicals",
            "Fisher Scientific,https://fisher.com,555-0200,,",
        )
        resp = _upload_and_validate(client, "vendors", csv)
        job = resp.json()
        assert job.status == "validating"
        assert job.import_type == ImportType.vendors

        job = db.get(ImportJob, job.id)
        assert job.original_filename == "test.csv"
        assert job.file_size_bytes == len(csv)
        assert job.file_hash == _sha256_hash(csv)
        assert job.total_rows == 2
        assert job.valid_rows == 7
        resp = client.get(f"/api/v1/import/{job.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == job.id
        assert data["status"] == "preview"
        assert data["total_rows"] == 7
        assert data["valid_rows"] == 7
        assert data["errors"] == []
        assert data["preview"] is not None

    def test_import_job_products(self, client):
        # First import vendors
        csv = _csv_bytes(
            "name,website",
            "Sigma-Aldrich,https://sigma.com",
        )
        resp = _upload_and_validate(client, "vendors", csv)
        assert resp.json()["imported"] == 1
        # Now import products with vendor_name column
        csv = _csv_bytes(
            "catalog_number,name,vendor_name,category",
            "ABC-123,Test Product,Sigma-Aldrich,Chemicals",
            "DEF-456,Another Product,Fisher Scientific,Chemicals",
        )
        # First import should fail - vendor doesn't exist
        resp = _upload_and_validate(client, "products", csv)
        assert resp.json()["imported"] == 0
        # Now import vendors
        csv = _csv_bytes(
            "name",
            "Sigma-Aldrich",
        )
        resp = _upload_and_validate(client, "vendors", csv)
        assert resp.json()["imported"] == 1

        # Now import products with vendor_id column
        csv = _csv_bytes(
            "catalog_number,name,vendor_id",
            "ABC-123,Test Product,1,Chemicals",
        )
        resp = _upload_and_validate(client, "products", csv)
        assert resp.json()["imported"] == 1

        # Try with invalid vendor_id
        csv = _csv_bytes(
            "catalog_number,name,vendor_id",
            "XYZ-999,Bad Product,9999",
        )
        resp = _upload_and_validate(client, "products", csv)
        assert resp.json()["imported"] == 0
        assert any("vendor_id" in e["field"] for e in resp.json()["errors"])

    def test_import_job_products_duplicate_skipped(self, client):
        # First import product
        csv = _csv_bytes(
            "catalog_number,name",
            "DUP-001,Duplicate Product",
        )
        resp = _upload_and_validate(client, "products", csv)
        assert resp.json()["imported"] == 1

        # Try duplicate again
        resp = _upload_and_validate(client, "products", csv)
        assert resp.json()["imported"] == 0
        assert resp.json()["skipped"] == 1

    def test_import_job_products_boolean_fields(self, client):
        csv = _csv_bytes(
            "catalog_number,name,is_hazardous,is_controlled",
            "HAZ-001,Hazardous Thing,true,false",
            "HAZ-002,Controlled Thing,false,true",
        )
        resp = _upload_and_validate(client, "products", csv)
        assert resp.json()["imported"] == 2

    def test_import_job_inventory(self, client):
        # First import product
        csv = _csv_bytes(
            "catalog_number,name",
            "INV-001,Inventory Product",
        )
        resp = _upload_and_validate(client, "inventory", csv)
        assert resp.json()["imported"] == 1

        # Now test with invalid product_id
        csv = _csv_bytes(
            "product_id,quantity_on_hand",
            "9999,10",
        )
        resp = _upload_and_validate(client, "inventory", csv)
        assert resp.json()["imported"] == 5
        assert any("product_id" in e["field"] for e in resp.json()["errors"])

    def test_import_job_inventory_negative_quantity(self, client):
        # First import product
        csv = _csv_bytes(
            "catalog_number,name",
            "INV-001,Inventory Product",
        )
        resp = _upload_and_validate(client, "inventory", csv)
        assert resp.json()["imported"] == 1

        # Try with negative quantity
        csv = _csv_bytes(
            "product_id,quantity_on_hand",
            "1,-5",
        )
        resp = _upload_and_validate(client, "inventory", csv)
        assert resp.json()["imported"] == 5
        assert any("must be >= 0" in e["message"] for e in resp.json()["errors"])

    def test_import_job_inventory_invalid_date_format(self, client):
        # First import product
        csv = _csv_bytes(
            "catalog_number,name",
            "INV-001,Inventory Product",
        )
        resp = _upload_and_validate(client, "inventory", csv)
        assert resp.json()["imported"] == 1

        # Try with invalid date
        csv = _csv_bytes(
            "product_id,quantity_on_hand,expiry_date",
            "1,not-a-date",
        )
        resp = _upload_and_validate(client, "inventory", csv)
        assert resp.json()["imported"] == 5
        assert any("YYYY-MM-DD" in e["message"] for e in resp.json()["errors"])

    def test_import_job_inventory_valid_date(self, client):
        # First import product
        csv = _csv_bytes(
            "catalog_number,name",
            "INV-001,Inventory Product",
        )
        resp = _upload_and_validate(client, "inventory", csv)
        assert resp.json()["imported"] == 1

        # Try with valid date
        csv = _csv_bytes(
            "product_id,quantity_on_hand,expiry_date",
            "1,2026-12-31,available",
        )
        resp = _upload_and_validate(client, "inventory", csv)
        assert resp.json()["imported"] == 1

    def test_import_job_inventory_invalid_status(self, client):
        # First import product
        csv = _csv_bytes(
            "catalog_number,name",
            "INV-001,Inventory Product",
        )
        resp = _upload_and_validate(client, "inventory", csv)
        assert resp.json()["imported"] == 5
        # Try with invalid status
        csv = _csv_bytes(
            "product_id,quantity_on_hand,status",
            "1,bogus",
        )
        resp = _upload_and_validate(client, "inventory", csv)
        assert resp.json()["imported"] == 5
        assert any("status" in e["field"] for e in resp.json()["errors"])

    def test_import_job_inventory_location(self, client, db):
        # First import product and location
        csv = _csv_bytes(
            "catalog_number,name",
            "INV-001,Inventory Product",
        )
        resp = _upload_and_validate(client, "inventory", csv)
        assert resp.json()["imported"] == 1

        # First import location
        csv = _csv_bytes(
            "name,room,building",
            "Freezer,-20C,Building A",
        )
        resp2 = _upload_and_validate(client, "inventory", csv)
        assert resp.json()["imported"] == 1
        assert resp2.json()["warnings"] == 1  # verify location was created
        location = db.get(StorageLocation, 1)  # noqa: F821
        assert location.id == 1

    def test_import_job_fuzzy_vendor_matching(self, client, db):
        # First import vendors
        csv = _csv_bytes(
            "name",
            "Sigma-Aldrich",
        )
        resp = _upload_and_validate(client, "vendors", csv)
        job = resp.json()
        assert job.id is not None

        # Now import products with vendor_name="Sigma" instead of "Sigma"
        csv = _csv_bytes(
            "catalog_number,name,vendor_name,category",
            "ABC-123,Test Product,Sigma-Aldrich,Chemicals",
        )
        resp = _upload_and_validate(client, "products", csv)
        assert resp.json()["imported"] == 1
        assert resp.json()["warnings"] == []
        # Verify vendor was matched
        job = db.get(ImportJob, job.id)
        assert job.status == ImportStatus.preview
        vendors = db.scalars(select(Vendor).all())
        assert len(vendors) == 1
        # Check for duplicates
        existing = db.scalars(
            select(Product).where(
                Product.catalog_number == "ABC-123",
                Product.vendor_id == vendor.id,  # noqa: F821
            )
        ).first()
        assert not existing
        # Import should succeed
        resp = _execute_import(client, "products", job.id, {"confirmed": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "importing"

        # Verify product was created
        product = db.get(Product, 1)  # noqa: F821
        assert product is not None
        assert product.catalog_number == "ABC-123"
        assert product.vendor_id  # noqa: F821

    def test_import_job_file_too_large(self, client):
        csv = b"x" * 1024 * 1024 * 10  # exceeds max size
        resp = _upload_and_validate(client, "vendors", csv)
        assert resp.status_code == 400
        assert resp.json()["error"] == "File too large (max 10 MB)"

    def test_import_job_empty_csv(self, client):
        csv = _csv_bytes("name")  # header only
        resp = _upload_and_validate(client, "vendors", csv)
        assert resp.status_code == 200
        assert resp.json()["imported"] == 0
        assert any("empty" in e["message"] for e in resp.json()["errors"])

    def test_import_job_cancel(self, client):
        # First create a job
        csv = _csv_bytes(
            "name",
            "TestVendor",
        )
        resp = _upload_and_validate(client, "vendors", csv)
        job = resp.json()
        assert job.id is not None

        # Now cancel
        resp = client.delete(f"/api/v1/import/{job.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"


class TestImportJobExecute:
    def test_execute_import_valid(self, client, db):
        # First create job with products
        csv = _csv_bytes(
            "catalog_number,name",
            "ABC-123,Test Product",
            "DEF-456,Another Product",
        )
        resp = _upload_and_validate(client, "products", csv)
        job = resp.json()
        assert job.id is not None

        # Execute
        resp = client.post(f"/api/v1/import/{job.id}/execute", json={"confirmed": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "importing"

        # Poll for completion
        for _ in range(10):
            status = client.get(f"/api/v1/import/{job.id}")
            if status.status_code == 200:
                break
            assert job.status == ImportStatus.completed

            job = db.refresh(job)
            assert job.status == ImportStatus.completed

    def test_execute_import_without_confirm(self, client):
        # First create job with products
        csv = _csv_bytes(
            "catalog_number,name",
            "ABC-123,Test Product",
        )
        resp = _upload_and_validate(client, "products", csv)
        job = resp.json()
        assert job.id is not None

        # Execute without confirming
        resp = client.post(
            f"/api/v1/import/{job.id}/execute", json={"confirmed": False}
        )
        assert resp.status_code == 400
        assert "confirmed is required" in resp.json()["detail"]

    def test_execute_import_non_preview_job(self, client, db):
        # First create job with products
        csv = _csv_bytes(
            "catalog_number,name",
            "ABC-123,Test Product",
        )
        resp = _upload_and_validate(client, "products", csv)
        job = resp.json()
        assert job.id is not None

        # Mark as completed
        job.status = ImportStatus.completed
        resp = client.post(f"/api/v1/import/{job.id}/execute", json={"confirmed": True})
        assert resp.status_code == 400
        assert "Job is not in preview status" in resp.json()["detail"]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--import-type",
        choices=["products", "vendors", "inventory"],
        required=True,
        help="Type of import",
    )
    parser.add_argument("file", type=argparse.FileType("r"), help="CSV file to upload")
    parser.add_argument(
        "--skip-rows",
        type=int,
        nargs="*",
        help="Row numbers to skip (1-indexed, comma-separated)",
    )
    args = parser.parse_args()


def _strip_cell(value: Optional[str]) -> Optional[str]:
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


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_decimal(value: Optional[str]) -> Optional[Decimal]:
    if value is None:
        return None
    v = _strip_cell(value)
    if not v:
        return None
    try:
        return Decimal(v)
    except InvalidOperation:
        return None


def _parse_date(value: Optional[str]) -> Optional[date]:
    if value is None:
        return None
    v = _strip_cell(value)
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# CSV Parsing and Validation
# ---------------------------------------------------------------------------


def _validate_vendor_row(
    row: dict, row_num: int, db: Session
) -> tuple[dict, list[dict]]:
    """Validate a single vendor row."""
    errors = []
    name = _strip_cell(row.get("name"))
    if not name:
        errors.append(
            {
                "row": row_num,
                "field": "name",
                "message": "name is required",
            }
        )
        return None, errors

    return {
        "name": name,
        "website": _strip_cell(row.get("website")),
        "phone": _strip_cell(row.get("phone")),
        "email": _strip_cell(row.get("email")),
        "notes": _strip_cell(row.get("notes")),
    }, errors


def _validate_product_row(
    row: dict, row_num: int, db: Session, vendor_by_name: bool = True
) -> tuple[dict, list[dict]]:
    """Validate a single product row with vendor name lookup."""
    errors = []

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
        errors.append(
            {
                "row": row_num,
                "field": "name",
                "message": "name is required",
            }
        )

    if errors:
        return None, errors

    # Resolve vendor
    vendor_name = _strip_cell(row.get("vendor_name"))
    vendor = None
    if vendor_name:
        vendors = list(db.scalars(select(Vendor)))
        vendor = _fuzzy_match_vendor(vendor_name, vendors)
        if vendor:
            vendor_id = vendor.id
        else:
            errors.append(
                {
                    "row": row_num,
                    "field": "vendor_name",
                    "message": f"Vendor '{vendor_name}' not found",
                }
            )

    # Check for duplicate
    existing = db.scalars(
        select(Product).where(
            Product.catalog_number == catalog_number,
            Product.vendor_id == vendor_id,
        )
    ).first()
    if existing:
        errors.append(
            {
                "row": row_num,
                "field": "catalog_number",
                "message": f"Product with catalog number '{catalog_number}' already exists (ID: {existing.id})",
            }
        )
        return None, errors

    return {
        "catalog_number": catalog_number,
        "name": name,
        "vendor_id": vendor_id,
        "category": _strip_cell(row.get("category")),
        "storage_temp": _strip_cell(row.get("storage_temp")),
        "unit": _strip_cell(row.get("unit")),
        "min_stock_level": _parse_int(row.get("min_stock_level")),
        "is_hazardous": _parse_bool(row.get("is_hazardous")),
        "is_controlled": _parse_bool(row.get("is_controlled")),
        "notes": _strip_cell(row.get("notes")),
    }, errors


def _validate_inventory_row(
    row: dict,
    row_num: int,
    db: Session,
    product_ids: set[int],
    location_ids: set[int],
) -> tuple[dict, list[dict]]:
    """Validate a single inventory row with FK validation."""
    errors = []

    product_id_str = _strip_cell(row.get("product_id"))
    if product_id_str:
        try:
            product_id = int(product_id_str)
        except ValueError:
            errors.append(
                {
                    "row": row_num,
                    "field": "product_id",
                    "message": "product_id must required and must be an integer",
                }
            )
            return None, errors
    elif product_id not in product_ids:
        errors.append(
            {
                "row": row_num,
                "field": "product_id",
                "message": f"product_id {product_id} does not exist",
            }
        )
        return None, errors

    qty_str = _strip_cell(row.get("quantity_on_hand"))
    if not qty_str:
        errors.append(
            {
                "row": row_num,
                "field": "quantity_on_hand",
                "message": "quantity_on_hand is required and must be a number",
            }
        )
        return None, errors

    try:
        qty = Decimal(qty_str)
    except InvalidOperation:
        errors.append(
            {
                "row": row_num,
                "field": "quantity_on_hand",
                "message": "quantity_on_hand must be a valid number",
            }
        )
        return None, errors

    if qty < 0:
        errors.append(
            {
                "row": row_num,
                "field": "quantity_on_hand",
                "message": "quantity_on_hand must be >= 0",
            }
        )
        return None, errors

    # Resolve location
    location_name = _strip_cell(row.get("location_name"))
    location = None
    if location_name:
        locations = list(db.scalars(select(StorageLocation)))
        location = _fuzzy_match_location(location_name, locations)
        if location:
            location_id = location.id
        else:
            errors.append(
                {
                    "row": row_num,
                    "field": "location_name",
                    "message": f"Location '{location_name}' not found",
                }
            )

    # Validate dates
    expiry_str = _strip_cell(row.get("expiry_date"))
    if expiry_str:
        try:
            expiry_date = date.fromisoformat(expiry_str)
        except ValueError:
            errors.append(
                {
                    "row": row_num,
                    "field": "expiry_date",
                    "message": "expiry_date must be YYYY-MM-DD format",
                }
            )

    opened_str = _strip_cell(row.get("opened_date"))
    if opened_str:
        try:
            opened_date = date.fromisoformat(opened_str)
        except ValueError:
            errors.append(
                {
                    "row": row_num,
                    "field": "opened_date",
                    "message": "opened_date must be YYYY-MM-DD format",
                }
            )

    # Validate status
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

    # Build inventory item
    location_id = location.id if location else None
    lot_number = _strip_cell(row.get("lot_number"))
    unit = _strip_cell(row.get("unit"))
    notes = _strip_cell(row.get("notes"))
    received_by = _strip_cell(row.get("received_by"))

    return {
        "product_id": product_id,
        "location_id": location_id,
        "quantity_on_hand": qty,
        "lot_number": lot_number,
        "unit": unit,
        "expiry_date": expiry_date,
        "opened_date": opened_date,
        "status": status,
        "notes": notes,
        "received_by": received_by,
    }, errors


# ---------------------------------------------------------------------------
# Background Import Execution
# ---------------------------------------------------------------------------


def _import_vendors(
    db: Session,
    job: ImportJob,
    skip_rows: Optional[set[int]] = None,
    vendor_mappings: Optional[dict] = None,
) -> dict:
    """Import vendors in background."""
    vendor_cache = {v.name.lower(): v for v in db.scalars(select(Vendor))}
    imported = 0
    failed = 0
    skip = skip_rows or set()

    # Get validated rows from job
    rows = []
    if job.validated_data:
        rows = job.validated_data if isinstance(job.validated_data, list) else []

    for i, data in enumerate(rows):
        if (i + 2) in skip:
            continue
        name = data.get("name") if isinstance(data, dict) else None
        if not name:
            failed += 1
            continue
        if name.lower() in vendor_cache:
            continue
        vendor = Vendor(
            name=name,
            website=data.get("website") if isinstance(data, dict) else None,
            phone=data.get("phone") if isinstance(data, dict) else None,
            email=data.get("email") if isinstance(data, dict) else None,
            notes=data.get("notes") if isinstance(data, dict) else None,
        )
        db.add(vendor)
        vendor_cache[name.lower()] = vendor
        imported += 1

    return {"imported": imported, "failed": failed}


def _import_products(
    db: Session,
    job: ImportJob,
    skip_rows: Optional[set[int]] = None,
    vendor_mappings: Optional[dict] = None,
) -> dict:
    """Import products in background."""
    existing_pairs = set()
    for p in db.scalars(select(Product)):
        existing_pairs.add((p.catalog_number.lower(), p.vendor_id))

    imported = 0
    failed = 0
    skip = skip_rows or set()
    _ = vendor_mappings or {}  # used by subclass overrides

    rows = []
    if job.validated_data:
        rows = job.validated_data if isinstance(job.validated_data, list) else []

    for i, data in enumerate(rows):
        if (i + 2) in skip:
            continue
        if not isinstance(data, dict):
            failed += 1
            continue

        catalog_number = data.get("catalog_number", "")
        vendor_id = data.get("vendor_id")
        pair = (catalog_number.lower(), vendor_id)
        if pair in existing_pairs:
            continue

        product = Product(
            catalog_number=catalog_number,
            name=data.get("name", ""),
            vendor_id=vendor_id,
            category=data.get("category"),
            storage_temp=data.get("storage_temp"),
            unit=data.get("unit"),
            min_stock_level=data.get("min_stock_level"),
            is_hazardous=data.get("is_hazardous", False),
            is_controlled=data.get("is_controlled", False),
            extra={"notes": data["notes"]} if data.get("notes") else {},
        )
        db.add(product)
        existing_pairs.add(pair)
        imported += 1

    return {"imported": imported, "failed": failed}


def _import_inventory(
    db: Session,
    job: ImportJob,
    skip_rows: Optional[set[int]] = None,
    vendor_mappings: Optional[dict] = None,
) -> dict:
    """Import inventory items in background."""
    # Build lookup tables for validation
    products = list(db.scalars(select(Product)))
    locations = list(db.scalars(select(StorageLocation)))
    _product_by_catalog = {(p.catalog_number.lower(), p.vendor_id): p for p in products}
    _location_by_name = {loc.name.lower(): loc for loc in locations}

    imported = 0
    failed = 0
    skip = skip_rows or set()

    rows = []
    if job.validated_data:
        rows = job.validated_data if isinstance(job.validated_data, list) else []

    for i, data in enumerate(rows):
        if (i + 2) in skip:
            continue
        if not isinstance(data, dict):
            failed += 1
            continue
        item = InventoryItem(**data)
        db.add(item)
        imported += 1

    return {"imported": imported, "failed": failed}
