#!/usr/bin/env python3
"""One-time script: normalize vendor_name on all existing documents.

Usage (inside the app container or with DATABASE_URL set):
    python scripts/normalize_existing_vendors.py

Or via docker compose:
    docker compose exec app python scripts/normalize_existing_vendors.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on path when run standalone
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lab_manager.services.vendor_normalize import normalize_vendor  # noqa: E402


def main() -> None:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from lab_manager.models.document import Document  # noqa: E402

    import os

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://labmanager:labmanager@localhost:5432/labmanager",
    )
    engine = create_engine(db_url)

    updated = 0
    skipped = 0

    with Session(engine) as db:
        docs = db.scalars(
            select(Document).where(Document.vendor_name.isnot(None))
        ).all()

        for doc in docs:
            original = doc.vendor_name
            normalized = normalize_vendor(original)
            if normalized != original:
                doc.vendor_name = normalized
                updated += 1
                print(f"  [{doc.id}] {original!r} -> {normalized!r}")
            else:
                skipped += 1

        db.commit()

    print(f"\nDone: {updated} updated, {skipped} unchanged, {updated + skipped} total")


if __name__ == "__main__":
    main()
