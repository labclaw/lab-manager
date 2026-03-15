"""Shared pagination helper for list endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Query

# Escape character used in all LIKE patterns.
LIKE_ESCAPE = "\\"


def escape_like(value: str) -> str:
    """Escape special characters for SQL LIKE patterns.

    All callers MUST pass ``escape=LIKE_ESCAPE`` (or use ``ilike_escaped``)
    so the database honours the backslash escapes.
    """
    return (
        value.replace(LIKE_ESCAPE, LIKE_ESCAPE + LIKE_ESCAPE)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )


def apply_sort(query, model, sort_by: str, sort_dir: str, allowed: set[str]):
    """Validate sort_by against allowed columns and apply ordering."""
    if sort_by not in allowed:
        sort_by = "id"
    col = getattr(model, sort_by, model.id)
    return query.order_by(col.desc() if sort_dir == "desc" else col.asc())


def paginate(query: Query, page: int = 1, page_size: int = 50) -> dict:
    """Apply pagination to a SQLAlchemy query and return metadata.

    Returns:
        dict with keys: items, total, page, page_size, pages
    """
    skip = (page - 1) * page_size
    items = query.offset(skip).limit(page_size).all()
    if len(items) < page_size and (skip == 0 or len(items) > 0):
        total = skip + len(items)
    else:
        total = query.count()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
    }
