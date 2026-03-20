"""Database engine and session management."""

from __future__ import annotations

import threading
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from lab_manager.config import get_settings

_engine = None
_readonly_engine = None
_session_factory = None
_lock = threading.RLock()


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
                # On managed PG (e.g. DO App Platform) the app user may lack
                # CREATE on the 'public' schema. Use a custom schema to avoid
                # this PG 15+ restriction. Set search_path via connect_args.
                if not settings.database_url.startswith("sqlite"):
                    kwargs.setdefault("connect_args", {})
                    kwargs["connect_args"]["options"] = (
                        "-c search_path=labmanager,public"
                    )
                _engine = create_engine(settings.database_url, **kwargs)

    return _engine


def get_readonly_engine():
    """Return a read-only engine for RAG queries.

    Falls back to the main engine if DATABASE_READONLY_URL is not configured.
    """
    global _readonly_engine
    if _readonly_engine is None:
        with _lock:
            if _readonly_engine is None:
                settings = get_settings()
                if settings.database_readonly_url:
                    try:
                        _readonly_engine = create_engine(
                            settings.database_readonly_url,
                            echo=False,
                            pool_size=5,
                            max_overflow=5,
                            pool_pre_ping=True,
                            connect_args={"options": "-c statement_timeout=10000"},
                        )
                    except Exception:
                        import logging

                        logging.getLogger(__name__).warning(
                            "Failed to create readonly engine, falling back to main engine"
                        )
                        _readonly_engine = get_engine()
                else:
                    import logging

                    logging.getLogger(__name__).warning(
                        "DATABASE_READONLY_URL not set, RAG queries use main engine + SET TRANSACTION READ ONLY"
                    )
                    _readonly_engine = get_engine()
    return _readonly_engine


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


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for DB sessions outside of FastAPI dependency injection."""
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
