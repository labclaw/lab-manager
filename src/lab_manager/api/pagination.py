"""Shared pagination helper for list endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.sql import Select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Escape character used in all LIKE patterns.
LIKE_ESCAPE = "\\"


def escape_like(value: str) -> str:
    """Escape special characters for SQL LIKE patterns."""
    return (
        value.replace(LIKE_ESCAPE, LIKE_ESCAPE + LIKE_ESCAPE)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )


def ilike_col(column, value: str):
    """Apply ILIKE with properly escaped pattern and ESCAPE clause."""
    return column.ilike(f"%{escape_like(value)}%", escape=LIKE_ESCAPE)


def apply_sort(stmt: Select, model, sort_by: str, sort_dir: str, allowed: set[str]):
    """Validate sort_by against allowed columns and apply ordering."""
    if sort_by not in allowed:
        sort_by = "id"
    col = getattr(model, sort_by, model.id)
    return stmt.order_by(col.desc() if sort_dir == "desc" else col.asc())


def paginate(stmt: Select, db: Session, page: int = 1, page_size: int = 50) -> dict:
    """Apply pagination to a SQLAlchemy select statement and return metadata.

    Args:
        stmt: A SQLAlchemy Select statement.
        db: SQLAlchemy Session used to execute the query.
        page: Page number (1-based).
        page_size: Items per page.

    Returns:
        dict with keys: items, total, page, page_size, pages
    """
    skip = (page - 1) * page_size
    # Fetch one extra row to detect whether more pages exist without a COUNT.
    items = db.scalars(stmt.offset(skip).limit(page_size + 1)).all()
    has_more = len(items) > page_size
    if has_more:
        items = items[:page_size]

    if not has_more and (skip == 0 or len(items) > 0):
        # We know the exact total without an extra query.
        total = skip + len(items)
    else:
        # Need COUNT on the *original* statement (no offset/limit applied yet).
        # Build a count subquery from the original stmt's where clause.
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = db.execute(count_stmt).scalar() or 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
    }
