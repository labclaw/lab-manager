"""Document CRUD endpoints."""

from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import apply_sort, ilike_col, paginate
from lab_manager.models.document import Document, DocumentStatus
from lab_manager.models.order import Order, OrderItem, OrderStatus
from lab_manager.models.vendor import Vendor

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/tiff",
    "application/pdf",
}
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


_DOC_SORTABLE = {
    "id",
    "created_at",
    "updated_at",
    "file_name",
    "document_type",
    "vendor_name",
    "status",
    "extraction_confidence",
}

_VALID_STATUSES = {s.value for s in DocumentStatus}

_BLOCKED_PREFIXES = ("/etc/", "/proc/", "/sys/", "/var/", "/root/", "/home/")


def _validate_file_path(v: str) -> str:
    """Check for path traversal and blocked system directories."""
    from pathlib import PurePosixPath

    parts = PurePosixPath(v).parts
    if ".." in parts:
        raise ValueError("Path traversal not allowed")
    if any(v.startswith(b) for b in _BLOCKED_PREFIXES):
        raise ValueError("Path traversal not allowed")
    return v


class DocumentCreate(BaseModel):
    file_path: str
    file_name: str
    document_type: Optional[str] = None
    vendor_name: Optional[str] = None
    ocr_text: Optional[str] = None
    extracted_data: Optional[dict] = None
    extraction_model: Optional[str] = None
    extraction_confidence: Optional[float] = None
    status: str = DocumentStatus.pending
    review_notes: Optional[str] = None
    reviewed_by: Optional[str] = None

    @field_validator("file_path")
    @classmethod
    def no_path_traversal(cls, v: str) -> str:
        return _validate_file_path(v)

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in _VALID_STATUSES:
            raise ValueError(f"status must be one of {_VALID_STATUSES}")
        return v


class DocumentUpdate(BaseModel):
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    document_type: Optional[str] = None
    vendor_name: Optional[str] = None
    ocr_text: Optional[str] = None
    extracted_data: Optional[dict] = None
    extraction_model: Optional[str] = None
    extraction_confidence: Optional[float] = None
    status: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_by: Optional[str] = None

    @field_validator("file_path")
    @classmethod
    def no_path_traversal(cls, v: str | None) -> str | None:
        if v is not None:
            _validate_file_path(v)
        return v


class ReviewAction(BaseModel):
    action: Literal["approve", "reject"]
    reviewed_by: str = "scientist"
    review_notes: Optional[str] = None


def _run_extraction(doc_id: int) -> None:
    """Background task: OCR + extract structured data from an uploaded document.

    Opens its own DB session (the request session is already closed).
    Failures set status to needs_review with review_notes.
    """
    from pathlib import Path

    from lab_manager.database import get_session_factory
    from lab_manager.intake.extractor import extract_from_text
    from lab_manager.intake.ocr import extract_text_from_image

    factory = get_session_factory()
    db = factory()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc is None:
            logger.error("Document %d not found for extraction", doc_id)
            return

        image_path = Path(doc.file_path)

        # OCR
        try:
            ocr_text = extract_text_from_image(image_path)
            doc.ocr_text = ocr_text
        except Exception as e:
            logger.error("OCR failed for doc %d: %s", doc_id, e)
            doc.status = DocumentStatus.needs_review
            doc.review_notes = f"OCR failed: {e}"
            db.commit()
            return

        if not ocr_text or not ocr_text.strip():
            logger.warning("Empty OCR text for doc %d, marking as ocr_failed", doc_id)
            doc.status = DocumentStatus.ocr_failed
            doc.review_notes = "OCR returned empty text"
            db.commit()
            return

        # Extract structured data
        try:
            from lab_manager.config import get_settings

            settings = get_settings()
            extracted = extract_from_text(ocr_text)
            doc.document_type = extracted.document_type
            doc.vendor_name = extracted.vendor_name
            doc.extracted_data = extracted.model_dump()
            doc.extraction_model = settings.extraction_model
            doc.extraction_confidence = extracted.confidence
            doc.status = DocumentStatus.needs_review
        except Exception as e:
            logger.error("Extraction failed for doc %d: %s", doc_id, e)
            doc.status = DocumentStatus.needs_review
            doc.review_notes = f"Extraction failed: {e}"

        db.commit()
        logger.info("Extraction complete for doc %d, status=%s", doc_id, doc.status)
    except Exception:
        logger.exception("Unexpected error in extraction for doc %d", doc_id)
        db.rollback()
    finally:
        db.close()


def _index_approved_doc(doc_id: int) -> None:
    """Background task: index an approved document and all related records in Meilisearch."""
    from lab_manager.database import get_session_factory
    from lab_manager.models.inventory import InventoryItem
    from lab_manager.models.product import Product
    from lab_manager.services.search import (
        index_document_record,
        index_inventory_record,
        index_order_item_record,
        index_order_record,
        index_product_record,
        index_vendor_record,
    )

    factory = get_session_factory()
    db = factory()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc is None:
            return
        try:
            index_document_record(doc)
        except Exception:
            logger.exception("Failed to index document %d", doc_id)

        order = db.query(Order).filter(Order.document_id == doc.id).first()
        if not order:
            return

        if order.vendor_id:
            vendor = db.query(Vendor).filter(Vendor.id == order.vendor_id).first()
            if vendor:
                try:
                    index_vendor_record(vendor)
                except Exception:
                    logger.exception("Failed to index vendor %d", vendor.id)

        try:
            index_order_record(order)
        except Exception:
            logger.exception("Failed to index order %d", order.id)

        items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        for oi in items:
            try:
                index_order_item_record(oi)
            except Exception:
                logger.exception("Failed to index order_item %d", oi.id)
            if oi.product_id:
                product = db.query(Product).filter(Product.id == oi.product_id).first()
                if product:
                    try:
                        index_product_record(product)
                    except Exception:
                        logger.exception("Failed to index product %d", product.id)
                inv_items = (
                    db.query(InventoryItem)
                    .filter(InventoryItem.order_item_id == oi.id)
                    .all()
                )
                for inv in inv_items:
                    try:
                        index_inventory_record(inv)
                    except Exception:
                        logger.exception("Failed to index inventory %d", inv.id)

        logger.info("Indexed approved doc %d and related records", doc_id)
    except Exception:
        logger.exception("Failed to index approved doc %d", doc_id)
    finally:
        db.close()


@router.post("/upload", status_code=201)
def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Upload a document photo/PDF and trigger background extraction."""
    from datetime import datetime
    from pathlib import Path

    from lab_manager.config import get_settings

    # Validate content type
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        return JSONResponse(
            status_code=400,
            content={
                "detail": f"File type '{file.content_type}' not allowed. "
                f"Accepted: {', '.join(sorted(_ALLOWED_CONTENT_TYPES))}"
            },
        )

    # Read file content and check size
    content = file.file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        return JSONResponse(
            status_code=413,
            content={
                "detail": f"File too large ({len(content)} bytes). "
                f"Maximum: {_MAX_UPLOAD_BYTES} bytes (50 MB)."
            },
        )

    # Build unique filename with timestamp prefix (include microseconds for uniqueness)
    settings = get_settings()
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    usec = f"{now.microsecond:06d}"
    raw_name = file.filename or "unnamed"
    # Strip directory separators and null bytes to prevent path traversal
    safe_name = raw_name.replace("/", "_").replace("\\", "_").replace("\x00", "")
    saved_name = f"{timestamp}_{usec}_{safe_name}"

    # Save to disk
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / saved_name
    dest.write_bytes(content)

    logger.info("Uploaded file %s (%d bytes)", saved_name, len(content))

    # Create Document record in processing state
    doc = Document(
        file_path=str(dest),
        file_name=saved_name,
        status=DocumentStatus.processing,
    )
    db.add(doc)
    db.flush()
    db.refresh(doc)

    # Trigger background OCR + extraction
    background_tasks.add_task(_run_extraction, doc.id)
    return doc


@router.get("/stats")
def document_stats(db: Session = Depends(get_db)):
    """Dashboard stats."""
    total = db.query(func.count(Document.id)).scalar()
    by_status = dict(
        db.query(Document.status, func.count(Document.id))
        .group_by(Document.status)
        .all()
    )
    by_type = dict(
        db.query(Document.document_type, func.count(Document.id))
        .group_by(Document.document_type)
        .all()
    )
    total_orders = db.query(func.count(Order.id)).scalar()
    total_items = db.query(func.count(OrderItem.id)).scalar()
    total_vendors = db.query(func.count(Vendor.id)).scalar()
    top_vendors = (
        db.query(Vendor.name, func.count(Order.id))
        .join(Order, Order.vendor_id == Vendor.id)
        .group_by(Vendor.name)
        .order_by(func.count(Order.id).desc())
        .limit(10)
        .all()
    )
    return {
        "total_documents": total,
        "by_status": by_status,
        "by_type": by_type,
        "total_orders": total_orders,
        "total_items": total_items,
        "total_vendors": total_vendors,
        "top_vendors": [{"name": n, "count": c} for n, c in top_vendors],
    }


@router.get("/")
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None),
    vendor_name: Optional[str] = Query(None),
    extraction_model: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    q = db.query(Document)
    if status:
        q = q.filter(Document.status == status)
    if document_type:
        q = q.filter(Document.document_type == document_type)
    if vendor_name:
        q = q.filter(ilike_col(Document.vendor_name, vendor_name))
    if extraction_model:
        q = q.filter(Document.extraction_model == extraction_model)
    if search:
        q = q.filter(
            ilike_col(Document.vendor_name, search)
            | ilike_col(Document.file_name, search)
        )
    q = apply_sort(q, Document, sort_by, sort_dir, _DOC_SORTABLE)
    return paginate(q, page, page_size)


@router.post("/", status_code=201)
def create_document(body: DocumentCreate, db: Session = Depends(get_db)):
    document = Document(**body.model_dump())
    db.add(document)
    db.flush()
    db.refresh(document)
    return document


@router.get("/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Document, document_id, "Document")


@router.patch("/{document_id}")
def update_document(
    document_id: int, body: DocumentUpdate, db: Session = Depends(get_db)
):
    """Partial update any document fields."""
    doc = get_or_404(db, Document, document_id, "Document")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(doc, key, value)
    db.flush()
    db.refresh(doc)
    return doc


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Soft-delete: set status to 'deleted'."""
    doc = get_or_404(db, Document, document_id, "Document")
    doc.status = DocumentStatus.deleted
    db.flush()
    return None


@router.post("/{document_id}/review")
def review_document(
    document_id: int,
    body: ReviewAction,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Approve or reject a document extraction."""
    doc = get_or_404(db, Document, document_id, "Document")

    # BUG 1 FIX: status guard — only allow review on needs_review
    if doc.status == DocumentStatus.processing:
        return JSONResponse(
            status_code=409,
            content={"detail": "Document is still being processed"},
        )
    if doc.status in (
        DocumentStatus.approved,
        DocumentStatus.rejected,
        DocumentStatus.deleted,
    ):
        return JSONResponse(
            status_code=409,
            content={"detail": f"Document already {doc.status}"},
        )

    if body.action == "approve":
        doc.status = DocumentStatus.approved
        doc.reviewed_by = body.reviewed_by
        doc.review_notes = body.review_notes
        # Create order if not already linked
        existing_order = db.query(Order).filter(Order.document_id == doc.id).first()
        if not existing_order and doc.extracted_data:
            _create_order_from_doc(doc, db)
        # Index all created records in Meilisearch (background)
        db.flush()
        background_tasks.add_task(_index_approved_doc, doc.id)
    elif body.action == "reject":
        doc.status = DocumentStatus.rejected
        doc.reviewed_by = body.reviewed_by
        doc.review_notes = body.review_notes

    db.flush()
    db.refresh(doc)
    return doc


def _create_order_from_doc(doc: Document, db: Session):
    """Create order from document's extracted_data.

    Also upserts Product records and creates InventoryItem entries for each
    order line item.
    """
    from datetime import date as date_type

    from lab_manager.models.inventory import InventoryItem
    from lab_manager.models.product import Product

    data = doc.extracted_data
    if not data:  # pragma: no cover — caller checks extracted_data first
        return

    # BUG 2 FIX: validate before creating order
    vendor_name = data.get("vendor_name") or doc.vendor_name
    items = data.get("items", [])
    if (not vendor_name or not vendor_name.strip()) and not items:
        logger.warning(
            "Skipping order creation for doc %d: no vendor_name and no items",
            doc.id,
        )
        return
    if not items:
        logger.warning(
            "Creating order for doc %d without items (vendor=%s)",
            doc.id,
            vendor_name,
        )

    vendor = None
    if vendor_name:
        vendor = (
            db.query(Vendor)
            .filter(func.lower(Vendor.name) == func.lower(vendor_name.strip()))
            .first()
        )
        if not vendor:
            vendor = Vendor(name=vendor_name)
            db.add(vendor)
            db.flush()

    order = Order(
        po_number=data.get("po_number"),
        vendor_id=vendor.id if vendor else None,
        delivery_number=data.get("delivery_number"),
        invoice_number=data.get("invoice_number"),
        status=OrderStatus.received,
        document_id=doc.id,
        received_by=data.get("received_by"),
    )
    if data.get("order_date"):
        try:
            order.order_date = date_type.fromisoformat(data["order_date"])
        except ValueError as e:
            logger.warning(
                "Failed to parse order_date from document: %s",
                data["order_date"],
                exc_info=e,
            )

    db.add(order)
    db.flush()

    for item in data.get("items", []):
        # --- upsert Product ---
        catalog_number = item.get("catalog_number")
        product = None
        if catalog_number and vendor:
            product = (
                db.query(Product)
                .filter(
                    Product.catalog_number == catalog_number,
                    Product.vendor_id == vendor.id,
                )
                .first()
            )
        if not product and catalog_number:
            product = Product(
                catalog_number=catalog_number,
                name=item.get("description") or catalog_number,
                vendor_id=vendor.id if vendor else None,
                category="Uncategorized",
                storage_temp=item.get("storage_temp"),
            )
            db.add(product)
            db.flush()

        # --- create OrderItem ---
        oi = OrderItem(
            order_id=order.id,
            catalog_number=catalog_number,
            description=item.get("description"),
            quantity=item.get("quantity") or 1,
            unit=item.get("unit"),
            lot_number=item.get("lot_number"),
            batch_number=item.get("batch_number"),
            unit_price=item.get("unit_price"),
            product_id=product.id if product else None,
        )
        db.add(oi)
        db.flush()

        # --- create InventoryItem ---
        if product:
            db.add(
                InventoryItem(
                    product_id=product.id,
                    order_item_id=oi.id,
                    lot_number=item.get("lot_number"),
                    quantity_on_hand=item.get("quantity") or 1,
                    unit=item.get("unit"),
                    status="available",
                )
            )

    # NOTE: Order has no total_amount column. Line-level pricing is
    # available via OrderItem.unit_price × quantity.
