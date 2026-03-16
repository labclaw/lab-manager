"""Integration tests for RAG SQL execution — requires PostgreSQL.

These tests verify the _execute_sql() function works correctly against a real
PostgreSQL database. They are skipped when running against SQLite (local dev).
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlmodel import Session

_DB_URL = os.environ.get("DATABASE_URL", "sqlite://")
_IS_PG = _DB_URL.startswith("postgresql")

pytestmark = pytest.mark.skipif(not _IS_PG, reason="Requires PostgreSQL")


@pytest.fixture
def pg_session(db_engine):
    """Fresh PG session with test data for RAG execution tests."""
    with Session(db_engine) as session:
        # Insert test data into the vendors table (allowed by RAG)
        session.execute(
            text(
                "INSERT INTO vendors (name, created_by) VALUES "
                "('Test Vendor A', 'test'), ('Test Vendor B', 'test')"
            )
        )
        session.commit()
        yield session
        # Cleanup
        session.execute(text("DELETE FROM vendors WHERE created_by = 'test'"))
        session.commit()


def test_read_only_blocks_insert(pg_session):
    """SET TRANSACTION READ ONLY should prevent INSERT."""
    from lab_manager.services.rag import _execute_sql

    with pytest.raises(Exception, match="read-only"):
        _execute_sql(
            pg_session,
            "INSERT INTO vendors (name) VALUES ('evil')",
        )


def test_read_only_blocks_update(pg_session):
    """SET TRANSACTION READ ONLY should prevent UPDATE."""
    from lab_manager.services.rag import _execute_sql

    with pytest.raises(Exception):
        _execute_sql(
            pg_session,
            "UPDATE vendors SET name = 'evil' WHERE id = 1",
        )


def test_read_only_blocks_delete(pg_session):
    """SET TRANSACTION READ ONLY should prevent DELETE."""
    from lab_manager.services.rag import _execute_sql

    with pytest.raises(Exception):
        _execute_sql(
            pg_session,
            "DELETE FROM vendors WHERE id = 1",
        )


def test_valid_select_returns_results(pg_session):
    """A valid SELECT should return results."""
    from lab_manager.services.rag import _execute_sql

    rows = _execute_sql(pg_session, "SELECT name FROM vendors ORDER BY name")
    assert len(rows) >= 2
    names = [r["name"] for r in rows]
    assert "Test Vendor A" in names
    assert "Test Vendor B" in names


def test_max_result_rows_limit(pg_session):
    """Results should be capped at MAX_RESULT_ROWS (200)."""
    from lab_manager.services.rag import MAX_RESULT_ROWS, _execute_sql

    # generate_series creates many rows without needing to insert
    rows = _execute_sql(
        pg_session,
        f"SELECT generate_series(1, {MAX_RESULT_ROWS + 100}) AS n",
    )
    assert len(rows) <= MAX_RESULT_ROWS


def test_savepoint_rollback_on_error(pg_session):
    """Bad SQL should not poison the session — savepoint rollback works."""
    from lab_manager.services.rag import _execute_sql

    # Execute a query that will fail (bad syntax)
    with pytest.raises(Exception):
        _execute_sql(pg_session, "SELECT * FROM nonexistent_table_xyz")

    # Session should still be usable after rollback
    rows = _execute_sql(pg_session, "SELECT 1 AS val FROM vendors LIMIT 1")
    assert len(rows) == 1
    assert rows[0]["val"] == 1


def test_statement_timeout_enforced(pg_session):
    """Long queries should be killed by statement_timeout."""
    from lab_manager.services.rag import _execute_sql

    # pg_sleep(30) exceeds the 10s timeout
    with pytest.raises(Exception, match="cancel|timeout"):
        _execute_sql(pg_session, "SELECT pg_sleep(30)")
