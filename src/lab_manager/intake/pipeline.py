"""Document intake pipeline: image → OCR → extract → store."""

from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from lab_manager.config import get_settings
from lab_manager.intake.ocr import extract_text_from_image
from lab_manager.intake.extractor import extract_from_text
from lab_manager.intake.schemas import ExtractedDocument
from lab_manager.models.document import Document
from lab_manager.models.order import Order, OrderItem
from lab_manager.models.vendor import Vendor


def _find_vendor(vendor_name: str, db: Session) -> Vendor | None:
    """Find vendor by name or alias, case-insensitive."""
    normalized = vendor_name.strip()
    # Try exact match first (case-insensitive)
    vendor = (
        db.query(Vendor)
        .filter(func.lower(Vendor.name) == func.lower(normalized))
        .first()
    )
    if vendor:
        return vendor
    # Try partial match
    vendor = (
        db.query(Vendor)
        .filter(func.lower(Vendor.name).contains(func.lower(normalized)))
        .first()
    )
    if vendor:
        return vendor
    # Try reverse partial (vendor name in extracted name) and alias check
    for v in db.query(Vendor).all():
        if v.name.lower() in normalized.lower() or normalized.lower() in v.name.lower():
            return v
        for alias in v.aliases or []:
            if (
                alias.lower() in normalized.lower()
                or normalized.lower() in alias.lower()
            ):
                return v
    return None


def process_document(image_path: Path, db: Session) -> Document:
    """Process a scanned document image end-to-end.

    1. Copy file to uploads/
    2. Run OCR
    3. Extract structured data
    4. Save Document record
    5. If high confidence, create Order + OrderItems
    """
    # Dedupe: skip if this filename was already processed
    existing = db.query(Document).filter(Document.file_name == image_path.name).first()
    if existing:
        return existing

    settings = get_settings()

    # 1. Copy to uploads
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / image_path.name
    if not dest.exists():
        shutil.copy2(image_path, dest)

    # 2. OCR
    ocr_text = extract_text_from_image(image_path)

    # 3. Extract structured data
    extracted = extract_from_text(ocr_text)

    # 4. Save Document
    doc = Document(
        file_path=str(dest),
        file_name=image_path.name,
        document_type=extracted.document_type,
        vendor_name=extracted.vendor_name,
        ocr_text=ocr_text,
        extracted_data=extracted.model_dump(),
        extraction_model=settings.extraction_model,
        extraction_confidence=extracted.confidence,
        status="extracted",
    )
    db.add(doc)
    db.flush()

    # 5. Auto-create order if confidence is high enough
    threshold = settings.auto_approve_threshold
    if extracted.confidence and extracted.confidence >= threshold:
        _create_order_from_extraction(extracted, doc, db)
        doc.status = "approved"
    else:
        doc.status = "needs_review"

    db.commit()
    db.refresh(doc)
    return doc


def _create_order_from_extraction(
    extracted: ExtractedDocument, doc: Document, db: Session
) -> Order:
    """Create Order + OrderItems from extracted data."""
    # Find or create vendor
    vendor = _find_vendor(extracted.vendor_name, db) if extracted.vendor_name else None
    if not vendor and extracted.vendor_name:
        vendor = Vendor(name=extracted.vendor_name)
        db.add(vendor)
        db.flush()

    order = Order(
        po_number=extracted.po_number,
        vendor_id=vendor.id,
        delivery_number=extracted.delivery_number,
        invoice_number=extracted.invoice_number,
        status="received",
        document_id=doc.id,
        received_by=extracted.received_by,
    )

    # Parse dates safely
    if extracted.order_date:
        try:
            from datetime import date

            order.order_date = date.fromisoformat(extracted.order_date)
        except ValueError:
            pass

    db.add(order)
    db.flush()

    for item_data in extracted.items:
        order_item = OrderItem(
            order_id=order.id,
            catalog_number=item_data.catalog_number,
            description=item_data.description,
            quantity=item_data.quantity or 1,
            unit=item_data.unit,
            lot_number=item_data.lot_number,
            batch_number=item_data.batch_number,
        )
        db.add(order_item)

    return order
