#!/usr/bin/env python3
"""Build comprehensive audit log for the full pipeline.

For each document, records:
  raw image → OCR text → LLM extraction → model review → error analysis

Output: docs/audit_log.json (per-document trace) + docs/audit_summary.json (aggregate)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from lab_manager.database import get_engine
from lab_manager.models.document import Document
from lab_manager.models.order import Order, OrderItem

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y%m%d_%H%M%S",
)
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
OCR_FILE = PROJECT_ROOT / "shenlab-docs" / "ocr-output" / "all_scans_qwen3_vl_v2.json"
REVIEW_DIR = Path("/tmp")


def load_ocr_data() -> dict[str, dict]:
    """Load OCR results keyed by filename."""
    data = json.loads(OCR_FILE.read_text())
    return {entry["file"]: entry for entry in data}


def load_opus_reviews() -> dict[int, dict]:
    """Load Opus 4.6 review results keyed by doc_id."""
    reviews = {}
    for i in range(8):
        path = REVIEW_DIR / f"review_batch_{i}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        entries = data if isinstance(data, list) else data.get("reviews", [data])
        for entry in entries:
            doc_id = entry.get("doc_id")
            if doc_id is not None:
                reviews[doc_id] = entry
    return reviews


def load_gemini_reviews() -> dict[int, dict]:
    """Load Gemini 2.5 Pro review results keyed by doc_id."""
    reviews = {}
    for i in range(8):
        path = REVIEW_DIR / f"gemini_review_{i}.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
            entries = data if isinstance(data, list) else data.get("reviews", [data])
            for entry in entries:
                doc_id = entry.get("doc_id")
                if doc_id is not None:
                    reviews[doc_id] = entry
        except (json.JSONDecodeError, KeyError):
            continue
    return reviews


def load_codex_reviews() -> dict[int, dict]:
    """Load Codex/GPT review results keyed by doc_id."""
    reviews = {}
    for i in range(8):
        path = REVIEW_DIR / f"codex_review_{i}.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
            entries = data if isinstance(data, list) else data.get("reviews", [data])
            for entry in entries:
                doc_id = entry.get("doc_id")
                if doc_id is not None:
                    reviews[doc_id] = entry
        except (json.JSONDecodeError, KeyError):
            continue
    return reviews


def classify_error_category(field: str, detail: str) -> str:
    """Classify an error into a high-level category for pattern analysis."""
    field_lower = field.lower()
    if "document_type" in field_lower:
        return "document_type_misclassification"
    if "po_number" in field_lower or "order_number" in field_lower:
        return "order_number_error"
    if "lot_number" in field_lower or "batch_number" in field_lower:
        return "lot_batch_confusion"
    if "vendor" in field_lower:
        return "vendor_identification_error"
    if "date" in field_lower:
        return "date_interpretation_error"
    if "quantity" in field_lower:
        return "quantity_error"
    if "catalog" in field_lower:
        return "catalog_number_error"
    if "description" in field_lower:
        return "description_error"
    if "delivery" in field_lower or "invoice" in field_lower:
        return "reference_number_error"
    if "items" in field_lower:
        return "items_extraction_error"
    return "other"


def build_audit_entry(
    doc: Document,
    ocr_entry: dict | None,
    order: Order | None,
    order_items: list[OrderItem],
    opus_review: dict | None,
    gemini_review: dict | None,
    codex_review: dict | None,
) -> dict:
    """Build a single audit log entry for one document."""
    entry = {
        "doc_id": doc.id,
        "file_name": doc.file_name,
        "file_path": doc.file_path,
        # Stage 1: Raw scan
        "stage_1_raw": {
            "image_path": doc.file_path,
            "exists": Path(doc.file_path).exists() if doc.file_path else False,
        },
        # Stage 2: OCR
        "stage_2_ocr": {
            "model": ocr_entry.get("model", "unknown") if ocr_entry else doc.extraction_model,
            "elapsed_s": ocr_entry.get("elapsed_s") if ocr_entry else None,
            "text_length": len(doc.ocr_text) if doc.ocr_text else 0,
            "text_preview": (doc.ocr_text[:200] + "...") if doc.ocr_text and len(doc.ocr_text) > 200 else doc.ocr_text,
            "line_count": len(ocr_entry.get("lines", [])) if ocr_entry else None,
            "is_empty": not doc.ocr_text or doc.ocr_text.strip() in ("", "(No text detected)"),
        },
        # Stage 3: LLM extraction
        "stage_3_extraction": {
            "extraction_model": "gemini-2.5-flash",
            "document_type": doc.document_type,
            "vendor_name": doc.vendor_name,
            "confidence": doc.extraction_confidence,
            "extracted_data": doc.extracted_data,
            "status_after_extraction": doc.status,
        },
        # Stage 4: Auto-approval decision
        "stage_4_auto_approval": {
            "threshold": 0.95,
            "confidence": doc.extraction_confidence,
            "auto_approved": doc.status == "approved",
            "sent_to_review": doc.status == "needs_review",
            "reason": (
                "confidence >= 0.95"
                if doc.status == "approved"
                else "confidence < 0.95"
                if doc.status == "needs_review"
                else f"status={doc.status}"
            ),
        },
        # Stage 5: Order creation
        "stage_5_order": None,
        # Stage 6: Model reviews
        "stage_6_reviews": {
            "opus_4_6": None,
            "gemini_2_5_pro": None,
            "codex_gpt": None,
        },
        # Stage 7: Consensus & error analysis
        "stage_7_error_analysis": {
            "consensus_errors": [],
            "error_categories": [],
            "needs_correction": False,
            "correction_priority": "none",
        },
    }

    # Stage 5: Order details
    if order:
        entry["stage_5_order"] = {
            "order_id": order.id,
            "po_number": order.po_number,
            "vendor_id": order.vendor_id,
            "status": order.status,
            "items_count": len(order_items),
            "items": [
                {
                    "id": item.id,
                    "catalog_number": item.catalog_number,
                    "description": item.description,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "lot_number": item.lot_number,
                    "batch_number": item.batch_number,
                    "unit_price": float(item.unit_price) if item.unit_price else None,
                }
                for item in order_items
            ],
        }

    # Stage 6: Reviews
    all_errors = []

    if opus_review:
        opus_errors = opus_review.get("errors", [])
        entry["stage_6_reviews"]["opus_4_6"] = {
            "status": opus_review.get("status", "unknown"),
            "error_count": len(opus_errors),
            "critical_count": sum(1 for e in opus_errors if e.get("severity") == "critical"),
            "minor_count": sum(1 for e in opus_errors if e.get("severity") == "minor"),
            "errors": opus_errors,
        }
        for e in opus_errors:
            all_errors.append({**e, "source": "opus_4_6"})

    if gemini_review:
        gemini_errors = gemini_review.get("errors", [])
        entry["stage_6_reviews"]["gemini_2_5_pro"] = {
            "status": gemini_review.get("status", "unknown"),
            "error_count": len(gemini_errors),
            "errors": gemini_errors,
        }
        for e in gemini_errors:
            all_errors.append({**e, "source": "gemini_2_5_pro"})

    if codex_review:
        codex_errors = codex_review.get("errors", [])
        entry["stage_6_reviews"]["codex_gpt"] = {
            "status": codex_review.get("status", "unknown"),
            "error_count": len(codex_errors),
            "errors": codex_errors,
        }
        for e in codex_errors:
            all_errors.append({**e, "source": "codex_gpt"})

    # Stage 7: Error analysis
    if all_errors:
        # Group errors by field
        by_field = {}
        for e in all_errors:
            field = e.get("field", "unknown")
            by_field.setdefault(field, []).append(e)

        consensus = []
        categories = set()
        has_critical = False

        for field, field_errors in by_field.items():
            sources = list(set(e["source"] for e in field_errors))
            severities = [e.get("severity", "unknown") for e in field_errors]
            is_critical = "critical" in severities

            if is_critical:
                has_critical = True

            category = classify_error_category(field, "")
            categories.add(category)

            consensus.append(
                {
                    "field": field,
                    "sources": sources,
                    "source_count": len(sources),
                    "severity": "critical" if is_critical else "minor",
                    "category": category,
                    "details": [
                        {
                            "source": e["source"],
                            "severity": e.get("severity"),
                            "expected": e.get("expected"),
                            "got": e.get("got") or e.get("extracted"),
                            "detail": e.get("detail") or e.get("message", ""),
                        }
                        for e in field_errors
                    ],
                }
            )

        entry["stage_7_error_analysis"] = {
            "total_errors": len(all_errors),
            "consensus_errors": consensus,
            "error_categories": sorted(categories),
            "needs_correction": has_critical,
            "correction_priority": "high" if has_critical else "low" if all_errors else "none",
        }

    return entry


def build_summary(audit_entries: list[dict]) -> dict:
    """Build aggregate summary from all audit entries."""
    total = len(audit_entries)
    correct = sum(
        1
        for e in audit_entries
        if not e["stage_7_error_analysis"]["needs_correction"]
        and e["stage_7_error_analysis"]["correction_priority"] == "none"
    )
    needs_fix = sum(1 for e in audit_entries if e["stage_7_error_analysis"]["needs_correction"])
    minor_only = total - correct - needs_fix

    # Error category distribution
    category_counts = {}
    for e in audit_entries:
        for cat in e["stage_7_error_analysis"].get("error_categories", []):
            category_counts[cat] = category_counts.get(cat, 0) + 1

    # Top error patterns
    field_error_counts = {}
    for e in audit_entries:
        for ce in e["stage_7_error_analysis"].get("consensus_errors", []):
            field = ce["field"]
            field_error_counts[field] = field_error_counts.get(field, 0) + 1

    # Confidence distribution
    conf_bins = {
        "0.0-0.5": 0,
        "0.5-0.7": 0,
        "0.7-0.8": 0,
        "0.8-0.9": 0,
        "0.9-0.95": 0,
        "0.95-1.0": 0,
    }
    for e in audit_entries:
        conf = e["stage_3_extraction"].get("confidence")
        if conf is None:
            continue
        if conf < 0.5:
            conf_bins["0.0-0.5"] += 1
        elif conf < 0.7:
            conf_bins["0.5-0.7"] += 1
        elif conf < 0.8:
            conf_bins["0.7-0.8"] += 1
        elif conf < 0.9:
            conf_bins["0.8-0.9"] += 1
        elif conf < 0.95:
            conf_bins["0.9-0.95"] += 1
        else:
            conf_bins["0.95-1.0"] += 1

    # Accuracy by confidence
    accuracy_by_conf = {}
    for e in audit_entries:
        conf = e["stage_3_extraction"].get("confidence")
        if conf is None:
            continue
        bucket = (
            "0.0-0.5"
            if conf < 0.5
            else "0.5-0.7"
            if conf < 0.7
            else "0.7-0.8"
            if conf < 0.8
            else "0.8-0.9"
            if conf < 0.9
            else "0.9-0.95"
            if conf < 0.95
            else "0.95-1.0"
        )
        if bucket not in accuracy_by_conf:
            accuracy_by_conf[bucket] = {"total": 0, "correct": 0, "critical_errors": 0}
        accuracy_by_conf[bucket]["total"] += 1
        if e["stage_7_error_analysis"]["correction_priority"] == "none":
            accuracy_by_conf[bucket]["correct"] += 1
        if e["stage_7_error_analysis"]["needs_correction"]:
            accuracy_by_conf[bucket]["critical_errors"] += 1

    # Document type accuracy
    type_accuracy = {}
    for e in audit_entries:
        dtype = e["stage_3_extraction"].get("document_type") or "unknown"
        if dtype not in type_accuracy:
            type_accuracy[dtype] = {"total": 0, "correct": 0, "critical": 0}
        type_accuracy[dtype]["total"] += 1
        if e["stage_7_error_analysis"]["correction_priority"] == "none":
            type_accuracy[dtype]["correct"] += 1
        if e["stage_7_error_analysis"]["needs_correction"]:
            type_accuracy[dtype]["critical"] += 1

    # Vendor name issues
    vendor_issues = []
    for e in audit_entries:
        for ce in e["stage_7_error_analysis"].get("consensus_errors", []):
            if ce["category"] == "vendor_identification_error":
                vendor_issues.append(
                    {
                        "doc_id": e["doc_id"],
                        "file_name": e["file_name"],
                        "details": ce["details"],
                    }
                )

    return {
        "generated_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "pipeline_config": {
            "ocr_model": "Qwen/Qwen3-VL-4B-Instruct",
            "extraction_model": "gemini-2.5-flash",
            "auto_approve_threshold": 0.95,
            "review_models": ["opus_4.6", "gemini_2.5_pro", "codex_gpt"],
        },
        "totals": {
            "documents": total,
            "correct_no_errors": correct,
            "minor_errors_only": minor_only,
            "critical_errors": needs_fix,
            "accuracy_rate": round(correct / total * 100, 1) if total else 0,
            "critical_error_rate": round(needs_fix / total * 100, 1) if total else 0,
        },
        "error_categories": dict(sorted(category_counts.items(), key=lambda x: -x[1])),
        "top_error_fields": dict(sorted(field_error_counts.items(), key=lambda x: -x[1])[:20]),
        "confidence_distribution": conf_bins,
        "accuracy_by_confidence": accuracy_by_conf,
        "document_type_accuracy": type_accuracy,
        "vendor_identification_issues": vendor_issues,
        "key_findings": {
            "most_common_error": max(category_counts, key=category_counts.get) if category_counts else None,
            "confidence_calibration": "Confidence scores may not correlate well with actual accuracy — high-confidence docs still have critical errors"
            if any(accuracy_by_conf.get("0.95-1.0", {}).get("critical_errors", 0) > 0 for _ in [1])
            else "Confidence calibration appears reasonable",
            "document_type_issues": sum(
                1
                for e in audit_entries
                if any(
                    ce["category"] == "document_type_misclassification"
                    for ce in e["stage_7_error_analysis"].get("consensus_errors", [])
                )
            ),
            "order_number_issues": sum(
                1
                for e in audit_entries
                if any(
                    ce["category"] == "order_number_error"
                    for ce in e["stage_7_error_analysis"].get("consensus_errors", [])
                )
            ),
        },
        "recommendations": [
            "Add document type classification as a separate step before field extraction",
            "Implement PO number format validation (regex patterns per vendor)",
            "Add lot/batch number disambiguation rules (VCAT codes, dates vs lot numbers)",
            "Improve vendor name normalization with alias mapping",
            "Consider lower auto-approve threshold given critical errors in high-confidence docs",
            "Add human review for document types: COA, shipping labels, MTA",
            "Implement cross-field validation (e.g., vendor name consistency with known vendors)",
        ],
    }


def main():
    log.info("Building comprehensive audit log...")

    # Load all data sources
    ocr_data = load_ocr_data()
    log.info("Loaded OCR data for %d files", len(ocr_data))

    opus_reviews = load_opus_reviews()
    log.info("Loaded %d Opus 4.6 reviews", len(opus_reviews))

    gemini_reviews = load_gemini_reviews()
    log.info("Loaded %d Gemini 2.5 Pro reviews", len(gemini_reviews))

    codex_reviews = load_codex_reviews()
    log.info("Loaded %d Codex/GPT reviews", len(codex_reviews))

    engine = get_engine()
    audit_entries = []

    with Session(engine) as db:
        docs = db.query(Document).order_by(Document.id).all()
        log.info("Processing %d documents from DB", len(docs))

        for doc in docs:
            # Find matching OCR entry
            ocr_entry = ocr_data.get(doc.file_name)

            # Find order if exists
            order = db.query(Order).filter(Order.document_id == doc.id).first()
            order_items = []
            if order:
                order_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()

            # Find reviews
            opus_review = opus_reviews.get(doc.id)
            gemini_review = gemini_reviews.get(doc.id)
            codex_review = codex_reviews.get(doc.id)

            entry = build_audit_entry(
                doc,
                ocr_entry,
                order,
                order_items,
                opus_review,
                gemini_review,
                codex_review,
            )
            audit_entries.append(entry)

    # Write full audit log
    DOCS_DIR.mkdir(exist_ok=True)
    audit_path = DOCS_DIR / "audit_log.json"
    audit_path.write_text(json.dumps(audit_entries, indent=2, default=str, ensure_ascii=False))
    log.info("Wrote full audit log: %s (%d entries)", audit_path, len(audit_entries))

    # Write aggregate summary
    summary = build_summary(audit_entries)
    summary_path = DOCS_DIR / "audit_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str, ensure_ascii=False))
    log.info("Wrote audit summary: %s", summary_path)

    # Print key stats
    t = summary["totals"]
    log.info("=" * 60)
    log.info("AUDIT SUMMARY")
    log.info("  Total documents: %d", t["documents"])
    log.info("  Correct (no errors): %d (%.1f%%)", t["correct_no_errors"], t["accuracy_rate"])
    log.info("  Minor errors only: %d", t["minor_errors_only"])
    log.info("  Critical errors: %d (%.1f%%)", t["critical_errors"], t["critical_error_rate"])
    log.info("")
    log.info("Error categories:")
    for cat, count in summary["error_categories"].items():
        log.info("  %s: %d docs", cat, count)
    log.info("")
    log.info("Accuracy by confidence:")
    for bucket, stats in summary["accuracy_by_confidence"].items():
        if stats["total"] > 0:
            acc = round(stats["correct"] / stats["total"] * 100, 1)
            log.info(
                "  %s: %d/%d correct (%.1f%%), %d critical",
                bucket,
                stats["correct"],
                stats["total"],
                acc,
                stats["critical_errors"],
            )


if __name__ == "__main__":
    main()
