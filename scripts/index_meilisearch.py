#!/usr/bin/env python3
"""Full reindex of all database tables into Meilisearch.

Usage:
    uv run python scripts/index_meilisearch.py
"""

from __future__ import annotations

import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    from lab_manager.database import get_session_factory
    from lab_manager.services.search import get_search_client, sync_all

    # Verify Meilisearch is reachable
    client = get_search_client()
    try:
        info = client.get_version()
        logger.info("Meilisearch version: %s", info.get("pkgVersion", "unknown"))
    except Exception as exc:
        logger.error("Cannot connect to Meilisearch: %s", exc)
        sys.exit(1)

    # Open DB session
    factory = get_session_factory()
    db = factory()
    try:
        logger.info("Starting full reindex...")
        t0 = time.time()
        counts = sync_all(db)
        elapsed = time.time() - t0

        logger.info("--- Reindex complete in %.2fs ---", elapsed)
        total = 0
        for index_name, count in counts.items():
            logger.info("  %-15s %d documents", index_name, count)
            total += count
        logger.info("  %-15s %d documents", "TOTAL", total)
    finally:
        db.close()


if __name__ == "__main__":
    main()
