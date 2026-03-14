"""Document CRUD endpoints."""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.api.pagination import apply_sort, escape_like, paginate
from lab_manager.models.document import Document, DocumentStatus
from lab_manager.models.order import Order, OrderItem, OrderStatus
from lab_manager.models.vendor import Vendor

router = APIRouter()

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
    order_id: Optional[int] = None


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
    order_id: Optional[int] = None


class ReviewAction(BaseModel):
    action: Literal["approve", "reject"]
    reviewed_by: str = "scientist"
    review_notes: Optional[str] = None


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
        q = q.filter(Document.vendor_name.ilike(f"%{escape_like(vendor_name)}%"))
    if extraction_model:
        q = q.filter(Document.extraction_model == extraction_model)
    if search:
        escaped = escape_like(search)
        q = q.filter(
            Document.vendor_name.ilike(f"%{escaped}%")
            | Document.file_name.ilike(f"%{escaped}%")
        )
    q = apply_sort(q, Document, sort_by, sort_dir, _DOC_SORTABLE)
    return paginate(q, page, page_size)


@router.post("/", status_code=201)
def create_document(body: DocumentCreate, db: Session = Depends(get_db)):
    document = Document(**body.model_dump())
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get("/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.patch("/{document_id}")
def update_document(
    document_id: int, body: DocumentUpdate, db: Session = Depends(get_db)
):
    """Partial update any document fields."""
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(doc, key, value)
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Soft-delete: set status to 'deleted'."""
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.status = DocumentStatus.deleted
    db.commit()
    return None


@router.post("/{document_id}/review")
def review_document(
    document_id: int, body: ReviewAction, db: Session = Depends(get_db)
):
    """Approve or reject a document extraction."""
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if body.action == "approve":
        doc.status = DocumentStatus.approved
        doc.reviewed_by = body.reviewed_by
        doc.review_notes = body.review_notes
        # Create order if not already linked
        existing_order = db.query(Order).filter(Order.document_id == doc.id).first()
        if not existing_order and doc.extracted_data:
            _create_order_from_doc(doc, db)
    elif body.action == "reject":
        doc.status = DocumentStatus.rejected
        doc.reviewed_by = body.reviewed_by
        doc.review_notes = body.review_notes
    else:
        raise HTTPException(status_code=400, detail="action must be approve or reject")

    db.commit()
    db.refresh(doc)
    return doc


def _create_order_from_doc(doc: Document, db: Session):
    """Create order from document's extracted_data."""
    from datetime import date as date_type

    data = doc.extracted_data
    if not data:
        return

    vendor = None
    vendor_name = data.get("vendor_name") or doc.vendor_name
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
        except ValueError:
            pass

    db.add(order)
    db.flush()

    for item in data.get("items", []):
        db.add(
            OrderItem(
                order_id=order.id,
                catalog_number=item.get("catalog_number"),
                description=item.get("description"),
                quantity=item.get("quantity") or 1,
                unit=item.get("unit"),
                lot_number=item.get("lot_number"),
                batch_number=item.get("batch_number"),
                unit_price=item.get("unit_price"),
            )
        )
