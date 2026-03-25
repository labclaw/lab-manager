"""Background task system for scalable async processing.

Uses a lightweight thread-pool executor with Redis-backed queue for
distributing work across multiple workers. Falls back to in-process
execution when Redis is unavailable.

Task categories:
- DOCUMENT: OCR, VLM extraction, consensus (CPU/IO heavy)
- SEARCH: Meilisearch indexing, re-indexing
- ALERT: Low-stock checks, expiry notifications
- ANALYTICS: Report generation, aggregation
- MAINTENANCE: Cleanup, archival
"""

from __future__ import annotations

import enum


class TaskPriority(enum.IntEnum):
    """Task priority levels (lower = higher priority)."""

    CRITICAL = 0  # Immediate: auth, health
    HIGH = 1  # User-facing: document processing
    NORMAL = 2  # Background: search indexing
    LOW = 3  # Deferred: analytics, cleanup


class TaskCategory(str, enum.Enum):
    """Task categories for routing to appropriate workers."""

    DOCUMENT = "document"
    SEARCH = "search"
    ALERT = "alert"
    ANALYTICS = "analytics"
    MAINTENANCE = "maintenance"
