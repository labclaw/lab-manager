#!/usr/bin/env python3
"""Load OCR results JSON into the documents table.

Usage: python scripts/load_ocr_results.py shenlab-docs/ocr-output/all_scans_qwen3_vl_v2.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from lab_manager.database import get_engine
from lab_manager.models.document import Document


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: python scripts/load_ocr_results.py <ocr_results.json>")

    results_path = Path(sys.argv[1])
    results = json.loads(results_path.read_text())
    print(f"Loaded {len(results)} OCR results from {results_path}")

    engine = get_engine()
    loaded = 0
    skipped = 0

    with Session(engine) as db:
        for entry in results:
            file_name = entry["file"]
            ocr_text = entry.get("fullText", "")
            model = entry.get("model", "unknown")

            # Skip if already in DB
            existing = (
                db.query(Document).filter(Document.file_name == file_name).first()
            )
            if existing:
                skipped += 1
                continue

            doc = Document(
                file_path=f"shenlab-docs/{file_name}",
                file_name=file_name,
                document_type=None,  # will be set by extraction
                ocr_text=ocr_text,
                extraction_model=model,
                status="ocr_complete",
            )
            db.add(doc)
            loaded += 1

        db.commit()

    print(f"Done: {loaded} loaded, {skipped} skipped (already in DB)")


if __name__ == "__main__":
    main()
