"""BDD test fixtures — runs against real PostgreSQL + Meilisearch via Docker.

Uses a connection-level transaction per test that rolls back after each
scenario, giving full isolation without truncating tables.
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlmodel import SQLModel, create_engine

# BDD tests always run against PostgreSQL (via docker-compose.test.yml).
_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://labmanager:testpass@localhost:5432/labmanager_test",
)
os.environ["DATABASE_URL"] = _DB_URL
os.environ.setdefault("MEILISEARCH_URL", "http://localhost:7700")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("ADMIN_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("UPLOAD_DIR", "/tmp/uploads")

from lab_manager.config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(_DB_URL)
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_connection(db_engine):
    """A connection with an outer transaction that rolls back after the test."""
    conn = db_engine.connect()
    trans = conn.begin()
    yield conn
    if trans.is_active:
        trans.rollback()
    conn.close()


@pytest.fixture
def db(db_connection):
    """Session bound to the test connection.

    Uses savepoints so that session.commit() inside the app doesn't escape the
    outer transaction — each commit becomes a SAVEPOINT that we can roll back.
    """
    session = Session(bind=db_connection)

    # Every time the session would commit, start a nested savepoint instead
    # so the outer transaction stays open.
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        if transaction.nested and not transaction._parent.nested:
            sess.begin_nested()

    yield session
    session.close()


@pytest.fixture
def api(db, db_connection):
    """TestClient hitting the real app with test DB session (rolled back per test)."""
    get_settings.cache_clear()

    from lab_manager.api.app import create_app
    from lab_manager.database import get_db

    app = create_app()

    def override():
        yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c


@pytest.fixture
def app_url():
    """Base URL for the running app-test container (E2E tests)."""
    return os.environ.get("APP_BASE_URL", "http://localhost:8000")
