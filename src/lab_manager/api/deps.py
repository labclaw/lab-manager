"""Dependency injection for FastAPI routes."""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException

from lab_manager.config import get_settings
from lab_manager.database import get_db  # noqa: F401 — re-export for route imports


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.auth_enabled:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
