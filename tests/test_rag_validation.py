"""Unit tests for RAG SQL validation — _validate_sql() attack patterns.

No database or external services needed. Tests the regex-based SQL validator
that serves as defense-in-depth behind the readonly PostgreSQL user.
"""

import pytest

from lab_manager.services.rag import _validate_sql


# --- Valid queries that SHOULD pass ---


def test_valid_simple_select():
    sql = "SELECT id, name FROM vendors"
    assert _validate_sql(sql) == sql.strip()


def test_valid_select_with_join():
    sql = "SELECT p.name, v.name FROM products p JOIN vendors v ON p.vendor_id = v.id"
    assert _validate_sql(sql) == sql.strip()


def test_valid_select_with_cte():
    """CTE aliases are checked against table allowlist, so CTE alias must match an allowed table."""
    sql = (
        "WITH orders AS (SELECT * FROM orders WHERE order_date > '2025-01-01') "
        "SELECT * FROM orders"
    )
    result = _validate_sql(sql)
    assert result.startswith("WITH")


def test_valid_select_all_allowed_tables():
    for table in [
        "vendors",
        "products",
        "staff",
        "locations",
        "documents",
        "orders",
        "order_items",
        "inventory",
    ]:
        sql = f"SELECT * FROM {table} LIMIT 10"
        assert _validate_sql(sql) == sql.strip()


def test_valid_aggregate_query():
    sql = "SELECT vendor_id, COUNT(*) FROM products GROUP BY vendor_id"
    assert _validate_sql(sql) == sql.strip()


def test_valid_subquery_in_where():
    sql = (
        "SELECT * FROM products WHERE vendor_id IN "
        "(SELECT id FROM vendors WHERE name ILIKE '%fisher%')"
    )
    assert _validate_sql(sql) == sql.strip()


# --- Forbidden keywords that SHOULD be rejected ---


def test_forbidden_drop():
    with pytest.raises(ValueError):
        _validate_sql("DROP TABLE vendors")


def test_forbidden_delete():
    with pytest.raises(ValueError):
        _validate_sql("DELETE FROM vendors WHERE id = 1")


def test_forbidden_insert():
    with pytest.raises(ValueError):
        _validate_sql("INSERT INTO vendors (name) VALUES ('evil')")


def test_forbidden_update():
    with pytest.raises(ValueError):
        _validate_sql("UPDATE vendors SET name = 'evil' WHERE id = 1")


def test_forbidden_alter():
    with pytest.raises(ValueError):
        _validate_sql("ALTER TABLE vendors ADD COLUMN evil TEXT")


def test_forbidden_truncate():
    with pytest.raises(ValueError):
        _validate_sql("TRUNCATE vendors")


def test_forbidden_create():
    with pytest.raises(ValueError):
        _validate_sql("CREATE TABLE evil (id INT)")


def test_forbidden_grant():
    with pytest.raises(ValueError):
        _validate_sql("GRANT ALL ON vendors TO evil")


def test_forbidden_revoke():
    with pytest.raises(ValueError):
        _validate_sql("REVOKE SELECT ON vendors FROM labmanager_ro")


# --- Case insensitive blocking ---


def test_case_insensitive_drop():
    with pytest.raises(ValueError):
        _validate_sql("DRoP TABLE vendors")


def test_case_insensitive_delete():
    with pytest.raises(ValueError):
        _validate_sql("dElEtE FROM vendors")


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
    with pytest.raises(ValueError):
        _validate_sql("SELECT 1; DO $$ BEGIN EXECUTE 'DROP TABLE vendors'; END $$")


# --- Must start with SELECT or WITH ---


def test_must_start_with_select():
    with pytest.raises(ValueError, match="must start with SELECT"):
        _validate_sql("EXPLAIN SELECT * FROM vendors")


def test_must_start_with_select_show():
    with pytest.raises(ValueError, match="must start with SELECT"):
        _validate_sql("SHOW server_version")


# --- Disallowed tables ---


def test_disallowed_table_pg_shadow():
    with pytest.raises(ValueError, match="forbidden"):
        _validate_sql("SELECT * FROM pg_shadow")


def test_disallowed_table_pg_catalog():
    with pytest.raises(ValueError, match="forbidden"):
        _validate_sql("SELECT * FROM pg_catalog.pg_class")


def test_disallowed_table_information_schema():
    with pytest.raises(ValueError, match="forbidden"):
        _validate_sql("SELECT * FROM information_schema.tables")


def test_disallowed_table_pg_authid():
    with pytest.raises(ValueError, match="forbidden"):
        _validate_sql("SELECT * FROM pg_authid")


def test_disallowed_table_pg_roles():
    with pytest.raises(ValueError, match="forbidden"):
        _validate_sql("SELECT * FROM pg_roles")


def test_disallowed_table_random_table():
    with pytest.raises(ValueError, match="not allowed"):
        _validate_sql("SELECT * FROM audit_log")


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


def test_forbidden_pg_read_file():
    with pytest.raises(ValueError, match="forbidden"):
        _validate_sql("SELECT pg_read_file('/etc/passwd')")


def test_forbidden_pg_terminate_backend():
    with pytest.raises(ValueError, match="forbidden"):
        _validate_sql("SELECT pg_terminate_backend(1234)")


def test_forbidden_pg_sleep():
    with pytest.raises(ValueError, match="forbidden"):
        _validate_sql("SELECT pg_sleep(10)")


def test_forbidden_dblink():
    with pytest.raises(ValueError, match="forbidden"):
        _validate_sql("SELECT * FROM dblink('host=evil', 'SELECT 1')")


def test_forbidden_lo_import():
    with pytest.raises(ValueError, match="forbidden"):
        _validate_sql("SELECT lo_import('/etc/passwd')")


def test_forbidden_set_config():
    with pytest.raises(ValueError, match="forbidden"):
        _validate_sql("SELECT set_config('log_statement', 'all', true)")


def test_forbidden_current_setting():
    with pytest.raises(ValueError, match="forbidden"):
        _validate_sql("SELECT current_setting('server_version')")
