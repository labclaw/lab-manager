#!/usr/bin/env python3
"""Process all scanned documents in shenlab-docs/ through the intake pipeline."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from sqlalchemy.orm import Session

from lab_manager.database import get_engine
from lab_manager.intake.pipeline import process_document


def main():
    scan_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("shenlab-docs")
    if not scan_dir.exists():
        raise SystemExit(f"Directory not found: {scan_dir}")

    engine = get_engine()
    images = sorted(p for p in scan_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff"})
    print(f"Found {len(images)} images in {scan_dir}")

    for i, img in enumerate(images, 1):
        print(f"[{i}/{len(images)}] {img.name}...", end=" ", flush=True)
        t0 = time.time()
        try:
            with Session(engine) as db:
                doc = process_document(img, db)
                print(f"-> {doc.status} ({time.time() - t0:.1f}s)")
        except Exception as e:
            print(f"ERROR: {e}")


if __name__ == "__main__":
    main()
