"""Document intake pipeline: image -> OCR -> extract -> store."""

from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path

from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from lab_manager.config import get_settings
from lab_manager.intake.extractor import extract_from_text
from lab_manager.intake.ocr import extract_text_from_image
from lab_manager.models.document import Document, DocumentStatus
from lab_manager.models.vendor import Vendor
from lab_manager.services.vendor_normalize import normalize_vendor

logger = logging.getLogger(__name__)


def _find_vendor(vendor_name: str, db: Session) -> Vendor | None:
    """Find vendor by name or alias, case-insensitive."""
    normalized = vendor_name.strip()
    key = normalized.lower()
    # Exact match (case-insensitive)
    vendor = db.scalars(select(Vendor).where(func.lower(Vendor.name) == key)).first()
    if vendor:
        return vendor
    # Substring match (either direction: query in vendor name, or vendor name in query)
    vendor = db.scalars(
        select(Vendor).where(
            func.lower(Vendor.name).contains(key)
            | literal(key).like(func.concat("%", func.lower(Vendor.name), "%"))
        )
    ).first()
    if vendor:
        return vendor
    # Alias check — requires scanning JSON column
    for v in db.scalars(select(Vendor).where(Vendor.aliases.isnot(None))).all():
        for alias in v.aliases or []:
            alias_lower = alias.lower()
            if alias_lower in key or key in alias_lower:
                return v
    return None


def process_document(image_path: Path, db: Session) -> Document:
    """Process a scanned document image end-to-end.

    1. Copy file to uploads/ (with content-hash dedup for same-name files)
    2. Run OCR
    3. Extract structured data
    4. Save Document record in needs_review status

    OCR or extraction failures are recorded in review_notes rather than
    propagated, so every submitted file gets a trackable Document record.
    """
    # Dedupe: use content hash to detect true duplicates (not just filename)
    file_bytes = image_path.read_bytes()
    file_hash = hashlib.sha256(file_bytes).hexdigest()[:16]

    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Build unique dest filename: if same name already exists, append hash
    dest = upload_dir / image_path.name
    dest_name = image_path.name
    if dest.exists():
        dest_name = f"{image_path.stem}_{file_hash}{image_path.suffix}"
        dest = upload_dir / dest_name

    # Check by dest_name (the actual name that will be stored)
    existing = db.scalars(
        select(Document).where(Document.file_name == dest_name)
    ).first()
    if existing:
        return existing

    if not dest.exists():
        shutil.copy2(image_path, dest)

    # Create document record immediately so failures are tracked
    doc = Document(
        file_path=str(dest),
        file_name=dest_name,
        status=DocumentStatus.pending,
    )
    db.add(doc)
    db.flush()

    # OCR
    try:
        ocr_text = extract_text_from_image(image_path)
        doc.ocr_text = ocr_text
    except Exception as e:
        logger.error("OCR failed for %s: %s", image_path.name, e)
        doc.status = DocumentStatus.needs_review
        doc.review_notes = f"OCR failed: {e}"
        db.commit()
        return doc

    # Short-circuit on empty OCR — don't waste VLM API calls on blank pages
    if not ocr_text or not ocr_text.strip():
        logger.warning("Empty OCR text for %s, marking as ocr_failed", image_path.name)
        doc.status = DocumentStatus.ocr_failed
        doc.review_notes = "OCR returned empty text"
        db.commit()
        return doc

    # Extract structured data
    from lab_manager.intake.validator import validate

    try:
        extracted = extract_from_text(ocr_text)
        if extracted is None:
            logger.error("Extraction returned None for %s", image_path.name)
            doc.status = DocumentStatus.needs_review
            doc.review_notes = "Extraction failed: no result returned"
        else:
            doc.document_type = extracted.document_type
            doc.vendor_name = normalize_vendor(extracted.vendor_name)
            doc.extracted_data = extracted.model_dump()
            doc.extraction_model = settings.extraction_model
            doc.extraction_confidence = extracted.confidence
            doc.status = DocumentStatus.needs_review

            # Run validation on extracted data
            validation_issues = validate(extracted.model_dump())
            if validation_issues:
                logger.warning(
                    "Validation issues for %s: %s", image_path.name, validation_issues
                )
                issues_str = "; ".join(
                    f"{i['field']}: {i['issue']}" for i in validation_issues
                )
                doc.review_notes = f"Validation issues: {issues_str}"
    except Exception as e:
        logger.error("Extraction failed for %s: %s", image_path.name, e)
        doc.status = DocumentStatus.needs_review
        doc.review_notes = f"Extraction failed: {e}"

    db.commit()
    db.refresh(doc)
    return doc
