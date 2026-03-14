"""Database engine and session management."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from lab_manager.config import get_settings


def get_engine():
    settings = get_settings()
    return create_engine(settings.database_url, echo=False)


def get_session_factory():
    return sessionmaker(bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()
