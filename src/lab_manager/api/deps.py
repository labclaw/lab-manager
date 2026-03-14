"""Dependency injection for FastAPI routes."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from lab_manager.database import get_session_factory


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()
