"""BDD test fixtures — runs against real PostgreSQL + Meilisearch via Docker.

Uses a connection-level transaction per test that rolls back after each
scenario, giving full isolation without truncating tables.

When DATABASE_URL is not set (no Docker), falls back to an in-memory SQLite
engine configured with StaticPool + check_same_thread=False so that the
TestClient's anyio thread portal can share the same connection.

SQLite transaction isolation note
----------------------------------
SQLAlchemy's do_begin() is a no-op for pysqlite; transactions start
implicitly on the first DML. This means a plain SAVEPOINT (without an
explicit outer BEGIN) acts as the outermost transaction, and RELEASE
SAVEPOINT immediately commits — there is no outer transaction left to
roll back.

Fix: for SQLite we issue an explicit BEGIN via conn.execute(text("BEGIN"))
before creating the session, then roll back with conn.execute(text("ROLLBACK"))
after each test. For PostgreSQL the standard conn.begin() / trans.rollback()
path is unchanged.
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

# Prefer PostgreSQL (via docker-compose.test.yml); fall back to in-memory SQLite.
_PG_DEFAULT = "postgresql+psycopg://labmanager:testpass@localhost:5432/labmanager_test"
_DB_URL = os.environ.get("DATABASE_URL", _PG_DEFAULT)
_IS_PG = _DB_URL.startswith("postgresql")

# Normalise: when no PG available use a plain in-memory SQLite URL so the app
# config also reads the same value (avoids leftover PG URL from root conftest).
if not _IS_PG:
    _DB_URL = "sqlite://"

os.environ["DATABASE_URL"] = _DB_URL
os.environ.setdefault("MEILISEARCH_URL", "http://localhost:7700")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("ADMIN_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("UPLOAD_DIR", "/tmp/uploads")

from lab_manager.config import get_settings  # noqa: E402

get_settings.cache_clear()


def _make_engine():
    if _IS_PG:
        return create_engine(_DB_URL)
    # StaticPool reuses the same in-memory connection across threads, which is
    # required because Starlette's TestClient runs the ASGI app in a separate
    # anyio thread portal. check_same_thread=False relaxes SQLite's per-thread
    # ownership guard so the shared connection works from multiple threads.
    return create_engine(
        _DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture(scope="session")
def db_engine():
    engine = _make_engine()
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    yield engine
    if _IS_PG:
        SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_connection(db_engine):
    """A connection with an outer transaction that rolls back after the test.

    For PostgreSQL the standard begin/rollback path is used. For SQLite we
    issue an explicit BEGIN SQL statement because SQLAlchemy's do_begin() is a
    no-op for pysqlite — without an explicit BEGIN the first SAVEPOINT becomes
    the outermost transaction and RELEASE SAVEPOINT immediately commits,
    leaving nothing for rollback to undo.
    """
    conn = db_engine.connect()
    if _IS_PG:
        trans = conn.begin()
        yield conn
        if trans.is_active:
            trans.rollback()
    else:
        conn.execute(text("BEGIN"))
        yield conn
        conn.execute(text("ROLLBACK"))
    conn.close()


@pytest.fixture
def db(db_connection):
    """Session bound to the test connection.

    Uses join_transaction_mode='create_savepoint' so that every
    session.commit() inside the app commits only to a SAVEPOINT, not to the
    outer BEGIN. The outer transaction is rolled back by db_connection on
    teardown, giving full per-test isolation.
    """
    session = Session(db_connection, join_transaction_mode="create_savepoint")
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
