"""Shared test fixtures."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

# Default to SQLite for local dev; CI sets DATABASE_URL to PostgreSQL.
_DB_URL = os.environ.get("DATABASE_URL", "sqlite://")
_IS_PG = _DB_URL.startswith("postgresql")

if not _IS_PG:
    os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("MEILISEARCH_URL", "http://localhost:7700")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("ADMIN_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password-not-for-production")
os.environ.setdefault("UPLOAD_DIR", "/tmp/lab-manager-test-uploads")

from lab_manager.config import get_settings  # noqa: E402

get_settings.cache_clear()


def _make_engine():
    """Create a test engine: PG if DATABASE_URL points to it, else SQLite."""
    if _IS_PG:
        return create_engine(_DB_URL)
    return create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )


@pytest.fixture
def db_engine():
    """Expose the test engine (needed by PG-only tests)."""
    engine = _make_engine()
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    yield engine
    if _IS_PG:
        SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    with Session(db_engine) as session:
        yield session


@pytest.fixture
def client(db_session):
    # Ensure auth is disabled for standard tests (test_auth.py manages its own).
    os.environ["AUTH_ENABLED"] = "false"
    get_settings.cache_clear()

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
