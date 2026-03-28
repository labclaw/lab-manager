"""Document CRUD endpoints."""

from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lab_manager.api.auth import require_permission
from lab_manager.api.deps import get_db, get_or_404
from lab_manager.exceptions import NotFoundError
from lab_manager.api.pagination import apply_sort, ilike_col, paginate
from lab_manager.models.document import Document, DocumentStatus
from lab_manager.models.order import Order, OrderItem, OrderStatus
from lab_manager.models.vendor import Vendor
from lab_manager.services.vendor_normalize import normalize_vendor

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


def _validate_file_path(v: str) -> str:
    """Allowlist validation: path must resolve under upload_dir or scans_dir."""
    from pathlib import Path
    from urllib.parse import unquote

    from lab_manager.config import get_settings

    decoded = unquote(v)
    p = Path(decoded)

    settings = get_settings()
    upload_root = Path(settings.upload_dir).resolve()
    scans_root = (
        Path(settings.scans_dir).expanduser().resolve() if settings.scans_dir else None
    )

    # If path is relative, resolve against upload_dir
    if not p.is_absolute():
        resolved = (upload_root / p).resolve()
    else:
        resolved = p.resolve()

    allowed_roots = [upload_root]
    if scans_root:
        allowed_roots.append(scans_root)

    if not any(
        str(resolved).startswith(str(root) + "/") or resolved == root
        for root in allowed_roots
    ):
        raise ValueError("File path must be under upload_dir or scans_dir")
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

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_STATUSES:
            raise ValueError(f"status must be one of {_VALID_STATUSES}")
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
        doc = db.scalars(select(Document).where(Document.id == doc_id)).first()
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
            doc.vendor_name = normalize_vendor(extracted.vendor_name)
            doc.extracted_data = extracted.model_dump(mode="json")
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
    from sqlalchemy.orm import selectinload

    from lab_manager.database import get_session_factory
    from lab_manager.models.inventory import InventoryItem
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
        doc = db.scalars(select(Document).where(Document.id == doc_id)).first()
        if doc is None:
            return
        try:
            index_document_record(doc)
        except Exception:
            logger.exception("Failed to index document %d", doc_id)

        # Eager-load order with vendor and items (+ products) in one query
        order = db.scalars(
            select(Order)
            .where(Order.document_id == doc.id)
            .options(
                selectinload(Order.vendor),
                selectinload(Order.items).selectinload(OrderItem.product),
            )
        ).first()
        if not order:
            return

        if order.vendor:
            try:
                index_vendor_record(order.vendor)
            except Exception:
                logger.exception("Failed to index vendor %d", order.vendor.id)

        try:
            index_order_record(order)
        except Exception:
            logger.exception("Failed to index order %d", order.id)

        # Batch-fetch all inventory items for these order items
        oi_ids = [oi.id for oi in order.items]
        inv_items_by_oi: dict[int, list] = {}
        if oi_ids:
            all_inv = db.scalars(
                select(InventoryItem).where(InventoryItem.order_item_id.in_(oi_ids))
            ).all()
            for inv in all_inv:
                inv_items_by_oi.setdefault(inv.order_item_id, []).append(inv)

        for oi in order.items:
            try:
                index_order_item_record(oi)
            except Exception:
                logger.exception("Failed to index order_item %d", oi.id)
            if oi.product:
                try:
                    index_product_record(oi.product)
                except Exception:
                    logger.exception("Failed to index product %d", oi.product.id)
            for inv in inv_items_by_oi.get(oi.id, []):
                try:
                    index_inventory_record(inv)
                except Exception:
                    logger.exception("Failed to index inventory %d", inv.id)

        logger.info("Indexed approved doc %d and related records", doc_id)
    except Exception:
        logger.exception("Failed to index approved doc %d", doc_id)
    finally:
        db.close()


@router.post(
    "/upload",
    status_code=201,
    dependencies=[Depends(require_permission("upload_documents"))],
)
def upload_document(
    file: UploadFile,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Upload a document photo/PDF and trigger background extraction."""
    from datetime import datetime, timezone
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
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    usec = f"{now.microsecond:06d}"
    raw_name = file.filename or "unnamed"
    # Sanitize filename: strip path separators, null bytes, and restrict to safe chars
    import re

    safe_name = raw_name.replace("/", "_").replace("\\", "_").replace("\x00", "")
    safe_name = re.sub(r"[^\w.\-]", "_", safe_name, flags=re.UNICODE)
    if not safe_name or safe_name.startswith("."):
        safe_name = "upload" + safe_name
    saved_name = f"{timestamp}_{usec}_{safe_name}"

    # Save to disk
    upload_dir = Path(
        getattr(request.app.state, "upload_dir", Path(settings.upload_dir).resolve())
    )
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
    # Commit before the background task runs so a fresh session can see the row.
    db.commit()
    db.refresh(doc)

    # Trigger background OCR + extraction
    background_tasks.add_task(_run_extraction, doc.id)
    return doc


@router.get("/stats", dependencies=[Depends(require_permission("view_analytics"))])
def document_stats(db: Session = Depends(get_db)):
    """Dashboard stats."""
    total = db.execute(select(func.count(Document.id))).scalar()
    by_status = dict(
        db.execute(
            select(Document.status, func.count(Document.id)).group_by(Document.status)
        ).all()
    )
    by_type = dict(
        db.execute(
            select(Document.document_type, func.count(Document.id)).group_by(
                Document.document_type
            )
        ).all()
    )
    total_orders = db.execute(select(func.count(Order.id))).scalar()
    total_items = db.execute(select(func.count(OrderItem.id))).scalar()
    total_vendors = db.execute(select(func.count(Vendor.id))).scalar()
    top_vendors = db.execute(
        select(Vendor.name, func.count(Order.id))
        .join(Order, Order.vendor_id == Vendor.id)
        .group_by(Vendor.name)
        .order_by(func.count(Order.id).desc())
        .limit(10)
    ).all()
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
    page_size: int = Query(20, ge=1, le=500),
    status: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None),
    vendor_name: Optional[str] = Query(None),
    extraction_model: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    q = select(Document)
    if status:
        q = q.where(Document.status == status)
    if document_type:
        q = q.where(Document.document_type == document_type)
    if vendor_name:
        q = q.where(ilike_col(Document.vendor_name, vendor_name))
    if extraction_model:
        q = q.where(Document.extraction_model == extraction_model)
    if search:
        q = q.where(
            ilike_col(Document.vendor_name, search)
            | ilike_col(Document.file_name, search)
        )
    q = apply_sort(q, Document, sort_by, sort_dir, _DOC_SORTABLE)
    return paginate(q, db, page, page_size)


@router.post(
    "/", status_code=201, dependencies=[Depends(require_permission("upload_documents"))]
)
def create_document(body: DocumentCreate, db: Session = Depends(get_db)):
    document = Document(**body.model_dump())
    db.add(document)
    db.flush()
    db.refresh(document)
    return document


@router.get("/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Document, document_id, "Document")


@router.patch(
    "/{document_id}", dependencies=[Depends(require_permission("review_documents"))]
)
def update_document(
    document_id: int, body: DocumentUpdate, db: Session = Depends(get_db)
):
    """Partial update any document fields.

    Status changes are restricted — use the /review endpoint for
    approve/reject actions.  PATCH may only set status to values
    that do not bypass the review workflow.
    """
    doc = get_or_404(db, Document, document_id, "Document")
    updates = body.model_dump(exclude_unset=True)

    # Block status changes that bypass the review workflow.
    _REVIEW_STATUSES = {
        DocumentStatus.approved,
        DocumentStatus.rejected,
        DocumentStatus.needs_review,
    }
    new_status = updates.get("status")
    if new_status is not None:
        new_status_enum = DocumentStatus(new_status)
        if new_status_enum in _REVIEW_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Cannot set status to '{new_status}' via PATCH. "
                    f"Use the /review endpoint instead."
                ),
            )
        if new_status_enum == DocumentStatus.deleted:
            raise HTTPException(
                status_code=422,
                detail="Cannot delete via PATCH. Use DELETE instead.",
            )
    if "vendor_name" in updates and updates["vendor_name"]:
        updates["vendor_name"] = normalize_vendor(updates["vendor_name"])
    for key, value in updates.items():
        setattr(doc, key, value)
    db.flush()
    db.refresh(doc)
    return doc


@router.delete(
    "/{document_id}",
    status_code=204,
    dependencies=[Depends(require_permission("delete_records"))],
)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Soft-delete: set status to 'deleted'."""
    doc = get_or_404(db, Document, document_id, "Document")
    doc.status = DocumentStatus.deleted
    db.flush()
    return None


@router.post(
    "/{document_id}/review",
    dependencies=[Depends(require_permission("review_documents"))],
)
def review_document(
    document_id: int,
    body: ReviewAction,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Approve or reject a document extraction."""
    # Acquire row lock to prevent TOCTOU race on concurrent approve requests.
    doc = db.scalars(
        select(Document).where(Document.id == document_id).with_for_update()
    ).first()
    if not doc:
        raise NotFoundError("Document", document_id)

    # BUG 1 FIX: status guard — only allow review on needs_review
    if doc.status == DocumentStatus.processing:
        return JSONResponse(
            status_code=409,
            content={"detail": "Document is still being processed"},
        )
    if doc.status == DocumentStatus.pending:
        return JSONResponse(
            status_code=409,
            content={"detail": "Document has not been processed yet"},
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
        existing_order = db.scalars(
            select(Order).where(Order.document_id == doc.id)
        ).first()
        if not existing_order and doc.extracted_data:
            _create_order_from_doc(doc, db)
    elif body.action == "reject":
        doc.status = DocumentStatus.rejected
        doc.reviewed_by = body.reviewed_by
        doc.review_notes = body.review_notes

    db.flush()
    # Commit before background indexing so the indexer sees approved state and related records.
    db.commit()
    db.refresh(doc)
    if body.action == "approve":
        background_tasks.add_task(_index_approved_doc, doc.id)
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
        vendor = db.scalars(
            select(Vendor).where(
                func.lower(Vendor.name) == func.lower(vendor_name.strip())
            )
        ).first()
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
        received_by=data.get("received_by") or doc.reviewed_by,
        received_date=date_type.today(),
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
            product = db.scalars(
                select(Product).where(
                    Product.catalog_number == catalog_number,
                    Product.vendor_id == vendor.id,
                )
            ).first()
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
                    expiry_date=item.get("expiry_date"),
                )
            )

    # NOTE: Order has no total_amount column. Line-level pricing is
    # available via OrderItem.unit_price × quantity.
