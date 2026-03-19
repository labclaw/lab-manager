"""Dependency injection for FastAPI routes."""

from __future__ import annotations

from typing import TypeVar

from sqlalchemy.orm import Session

from lab_manager.database import get_db  # noqa: F401 — re-export for route imports
from lab_manager.exceptions import NotFoundError

T = TypeVar("T")


def get_or_404[T](db: Session, model: type[T], id: int, label: str | None = None) -> T:
    """Fetch a model instance by primary key, raising NotFoundError if missing."""
    obj = db.get(model, id)
    if not obj:
        raise NotFoundError(label or model.__name__, id)
    return obj
