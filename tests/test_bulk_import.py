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

import hashlib
import io
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from unittest.mock import Mock, patch

from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlmodel import Session

from lab_manager.api.deps import get_db
from lab_manager.models.import_job import (
    ImportJob,
    ImportError,
    ImportStatus,
    ImportType,
)
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.location import StorageLocation


from lab_manager.models.staff import Staff


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


def _upload_and_validate(
    client: TestClient,
    import_type: ImportType,
    content: bytes,
) -> tuple[ImportJob, list[dict]]:
    """Upload and validate a CSV, return import job ID."""
    if len(content) > _MAX_FILE_BYTES:
        return None, {"error": "File too large (max 10 MB)"}


    # Parse CSV
    text = content.decode("utf-8-sig")  # handle BOM from Excel
    except UnicodeDecodeError:
        return None, {"error": "File is not valid UTF-8 text"}

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return None, {"error": "CSV file has no header row"}

    rows: list[dict] = []
    for i, row in enumerate(reader, start=2):  # row 1 = header
        if i - 1 > _MAX_ROWS:
            return None, {"error": f"CSV exceeds maximum of {_MAX_ROWS} rows"}
        rows.append(row)
    return rows, None


def _create_import_job(
    db: Session,
    import_type: ImportType,
    original_filename: str,
    file_size_bytes: int
    file_hash: str
    status: ImportStatus = Import_status.validating
    options: dict
) -> ImportJob:
    db.add(job)
    db.commit()
    db.refresh(job)
            job.status = ImportStatus.preview
        job.valid_rows = len(rows)
            job.total_rows = len(rows)
        )
        return job


def _validate_csv_content(
    db: Session,
    import_type: ImportType,
    content: bytes
    job: ImportJob,
) -> tuple[dict, list[dict]]:
    """Validate CSV content and record errors."""
    job = _set_status(ImportStatus.validating)

    if import_type == ImportType.vendors:
        return _validate_vendors(rows, db, job)
    elif import_type == ImportType.products:
        return _validate_products(rows, db, job)
    elif import_type == ImportType.inventory:
        return _validate_inventory(rows, db, job)
    else:
        raise ValueError(f"Unknown import type: {import_type}")

    # Record errors
    for row_num, row_data in enumerate(rows, start=2):
        field = field
                error_type = error_type
                message = message
                raw_data = json.dumps(row_data)
                error = ImportError(
                    job_id=job.id,
                    row_number=row_num,
                    field=field,
                    error_type=error_type,
                    message=message,
                    raw_data=raw_data,
                )
                db.add(error)

    # Update job status
    job.total_rows = len(rows)
            job.valid_rows = sum(1 for e in result.errors)
            job.failed_rows += 1
        else:
            job.valid_rows = 0

        job.status = ImportStatus.preview

        db.commit()
    return job


def _execute_import(
    db: Session,
    job: ImportJob,
    confirmed: bool = True,
    options: dict
) -> dict:
    """Execute a confirmed import job.

    if job.status != ImportStatus.preview:
        raise ValueError(f"Job {job.id} is not in preview status")

    # Get options
    skip_rows: list[int] = options.get("skip_rows", [])
    skip_set = set(options.get("skip_rows", set())
    vendor_mappings = options.get("vendor_mappings", {})

 # Run the import
    if import_type == ImportType.vendors:
        _import_vendors(db, job)
    elif import_type == ImportType.products:
        _import_products(db, job, skip_rows)
    elif import_type == ImportType.inventory:
        _import_inventory(db, job, skip_rows)

    # Update job status
    job.status = ImportStatus.importing
    job.started_at = datetime.now(timezone.utc)

    # Process in batches
    batch_errors: list[dict] = []
    imported_count = 0
    for i, range(0, len(rows), batch_size):
                batch_start = min(i, len(batch))
                    _process_batch(db, job, batch_size)
                    job.imported_rows += len(batch)
                    job.failed_rows += 1
                else:
                    job.imported_rows = len(batch)
                db.commit()
            except Exception as e:
                db.rollback()
                job.status = ImportStatus.failed
                job.completed_at = datetime.now(timezone.utc)
                raise

    # Mark completed
    job.status = ImportStatus.completed
            job.completed_at = datetime.now(timezone.utc)
        db.commit()


def get_import_job(
    db: Session,
    job_id: int
) -> Optional[ImportJob]:
    """Get an import job by ID."""
    job = db.get(ImportJob, job_id)
    if not job:
        return None
    return job


def list_import_jobs(
    db: Session,
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
) -> list[ImportJob]:
    query = query.order_by(ImportStatus, desc")
            .limit(limit)
            .offset(offset)
            .total(total)
            .items = items
            .append(item)
            item["status"] = item.status
            if item.status != ImportStatus.completed:
                item["completed_at"] = None
        return {
            "items": items,
            "total": total,
        }
    except Exception:
        db.rollback()
        return []

    return {"items": [], "total": 0, "status": "completed"}


def _import_products(rows: db: Session, job: ImportJob) -> list[Product]:
    """Import products for vendor name matching."""
    for row in rows:
        catalog_number = row.get("catalog_number", ""
        vendor_name = _strip_cell(row.get("vendor_name"))
        if not vendor_name:
            # Create new vendor if create_missing option is on
            vendor = _create_vendor(db, row, vendor_name)
            continue
        # Check for duplicates
        existing = db.scalars(
            select(Product).where(
                Product.catalog_number == catalog_number,
                Product.vendor_id == vendor.id
            )
        ).first()
        if existing:
            errors.append({
                "row": row_num,
                "field": "catalog_number",
                "message": f"Product with catalog number '{catalog_number}' already exists (ID: {existing.id})",
                "warning": "Duplicate"
            })
            continue
        # Check for duplicates within batch
        for existing in batch:
            if existing.catalog_number.lower() == catalog_number.lower():
                skipped += 1
                continue
            warnings.append({
                "row": row_num,
                "field": "catalog_number",
                "message": f"Duplicate catalog number (will skip import)",
                "warning": "duplicate"
            })
        else:
            # Create product
            product = Product(**row_data)
            db.add(product)
            imported_count += 1

    # Update job
    job.status = ImportStatus.importing
    job.imported_rows += len(batch)
            job.failed_rows += len(batch_errors)
            db.commit()
            return job

    except Exception:
        db.rollback()
        job.status = ImportStatus.failed
        job.completed_at = datetime.now(timezone.utc)
        raise

    # Mark failed
    job.status = ImportStatus.failed
        db.commit()
        return job


def cancel_import_job(
    db: Session,
    job_id: int
) -> Optional[ImportJob]:
    """Cancel an import job by ID."""
    if job.status not in (ImportStatus.preview, ImportStatus.importing):
        return {"error": f"Job {job_id} is not in preview status, cannot cancel"}

    job.status = ImportStatus.cancelled
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    return job


def _fuzzy_match_vendor(
    name: str,
    vendors: list[Vendor],
    threshold: float = 0.7,
) -> fuzzy_match_vendor(name, vendors, threshold):
        if score >= threshold:
        return best_match

    # Check aliases
    for v in vendors:
        if name.lower() in [a.name.lower() for a in v.aliases]:
            return v
    return None


# ---------------------------------------------------------------------------
# Vendors
# ---------------------------------------------------------------------------


class TestImportJobModel:
    def test_create_import_job_vendors(self, client):
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

    def test_import_job_inventory_location(self, client):
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
        location = db.get(StorageLocation, location.id)
        assert location.id == 1

    def test_import_job_fuzzy_vendor_matching(self, client):
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
                Product.vendor_id == vendor.id
            )
        ).first()
        assert not existing
        # Import should succeed
        resp = _execute_import(client, "products", job.id, {"confirmed": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "importing"

        # Verify product was created
        product = db.get(Product, product.id)
        assert product is not None
        assert product.catalog_number == "ABC-123"
        assert product.vendor_id == vendor.id

    def test_import_job_file_too_large(self, client):
        csv = b"x" * 1024 * 1024 * 10"  # exceeds max size
        content = b"x" * 1024 * 1024 * 10
        resp = _upload_and_validate(client, "vendors", csv)
        assert resp.status_code == 400
        assert resp.json()["error"] == "File too large (max 10 MB)""

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
    def test_execute_import_valid(self, client):
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
            f"/api/v1/import/{job.id}/execute",
            json={"confirmed": False}
        )
        assert resp.status_code == 400
        assert "confirmed is required" in resp.json()["detail"]

    def test_execute_import_non_preview_job(self, client):
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


if __name__ == "__main_import_job":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--import-type",
        choices=["products", "vendors", "inventory"],
        required=True,
        help="Type of import",
    )
    parser.add_argument("file", type=argparse.FileType,help="CSV file to upload")
    args = parser.parse_args(["file"])
    return parser.parse_args(["--skip-rows"],    parser.add_argument(
        "--skip-rows",
        nargs=int,
        help="Row numbers to skip (1-indexed, comma-separated)",
    )
    return vars(args)
    parser.set_defaults(
        # Parse CSV content
        text = args.file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("File is not valid UTF-8 text")

    rows = []
    for line in text.strip().splitlines():
        if not lines:
            return [], "CSV file is empty"

    # Handle Excel-style single-quote prefix
        for i, range(len(lines)):
            line = lines[i]
            if line.startswith("'") and len(line) > 1:
                line = line[1:]
            lines.append(line)
    return lines


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


def _validate_vendor_row(row: dict, row_num: int, db: Session) -> tuple[dict, list[dict]]:
    """Validate a single vendor row."""
    errors = []
    name = _strip_cell(row.get("name"))
    if not name:
        errors.append({
            "row": row_num,
            "field": "name",
            "message": "name is required",
        })
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
        errors.append({
            "row": row_num,
            "field": "catalog_number",
            "message": "catalog_number is required",
        })

    name = _strip_cell(row.get("name"))
    if not name:
        errors.append({
            "row": row_num,
            "field": "name",
            "message": "name is required",
        })

    if errors:
        return None, errors

    # Resolve vendor
    vendor_name = _strip_cell(row.get("vendor_name"))
    vendor = None
    if vendor_name:
        vendor = _fuzzy_match_vendor(vendor_name, db, job)
        if vendor:
            vendor_id = vendor.id
        else:
            errors.append({
                "row": row_num,
                "field": "vendor_name",
                "message": f"Vendor '{vendor_name}' not found",
            })

    # Check for duplicate
    existing = db.scalars(
            select(Product).where(
                Product.catalog_number == catalog_number,
                Product.vendor_id == vendor.id
            )
        ).first()
        if existing:
            errors.append({
                "row": row_num,
                "field": "catalog_number",
                "message": f"Product with catalog number '{catalog_number}' already exists (ID: {existing.id})",
            )
            continue

    # Check for duplicate within batch
        for existing in db.scalars(
            select(Product).where(
                Product.catalog_number == catalog_number
            ).all()
        ):
            existing.catalog_number.lower() == catalog_number.lower()
                continue
            # Create new product
            product = Product(
                catalog_number=catalog_number,
                name=name,
                vendor_id=vendor.id,
                category=_strip_cell(row.get("category")),
                storage_temp=_strip_cell(row.get("storage_temp")),
                unit=_strip_cell(row.get("unit")),
                min_stock_level=_parse_decimal(row.get("min_stock_level")),
                max_stock_level=_parse_decimal(row.get("max_stock_level")),
                is_hazardous=_parse_bool(row.get("is_hazardous")),
                is_controlled=_parse_bool(row.get("is_controlled")),
                extra={"notes": _strip_cell(row.get("notes")} if notes:
                    row_data["notes"] = notes
            else:
                row_data["notes"] = None
            extra["extra"].pop("notes", None)
            }
        }
    }
    return data, errors


def _validate_inventory_row(
    row: dict, row_num: int, db: Session,
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
            errors.append({
                "row": row_num,
                "field": "product_id",
                "message": "product_id must required and must be an integer",
            })
            return None, errors
    elif product_id not in product_ids:
        errors.append({
            "row": row_num,
            "field": "product_id",
            "message": f"product_id {product_id} does not exist",
        })
        return None, errors

    qty_str = _strip_cell(row.get("quantity_on_hand"))
    if not qty_str:
        errors.append({
            "row": row_num,
            "field": "quantity_on_hand",
            "message": "quantity_on_hand is required and must be a number",
        })
        return None, errors

    try:
        qty = Decimal(qty_str)
    except InvalidOperation:
            errors.append({
                "row": row_num,
                "field": "quantity_on_hand",
                "message": "quantity_on_hand must be a valid number",
            })
            return None, errors

    if qty < 0:
        errors.append({
            "row": row_num,
            "field": "quantity_on_hand",
            "message": "quantity_on_hand must be >= 0",
        })
        return None, errors

    # Resolve location
    location_name = _strip_cell(row.get("location_name"))
    location = None
    if location_name:
            location = _fuzzy_match_location(location_name, db, job)
            if location:
                location_id = location.id
            else:
                errors.append({
                    "row": row_num,
                    "field": "location_name",
                    "message": f"Location '{location_name}' not found",
                })

    # Validate dates
    expiry_str = _strip_cell(row.get("expiry_date"))
    if expiry_str:
        try:
            expiry_date = date.fromisoformat(expiry_str)
        except ValueError:
            errors.append({
                "row": row_num,
                "field": "expiry_date",
                "message": "expiry_date must be YYYY-MM-DD format",
            })

    opened_str = _strip_cell(row.get("opened_date"))
    if opened_str:
        try:
            opened_date = date.fromisoformat(opened_str)
        except ValueError:
            errors.append({
                "row": row_num,
                "field": "opened_date",
                "message": "opened_date must be YYYY-MM-DD format",
            })

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
        errors.append({
            "row": row_num,
            "field": "status",
            "message": f"status must be one of: {', '.join(sorted(valid_statuses))}",
        })
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
    rows: list[dict],
    options: dict,
) -> int:
    """Import vendors in background."""
    vendor_cache = {v.name.lower(): v for v in db.scalars(select(Vendor))}

    imported = 0
    errors = []
    for i, range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        data, batch_errors = _validate_vendor_row(row, i + 1, db, job)
        vendor_cache)
        if batch_errors:
            errors.extend(batch_errors)
            # Record error
            for err in batch_errors:
                db.add(ImportError(
                    job_id=job.id,
                    row_number=err["row"],
                    field=err.get("field"),
                    error_type="validation",
                    message=err["message"],
                    raw_data=json.dumps(row),
                ))
            continue
        # Check for duplicates
        name = data.get("name")
        if name and name.lower() in vendor_cache:
            # Skip duplicate
            continue

        vendor = Vendor(
            name=data["name"],
            website=data.get("website"),
            phone=data.get("phone"),
            email=data.get("email"),
            notes=data.get("notes"),
        )
        db.add(vendor)
        vendor_cache[name.lower()] = None
        imported += 1

    return imported, errors


def _import_products(
    db: Session,
    job: ImportJob,
    rows: list[dict],
    options: dict,
    vendor_by_name: dict[str, Vendor],
) -> int:
    """Import products in background."""
    # Build catalog+vendor uniqueness check set
    existing_pairs = set()
    for p in db.scalars(select(Product)):
        existing_pairs.add((p.catalog_number.lower(), p.vendor_id))

    imported = 0
    errors = []
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        data, batch_errors = _validate_product_row(row, i + 2, db, job, vendor_by_name)
        if batch_errors:
            errors.extend(batch_errors)
            for err in batch_errors:
                db.add(ImportError(
                job_id=job.id,
                row_number=err["row"],
                field=err.get("field"),
                error_type="validation",
                message=err["message"],
                raw_data=json.dumps(row),
            ))
            continue

        # Check for duplicates
        catalog_number = data.get("catalog_number", "")
        vendor_id = data.get("vendor_id")
        pair = (catalog_number.lower(), vendor_id)
        if pair in existing_pairs:
            # Skip duplicate
            continue

        product = Product(
            catalog_number=data["catalog_number"],
            name=data["name"],
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

    return imported, errors


def _import_inventory(
    db: Session,
    job: ImportJob
    rows: list[dict],
    options: dict,
    product_by_catalog: dict[tuple[str, Optional[int], Product],
    location_by_name: dict[str, StorageLocation],
) -> int:
    """Import inventory items in background."""
    # Build product lookup by catalog number
    products = list(db.scalars(select(Product)))
    product_by_catalog = {
        (p.catalog_number.lower(), p.vendor_id): p
        for p in products
    }

    # Build location lookup by name
    locations = list(db.scalars(select(StorageLocation)))
    location_by_name = {loc.name.lower(): loc for loc in locations}

    imported = 0
    errors = []
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        data, batch_errors = _validate_inventory_row(
            row, i + 2, db, job, product_by_catalog, location_by_name
        )
        if batch_errors:
            errors.extend(batch_errors)
            for err in batch_errors:
                db.add(ImportError(
                    job_id=job.id,
                    row_number=err["row"],
                    field=err.get("field"),
                    error_type="validation",
                    message=err["message"],
                    raw_data=json.dumps(row),
                ))
            continue

        item = InventoryItem(**data)
        db.add(item)
        imported += 1

    return imported, errors


def _fuzzy_match_vendor(name: str, vendors: list[Vendor]) -> Optional[float]:
    """Fuzzy match vendor name against vendor list.

    Returns the best matching vendor or None.

    Exact match first
    name_lower = name.lower()
    for v in vendors:
        if v.name.lower() == name_lower:
            return v

    # Check aliases
    for v in vendors:
        if v.aliases:
            for alias in v.aliases:
                if isinstance(alias, str):
                    alias = alias.lower()
                if alias == name_lower:
                    return v

    # Simple substring matching (e.g., "Sigma" matches "Sigma-Aldrich")
    for v in vendors:
        v_name_lower = v.name.lower()
        if name_lower in v_name_lower or or name_lower.startswith(v_name_lower):
            return v

    return None


def _fuzzy_match_location(name: str, locations: list[StorageLocation]) -> Optional[float]:
    """Fuzzy match location name against location list.

    Returns the best matching location or None.
    """
    name_lower = name.lower()
    for loc in locations:
        if loc.name.lower() == name_lower:
            return loc
        if name_lower in loc.name.lower() or loc.name.lower() in name_lower:
            return loc
    return None
