"""Shared pagination helper for list endpoints."""

from __future__ import annotations

from sqlalchemy import Select, func, select

LIKE_ESCAPE = "\\"


def escape_like(value: str) -> str:
    return (
        value.replace(LIKE_ESCAPE, LIKE_ESCAPE + LIKE_ESCAPE)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )


def ilike_col(column, value: str):
    return column.ilike(f"%{escape_like(value)}%", escape=LIKE_ESCAPE)


def apply_sort(stmt, model, sort_by: str, sort_dir: str, allowed: set[str]):
    if sort_by not in allowed:
        sort_by = "id"
    col = getattr(model, sort_by, model.id)
    return stmt.order_by(col.desc() if sort_dir == "desc" else col.asc())


def paginate(db, stmt, page: int = 1, page_size: int = 50) -> dict:
    skip = (page - 1) * page_size
    items = db.execute(stmt.offset(skip).limit(page_size + 1)).scalars().all()
    has_more = len(items) > page_size
    if has_more:
        items = items[:page_size]

    if not has_more and (skip == 0 or len(items) > 0):
        total = skip + len(items)
    else:
        if isinstance(stmt, Select):
            count_stmt = select(func.count()).select_from(
                stmt.order_by(None).subquery()
            )
            total = db.execute(count_stmt).scalar() or 0
        else:
            total = stmt.order_by(None).count()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
    }
