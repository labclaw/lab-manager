"""Database engine and session management."""

from __future__ import annotations

import threading
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from lab_manager.config import get_settings

_engine = None
_session_factory = None
_lock = threading.Lock()


def get_engine():
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:  # double-check
                settings = get_settings()
                kwargs = {"echo": False}
                if settings.database_url.startswith("sqlite"):
                    pass
                else:
                    kwargs.update(pool_size=10, max_overflow=20, pool_pre_ping=True)
                _engine = create_engine(settings.database_url, **kwargs)
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        with _lock:
            if _session_factory is None:  # double-check
                _session_factory = sessionmaker(bind=get_engine())
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """Yield a DB session that auto-commits on success, rolls back on error."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
