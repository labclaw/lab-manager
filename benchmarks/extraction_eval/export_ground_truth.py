"""Export ground truth from approved documents in the database.

Extracts human-approved document extractions to serve as ground truth
for the evaluation harness.

Usage:
    python -m benchmarks.extraction-eval.export_ground_truth
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def export_ground_truth(output_path: Path, limit: int = 100) -> int:
    """Export approved documents from DB as ground truth JSON.

    Args:
        output_path: Where to write the JSON file.
        limit: Max documents to export.

    Returns:
        Number of documents exported.
    """
    from sqlalchemy import select
    from sqlmodel import Session

    from lab_manager.database import get_engine
    from lab_manager.models.document import Document, DocumentStatus

    engine = get_engine()
    ground_truth = []

    with Session(engine) as db:
        stmt = (
            select(Document)
            .where(Document.status == DocumentStatus.approved)
            .where(Document.extracted_data.isnot(None))
            .where(Document.ocr_text.isnot(None))
            .limit(limit)
        )
        docs = db.exec(stmt).all()

        for doc in docs:
            ground_truth.append(
                {
                    "id": doc.id,
                    "file_name": doc.file_name,
                    "vendor_name": doc.vendor_name,
                    "document_type": doc.document_type,
                    "ocr_text": doc.ocr_text,
                    "extracted_data": doc.extracted_data,
                    "extraction_confidence": doc.extraction_confidence,
                }
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(ground_truth, indent=2, default=str))
    logger.info("Exported %d documents to %s", len(ground_truth), output_path)
    return len(ground_truth)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    output_path = Path(__file__).parent / "ground_truth.json"
    count = export_ground_truth(output_path)
    print(f"Exported {count} ground truth documents to {output_path}")
    if count == 0:
        print("No approved documents found. Approve some documents first.")
        sys.exit(1)
