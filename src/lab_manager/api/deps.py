"""Dependency injection for FastAPI routes."""

from __future__ import annotations

import hmac
from typing import TypeVar

from fastapi import Header, HTTPException
from sqlmodel import Session

from lab_manager.config import get_settings
from lab_manager.database import get_db  # noqa: F401 — re-export for route imports
from lab_manager.exceptions import NotFoundError

T = TypeVar("T")


def get_or_404(db: Session, model: type[T], id: int, label: str | None = None) -> T:
    """Fetch a model instance by primary key, raising NotFoundError if missing."""
    obj = db.get(model, id)
    if not obj:
        raise NotFoundError(label or model.__name__, id)
    return obj


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.auth_enabled:
        return
    if not settings.api_key:
        raise HTTPException(
            status_code=500,
            detail="Server misconfiguration: auth enabled but no API key set",
        )
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
