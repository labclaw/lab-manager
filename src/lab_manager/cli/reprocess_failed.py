"""Re-process documents that failed OCR or extraction due to rate limiting.

Usage: uv run python scripts/reprocess_failed.py [--delay SECONDS] [--batch-size N]
"""

import argparse
import logging
import time

from lab_manager.database import get_session_factory
from lab_manager.models.document import Document, DocumentStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def reprocess_failed(delay: float = 8.0, batch_size: int = 0):
    """Re-run OCR + extraction on documents missing extracted_data."""
    from pathlib import Path

    from lab_manager.intake.extractor import extract_from_text
    from lab_manager.intake.ocr import extract_text_from_image
    from lab_manager.config import get_settings

    settings = get_settings()
    factory = get_session_factory()
    db = factory()

    try:
        # Find docs that still need meaningful extraction output
        query = (
            db.query(Document)
            .filter(
                Document.status.in_(
                    [DocumentStatus.needs_review, DocumentStatus.ocr_failed]
                )
            )
            .filter(
                (Document.extracted_data.is_(None)) | (Document.vendor_name.is_(None))
            )
            .order_by(Document.id)
        )
        if batch_size > 0:
            query = query.limit(batch_size)

        docs = query.all()
        total = len(docs)
        logger.info("Found %d documents to reprocess", total)

        success = 0
        ocr_fail = 0
        extract_fail = 0

        for i, doc in enumerate(docs, 1):
            logger.info(
                "[%d/%d] Processing doc %d: %s", i, total, doc.id, doc.file_name
            )

            image_path = Path(doc.file_path)
            if not image_path.exists():
                logger.warning("  File not found: %s, skipping", image_path)
                continue

            # OCR (skip if already have text)
            if not doc.ocr_text or not doc.ocr_text.strip():
                try:
                    ocr_text = extract_text_from_image(image_path)
                    doc.ocr_text = ocr_text
                except Exception as e:
                    logger.error("  OCR failed: %s", e)
                    doc.review_notes = f"OCR failed: {e}"
                    doc.status = DocumentStatus.needs_review
                    ocr_fail += 1
                    db.commit()
                    time.sleep(delay)
                    continue

                if not ocr_text or not ocr_text.strip():
                    doc.status = DocumentStatus.ocr_failed
                    doc.review_notes = "OCR returned empty text"
                    ocr_fail += 1
                    db.commit()
                    time.sleep(delay)
                    continue
            else:
                ocr_text = doc.ocr_text

            # Wait between OCR and extraction to avoid rate limits
            time.sleep(delay / 2)

            # Extraction
            try:
                extracted = extract_from_text(ocr_text)
                doc.document_type = extracted.document_type
                doc.vendor_name = extracted.vendor_name
                doc.extracted_data = extracted.model_dump()
                doc.extraction_model = settings.extraction_model
                doc.extraction_confidence = extracted.confidence
                doc.status = DocumentStatus.needs_review
                doc.review_notes = None
                success += 1
                logger.info(
                    "  Extracted: vendor=%s type=%s conf=%s",
                    extracted.vendor_name,
                    extracted.document_type,
                    extracted.confidence,
                )
            except Exception as e:
                logger.error("  Extraction failed: %s", e)
                doc.review_notes = f"Extraction failed: {e}"
                extract_fail += 1

            db.commit()
            time.sleep(delay)

        logger.info(
            "Done. success=%d, ocr_fail=%d, extract_fail=%d",
            success,
            ocr_fail,
            extract_fail,
        )
        try:
            from lab_manager.services.search import sync_documents

            indexed = sync_documents(db)
            logger.info("Indexed %d documents into Meilisearch", indexed)
        except Exception as e:
            logger.warning("Document reindex failed: %s", e)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--delay", type=float, default=8.0, help="Delay between API calls (seconds)"
    )
    parser.add_argument(
        "--batch-size", type=int, default=0, help="Max docs to process (0=all)"
    )
    args = parser.parse_args()
    reprocess_failed(delay=args.delay, batch_size=args.batch_size)
