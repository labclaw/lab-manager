"""Unit tests for RAG SQL validation — _validate_sql() attack patterns.

No database or external services needed. Tests the regex-based SQL validator
that serves as defense-in-depth behind the readonly PostgreSQL user.
"""

import pytest

from lab_manager.services.rag import _validate_sql


# --- Valid queries that SHOULD pass ---


def test_valid_simple_select():
    sql = "SELECT id, name FROM vendors"
    result = _validate_sql(sql)
    assert result.startswith(sql.strip())
    assert "LIMIT" in result


def test_valid_select_with_join():
    sql = "SELECT p.name, v.name FROM products p JOIN vendors v ON p.vendor_id = v.id"
    result = _validate_sql(sql)
    assert result.startswith(sql.strip())


def test_valid_select_with_cte():
    """CTE aliases are checked against table allowlist, so CTE alias must match an allowed table."""
    sql = (
        "WITH orders AS (SELECT * FROM orders WHERE order_date > '2025-01-01') "
        "SELECT * FROM orders"
    )
    result = _validate_sql(sql)
    assert result.startswith(sql)


@pytest.mark.parametrize(
    "table",
    [
        "vendors",
        "products",
        "locations",
        "documents",
        "orders",
        "order_items",
        "inventory",
    ],
)
def test_valid_select_allowed_table(table):
    sql = f"SELECT * FROM {table} LIMIT 10"
    assert _validate_sql(sql) == sql.strip()


def test_valid_aggregate_query():
    sql = "SELECT vendor_id, COUNT(*) FROM products GROUP BY vendor_id"
    result = _validate_sql(sql)
    assert result.startswith(sql.strip())


def test_valid_subquery_in_where():
    sql = (
        "SELECT * FROM products WHERE vendor_id IN "
        "(SELECT id FROM vendors WHERE name ILIKE '%fisher%')"
    )
    result = _validate_sql(sql)
    assert result.startswith(sql.strip())


def test_valid_multiline_select():
    sql = "SELECT *\nFROM vendors\nWHERE id > 1\nLIMIT 10"
    assert _validate_sql(sql) == sql.strip()


def test_valid_trailing_semicolon_stripped():
    result = _validate_sql("SELECT 1 FROM vendors;")
    assert result.startswith("SELECT 1 FROM vendors")


# --- Forbidden keywords that SHOULD be rejected ---


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE vendors",
        "DELETE FROM vendors WHERE id = 1",
        "INSERT INTO vendors (name) VALUES ('evil')",
        "UPDATE vendors SET name = 'evil' WHERE id = 1",
        "ALTER TABLE vendors ADD COLUMN evil TEXT",
        "TRUNCATE vendors",
        "CREATE TABLE evil (id INT)",
        "GRANT ALL ON vendors TO evil",
        "REVOKE SELECT ON vendors FROM labmanager_ro",
    ],
    ids=[
        "drop",
        "delete",
        "insert",
        "update",
        "alter",
        "truncate",
        "create",
        "grant",
        "revoke",
    ],
)
def test_forbidden_keyword_rejected(sql):
    with pytest.raises(ValueError):
        _validate_sql(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT COPY 'vendors' TO '/tmp/out'",
        "SELECT 1; EXEC sp_configure",
        "SELECT 1; EXECUTE 'DROP TABLE vendors'",
    ],
    ids=["copy", "exec", "execute"],
)
def test_forbidden_keyword_in_pattern(sql):
    """Keywords in _FORBIDDEN_PATTERN that are not start-of-query."""
    with pytest.raises(ValueError):
        _validate_sql(sql)


# --- Case insensitive blocking ---


@pytest.mark.parametrize(
    "sql",
    [
        "DRoP TABLE vendors",
        "dElEtE FROM vendors",
    ],
    ids=["drop", "delete"],
)
def test_case_insensitive_forbidden(sql):
    with pytest.raises(ValueError):
        _validate_sql(sql)


# --- Stacked queries ---


def test_stacked_queries_semicolon():
    with pytest.raises(ValueError, match="Stacked"):
        _validate_sql("SELECT 1; DROP TABLE vendors")


# --- Comment injection ---


def test_comment_dash_rejected():
    with pytest.raises(ValueError, match="comment"):
        _validate_sql("SELECT * FROM vendors -- DROP TABLE vendors")


def test_comment_block_rejected():
    with pytest.raises(ValueError, match="comment"):
        _validate_sql("SELECT * FROM vendors /* DROP TABLE vendors */")


# --- Dollar quoting ---


def test_dollar_quoting_rejected():
    """Dollar quoting with semicolon — caught by stacked-query check."""
    with pytest.raises(ValueError, match="Stacked"):
        _validate_sql("SELECT 1; DO $$ BEGIN EXECUTE 'DROP TABLE vendors'; END $$")


# --- Must start with SELECT or WITH ---


def test_must_start_with_select():
    with pytest.raises(ValueError, match="must start with SELECT"):
        _validate_sql("EXPLAIN SELECT * FROM vendors")


def test_must_start_with_select_show():
    with pytest.raises(ValueError, match="must start with SELECT"):
        _validate_sql("SHOW server_version")


# --- Disallowed tables ---


@pytest.mark.parametrize(
    "sql,match_pattern",
    [
        ("SELECT * FROM pg_shadow", "forbidden"),
        ("SELECT * FROM pg_catalog.pg_class", "forbidden"),
        ("SELECT * FROM information_schema.tables", "forbidden"),
        ("SELECT * FROM pg_authid", "forbidden"),
        ("SELECT * FROM pg_roles", "forbidden"),
        ("SELECT * FROM some_unlisted_table", "not allowed"),
    ],
    ids=[
        "pg_shadow",
        "pg_catalog",
        "information_schema",
        "pg_authid",
        "pg_roles",
        "arbitrary_table",
    ],
)
def test_disallowed_table(sql, match_pattern):
    with pytest.raises(ValueError, match=match_pattern):
        _validate_sql(sql)


def test_cte_with_non_allowed_alias_rejected():
    with pytest.raises(ValueError, match="not allowed"):
        _validate_sql("WITH tmp AS (SELECT * FROM vendors) SELECT * FROM tmp")


# --- Unicode bypass attempts ---


def test_unicode_fullwidth_semicolon():
    """Fullwidth semicolon U+FF1B should be normalized to ASCII ; and rejected."""
    with pytest.raises(ValueError):
        _validate_sql("SELECT 1\uff1b DROP TABLE vendors")


def test_unicode_fullwidth_chars():
    """Fullwidth DROP should be normalized and caught."""
    with pytest.raises(ValueError):
        _validate_sql("\uff24\uff32\uff2f\uff30 TABLE vendors")


# --- Dangerous functions ---


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT pg_terminate_backend(1234)",
        "SELECT pg_sleep(10)",
        "SELECT * FROM dblink('host=evil', 'SELECT 1')",
        "SELECT lo_import('/etc/passwd')",
        "SELECT set_config('log_statement', 'all', true)",
        "SELECT current_setting('server_version')",
    ],
    ids=[
        "pg_read_file",
        "pg_terminate_backend",
        "pg_sleep",
        "dblink",
        "lo_import",
        "set_config",
        "current_setting",
    ],
)
def test_forbidden_function(sql):
    with pytest.raises(ValueError, match="forbidden"):
        _validate_sql(sql)


# --- Edge cases ---


def test_empty_input_rejected():
    with pytest.raises(ValueError):
        _validate_sql("")


def test_whitespace_only_rejected():
    with pytest.raises(ValueError):
        _validate_sql("   ")


def test_mixed_case_table_name_passes():
    """Allowed tables should match case-insensitively."""
    sql = "SELECT * FROM VENDORS"
    result = _validate_sql(sql)
    assert result.startswith(sql.strip())


def test_limit_preserved_when_present():
    """Queries with LIMIT should not get a second LIMIT appended."""
    sql = "SELECT * FROM vendors LIMIT 10"
    assert _validate_sql(sql) == sql.strip()


def test_limit_injected_when_missing():
    """Queries without LIMIT get a safety cap appended."""
    sql = "SELECT * FROM vendors"
    result = _validate_sql(sql)
    assert "LIMIT 200" in result


def test_limit_in_subquery_does_not_count():
    """A LIMIT in a subquery should not prevent outer LIMIT injection."""
    sql = "SELECT * FROM vendors WHERE id IN (SELECT vendor_id FROM products LIMIT 10)"
    result = _validate_sql(sql)
    assert result.endswith("LIMIT 200")
