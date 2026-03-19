#!/usr/bin/env python3
"""Full pipeline: load OCR JSON → LLM extraction → create orders.

Usage:
    python scripts/run_full_pipeline.py shenlab-docs/ocr-output/all_scans_qwen3_vl_v2.json
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from lab_manager.config import get_settings
from lab_manager.database import get_engine
from lab_manager.intake.extractor import extract_from_text
from lab_manager.intake.schemas import ExtractedDocument
from lab_manager.models.document import Document
from lab_manager.models.order import Order, OrderItem
from lab_manager.models.vendor import Vendor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y%m%d_%H%M%S",
)
log = logging.getLogger(__name__)


def find_vendor(vendor_name: str, db: Session) -> Vendor | None:
    """Find vendor by name or alias, case-insensitive."""
    normalized = vendor_name.strip()
    vendor = db.query(Vendor).filter(func.lower(Vendor.name) == func.lower(normalized)).first()
    if vendor:
        return vendor
    vendor = db.query(Vendor).filter(func.lower(Vendor.name).contains(func.lower(normalized))).first()
    if vendor:
        return vendor
    for v in db.query(Vendor).all():
        if v.name.lower() in normalized.lower() or normalized.lower() in v.name.lower():
            return v
        for alias in v.aliases or []:
            if alias.lower() in normalized.lower() or normalized.lower() in alias.lower():
                return v
    return None


def create_order(extracted: ExtractedDocument, doc: Document, db: Session) -> Order | None:
    """Create Order + OrderItems from extracted data."""
    if not extracted.vendor_name:
        return None

    vendor = find_vendor(extracted.vendor_name, db)
    if not vendor:
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

    if extracted.order_date:
        try:
            order.order_date = date.fromisoformat(extracted.order_date)
        except ValueError:
            pass
    if extracted.ship_date:
        try:
            order.ship_date = date.fromisoformat(extracted.ship_date)
        except ValueError:
            pass

    db.add(order)
    db.flush()

    for item in extracted.items:
        db.add(
            OrderItem(
                order_id=order.id,
                catalog_number=item.catalog_number,
                description=item.description,
                quantity=item.quantity or 1,
                unit=item.unit,
                lot_number=item.lot_number,
                batch_number=item.batch_number,
                unit_price=item.unit_price,
            )
        )

    return order


def process_one(entry: dict, db: Session, settings) -> str:
    """Process a single OCR result through extraction + DB storage.

    Returns status string.
    """
    file_name = entry["file"]
    ocr_text = entry.get("fullText", "")

    # Skip if already processed
    existing = db.query(Document).filter(Document.file_name == file_name).first()
    if existing and existing.status not in ("pending", "ocr_complete"):
        return "skipped"

    if not ocr_text or ocr_text.strip() == "(No text detected)":
        if existing:
            existing.status = "empty"
            db.commit()
            return "empty"
        doc = Document(
            file_path=f"shenlab-docs/{file_name}",
            file_name=file_name,
            document_type="unknown",
            ocr_text=ocr_text,
            extraction_model=entry.get("model", "unknown"),
            status="empty",
        )
        db.add(doc)
        db.commit()
        return "empty"

    # Run LLM extraction
    try:
        extracted = extract_from_text(ocr_text)
    except Exception as e:
        log.warning("Extraction failed for %s: %s", file_name, e)
        doc = existing or Document(
            file_path=f"shenlab-docs/{file_name}",
            file_name=file_name,
            ocr_text=ocr_text,
            extraction_model=entry.get("model", "unknown"),
        )
        doc.status = "extraction_failed"
        if not existing:
            db.add(doc)
        db.commit()
        return "extraction_failed"

    # Update or create document
    if existing:
        doc = existing
    else:
        doc = Document(
            file_path=f"shenlab-docs/{file_name}",
            file_name=file_name,
            extraction_model=entry.get("model", "unknown"),
        )
        db.add(doc)

    doc.ocr_text = ocr_text
    doc.document_type = extracted.document_type
    doc.vendor_name = extracted.vendor_name
    doc.extracted_data = extracted.model_dump()
    doc.extraction_confidence = extracted.confidence
    doc.status = "extracted"
    db.flush()

    # Create order if confidence >= threshold
    threshold = settings.auto_approve_threshold
    if extracted.confidence and extracted.confidence >= threshold:
        order = create_order(extracted, doc, db)
        if order:
            doc.status = "approved"
            log.info("  -> auto-approved, order #%d created", order.id)
    else:
        doc.status = "needs_review"

    db.commit()
    return doc.status


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python scripts/run_full_pipeline.py <ocr_results.json>")

    results_path = Path(sys.argv[1])
    results = json.loads(results_path.read_text())
    log.info("Loaded %d OCR results from %s", len(results), results_path)

    settings = get_settings()
    log.info("Extraction model: %s", settings.extraction_model)
    log.info("Auto-approve threshold: %.2f", settings.auto_approve_threshold)

    engine = get_engine()
    stats = {
        "approved": 0,
        "needs_review": 0,
        "empty": 0,
        "skipped": 0,
        "extraction_failed": 0,
    }
    total = len(results)
    t_start = time.time()

    for i, entry in enumerate(results, 1):
        file_name = entry["file"]
        log.info("[%d/%d] %s", i, total, file_name)
        t0 = time.time()

        try:
            with Session(engine) as db:
                status = process_one(entry, db, settings)
        except Exception as e:
            log.error("  -> ERROR: %s", e)
            status = "extraction_failed"

        elapsed = time.time() - t0
        stats[status] = stats.get(status, 0) + 1
        log.info("  -> %s (%.1fs)", status, elapsed)

    total_time = time.time() - t_start
    log.info("=" * 60)
    log.info("DONE in %.0fs (%.1f min)", total_time, total_time / 60)
    log.info("Results: %s", json.dumps(stats, indent=2))

    # Save summary
    summary_path = results_path.parent / f"pipeline_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    summary = {
        "source": str(results_path),
        "total": total,
        "stats": stats,
        "elapsed_s": round(total_time, 1),
        "model": settings.extraction_model,
        "threshold": settings.auto_approve_threshold,
    }
    summary_path.write_text(json.dumps(summary, indent=2))
    log.info("Summary saved to %s", summary_path)


if __name__ == "__main__":
    main()
