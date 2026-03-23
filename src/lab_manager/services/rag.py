"""RAG service: natural language Q&A over lab inventory via LiteLLM + SQL."""

from __future__ import annotations

import logging
import re

from sqlalchemy import text
from sqlmodel import Session

from lab_manager.config import get_settings
from lab_manager.services.litellm_client import create_completion, response_text
from lab_manager.services.serialization import serialize_value as _serialize_value

logger = logging.getLogger(__name__)


def _get_model() -> str:
    """Return the RAG model name from settings (configurable via RAG_MODEL env var)."""
    return get_settings().rag_model


# Max question length to prevent cost amplification
MAX_QUESTION_LENGTH = 2000

# SQL execution timeout (seconds)
SQL_TIMEOUT_S = 10

DB_SCHEMA = """\
-- PostgreSQL schema for a lab inventory management system

CREATE TABLE vendors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    aliases JSON,
    website VARCHAR(500),
    phone VARCHAR(50),
    email VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    created_by VARCHAR(100)
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    catalog_number VARCHAR(100) NOT NULL,
    name VARCHAR(500) NOT NULL,
    vendor_id INTEGER REFERENCES vendors(id),
    category VARCHAR(100),
    cas_number VARCHAR(30),
    storage_temp VARCHAR(50),
    unit VARCHAR(50),
    hazard_info VARCHAR(255),
    extra JSON,
    min_stock_level NUMERIC(12, 4),
    max_stock_level NUMERIC(12, 4),
    reorder_quantity NUMERIC(12, 4),
    shelf_life_days INTEGER,
    storage_requirements VARCHAR(500),
    is_hazardous BOOLEAN DEFAULT FALSE,
    is_controlled BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    created_by VARCHAR(100)
);

CREATE TABLE staff (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(255) UNIQUE,
    role VARCHAR(50) DEFAULT 'member',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    created_by VARCHAR(100)
);

CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    room VARCHAR(100),
    building VARCHAR(100),
    temperature INTEGER,
    description TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    created_by VARCHAR(100)
);

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    file_path VARCHAR(1000) NOT NULL,
    file_name VARCHAR(255) UNIQUE NOT NULL,
    document_type VARCHAR(50),
    vendor_name VARCHAR(255),
    ocr_text TEXT,
    extracted_data JSON,
    extraction_model VARCHAR(100),
    extraction_confidence FLOAT,
    status VARCHAR(30) DEFAULT 'pending',
    review_notes TEXT,
    reviewed_by VARCHAR(200),
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    created_by VARCHAR(100)
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    po_number VARCHAR(100),
    vendor_id INTEGER REFERENCES vendors(id),
    order_date DATE,
    ship_date DATE,
    received_date DATE,
    received_by VARCHAR(200),
    status VARCHAR(30) DEFAULT 'pending',
    delivery_number VARCHAR(100),
    invoice_number VARCHAR(100),
    document_id INTEGER REFERENCES documents(id),
    extra JSON,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    created_by VARCHAR(100)
);

CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    catalog_number VARCHAR(100),
    description VARCHAR(1000),
    quantity NUMERIC(12, 4) DEFAULT 1,
    unit VARCHAR(50),
    lot_number VARCHAR(100),
    batch_number VARCHAR(100),
    unit_price NUMERIC(12, 4),
    product_id INTEGER REFERENCES products(id),
    extra JSON,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    created_by VARCHAR(100)
);

CREATE TABLE inventory (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    location_id INTEGER REFERENCES locations(id),
    lot_number VARCHAR(100),
    quantity_on_hand NUMERIC(12, 4) DEFAULT 0,
    unit VARCHAR(50),
    expiry_date DATE,
    opened_date DATE,
    status VARCHAR(30) DEFAULT 'available',
    notes TEXT,
    received_by VARCHAR(200),
    order_item_id INTEGER REFERENCES order_items(id),
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    created_by VARCHAR(100)
);

CREATE TABLE consumption_log (
    id SERIAL PRIMARY KEY,
    inventory_id INTEGER NOT NULL REFERENCES inventory(id),
    product_id INTEGER REFERENCES products(id),
    quantity_used NUMERIC(12, 4) NOT NULL,
    quantity_remaining NUMERIC(12, 4) NOT NULL,
    consumed_by VARCHAR(200) NOT NULL,
    purpose VARCHAR(500),
    action VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    created_by VARCHAR(100)
);

CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message VARCHAR(1000) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INTEGER NOT NULL,
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(200),
    acknowledged_at TIMESTAMPTZ,
    is_resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    created_by VARCHAR(100)
);

CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    record_id INTEGER NOT NULL,
    action VARCHAR(20) NOT NULL,
    changed_by VARCHAR(100),
    changes JSON,
    timestamp TIMESTAMPTZ NOT NULL
);
"""

NL_TO_SQL_PROMPT = """\
You are a SQL expert for a lab inventory management system. Given a natural language \
question, generate a single PostgreSQL SELECT query to answer it.

DATABASE SCHEMA:
{schema}

RULES:
- Output ONLY the SQL query, nothing else. No markdown, no explanation.
- Only SELECT queries. Never use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, or REVOKE.
- Only query these tables: vendors, products, staff, locations, documents, orders, order_items, inventory, consumption_log, alerts, audit_log.
- Do NOT access system catalogs (pg_shadow, pg_authid, information_schema, pg_catalog).
- Do NOT call functions with side effects (pg_terminate_backend, set_config, dblink, lo_import, etc.).
- Use JOINs when the question involves related tables (e.g., vendor name for a product).
- Use ILIKE for case-insensitive text matching.
- For date-relative queries, use CURRENT_DATE (e.g., "this month" = date_trunc('month', CURRENT_DATE)).
- LIMIT results to 50 rows maximum unless the user explicitly asks for more.
- For counts or aggregates, no LIMIT is needed.
- If the question is ambiguous, make a reasonable assumption and query broadly.

QUESTION: {question}
"""

FORMAT_ANSWER_PROMPT = """\
You are a helpful lab assistant. A scientist asked a question about lab inventory, and \
a database query was executed to get the answer.

QUESTION: {question}

SQL QUERY EXECUTED:
{sql}

QUERY RESULTS (as list of row dicts):
{results}

Provide a clear, helpful answer to the scientist's question based on the results. \
If the results are empty, say so clearly. Use the same language as the question \
(if the question is in Chinese, answer in Chinese; if English, answer in English). \
Be concise but complete. Format numbers and dates nicely. \
If there are many rows, summarize the key findings.
"""

# Dangerous SQL keywords/functions that must never appear in generated queries
_FORBIDDEN_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|EXEC|EXECUTE"
    r"|UNION|INTO\s+OUTFILE|COPY|DO\s*\$"
    r"|EXPLAIN|CALL|PREPARE|LISTEN|NOTIFY"
    r"|SET\s+ROLE|SET\s+SESSION\s+AUTHORIZATION"
    r"|pg_read_file|pg_write_file|pg_ls_dir|pg_stat_file"
    r"|pg_terminate_backend|pg_cancel_backend|pg_sleep"
    r"|lo_import|lo_export|dblink|set_config"
    r"|pg_shadow|pg_authid|pg_roles"
    r"|pg_catalog|information_schema|pg_stat_activity|current_setting)\b",
    re.IGNORECASE,
)

# Columns that must never appear in RAG queries (PII, credentials)
_FORBIDDEN_COLUMNS = re.compile(r"\bpassword_hash\b", re.IGNORECASE)

# Defense-in-depth: block data-modifying keywords anywhere in SQL (catches CTE bypasses)
_DANGEROUS_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|EXECUTE)\b",
    re.IGNORECASE,
)

# Allowed table names for FROM/JOIN clauses
_ALLOWED_TABLES = {
    "vendors",
    "products",
    "staff",
    "locations",
    "documents",
    "orders",
    "order_items",
    "inventory",
    "consumption_log",
    "alerts",
    "audit_log",
}

# Allow only SELECT (including WITH/CTE)
_ALLOWED_START = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)

# Extract table names from FROM/JOIN clauses
_TABLE_REF_PATTERN = re.compile(
    r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_.]*)", re.IGNORECASE
)


def _generate_completion(prompt: str) -> str:
    """Generate text with LiteLLM using the centralized client."""
    model = _get_model()
    resp = create_completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return response_text(resp)


def _validate_sql(sql: str) -> str:
    """Validate that the SQL is a read-only SELECT. Raises ValueError if not."""
    import unicodedata

    # Normalize Unicode to ASCII-safe form — blocks fullwidth chars, homoglyphs
    sql = unicodedata.normalize("NFKC", sql)
    sql = sql.strip().rstrip(";").strip()

    if ";" in sql:
        raise ValueError("Stacked queries not allowed")

    # Block SQL comments that could hide forbidden tokens.
    if "--" in sql or "/*" in sql:
        raise ValueError("SQL comments are not allowed")

    if not _ALLOWED_START.match(sql):
        raise ValueError(f"Query must start with SELECT or WITH, got: {sql[:60]}...")

    if _FORBIDDEN_PATTERN.search(sql):
        raise ValueError(f"Query contains forbidden keywords: {sql[:120]}...")

    # Defense-in-depth: block dangerous keywords anywhere (catches CTE bypasses)
    if _DANGEROUS_KEYWORDS.search(sql):
        raise ValueError("Query contains forbidden keyword")

    if _FORBIDDEN_COLUMNS.search(sql):
        raise ValueError("Query references forbidden columns")

    # Enforce table allowlist: every FROM/JOIN target must be in _ALLOWED_TABLES.
    table_refs = _TABLE_REF_PATTERN.findall(sql)
    for ref in table_refs:
        table_name = ref.split(".")[-1].lower()
        if table_name not in _ALLOWED_TABLES:
            raise ValueError(f"Table '{ref}' is not allowed")

    return sql


def _serialize_rows(rows: list[dict]) -> list[dict]:
    """Ensure all values in result rows are JSON-serializable."""
    return [{k: _serialize_value(v) for k, v in row.items()} for row in rows]


def _generate_sql(question: str) -> str:
    """Ask the configured RAG model to translate a natural language question to SQL."""
    prompt = NL_TO_SQL_PROMPT.format(schema=DB_SCHEMA, question=question)
    raw = _generate_completion(prompt)

    # Some models wrap SQL in fenced markdown
    if raw.startswith("```"):
        lines = raw.split("\n")
        # Remove first and last fence lines
        lines = [line for line in lines if not line.strip().startswith("```")]
        raw = "\n".join(lines).strip()

    return _validate_sql(raw)


MAX_RESULT_ROWS = 200


def _execute_sql(db: Session, sql: str) -> list[dict]:
    """Execute a read-only SQL query and return results.

    Uses the readonly engine when available (DATABASE_READONLY_URL).
    Falls back to the main engine with SET TRANSACTION READ ONLY.
    Enforces a row limit to prevent memory exhaustion.
    """
    from lab_manager.database import get_readonly_engine, get_engine

    readonly_engine = get_readonly_engine()
    use_dedicated_readonly = readonly_engine is not get_engine()

    if use_dedicated_readonly:
        # Dedicated readonly PG user — DB enforces SELECT-only
        # Defense-in-depth: also set READ ONLY at transaction level
        with readonly_engine.connect() as conn, conn.begin():
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(text(f"SET LOCAL statement_timeout = '{int(SQL_TIMEOUT_S)}s'"))
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = [
                dict(zip(columns, row)) for row in result.fetchmany(MAX_RESULT_ROWS)
            ]
            return _serialize_rows(rows)
    else:
        # Fallback: main engine with application-level READ ONLY
        db.execute(text("SET TRANSACTION READ ONLY"))
        db.execute(text(f"SET LOCAL statement_timeout = '{int(SQL_TIMEOUT_S)}s'"))
        nested = db.begin_nested()
        try:
            result = db.execute(text(sql))
            columns = list(result.keys())
            rows = [
                dict(zip(columns, row)) for row in result.fetchmany(MAX_RESULT_ROWS)
            ]
            nested.commit()
            return _serialize_rows(rows)
        except Exception:
            nested.rollback()
            raise


def _format_answer(question: str, sql: str, results: list[dict]) -> str:
    """Ask the configured RAG model to format query results into a human-readable answer."""
    # Truncate results for the prompt if too many rows
    display_results = results[:50]
    prompt = FORMAT_ANSWER_PROMPT.format(
        question=question,
        sql=sql,
        results=display_results,
    )
    return _generate_completion(prompt)


def _fallback_search(question: str) -> dict:
    """Fall back to Meilisearch full-text search when SQL generation fails."""
    try:
        from lab_manager.services.search import search

        hits = []
        for index_name in ("documents", "vendors", "orders", "products", "order_items"):
            hits = search(question, index=index_name, limit=20)
            if hits:
                break

        answer = (
            f"Found {len(hits)} results via text search."
            if hits
            else "No results found via text search either."
        )
        return {
            "question": question,
            "answer": answer,
            "raw_results": hits,
            "source": "search",
        }
    except Exception as e:
        logger.warning("Meilisearch fallback also failed: %s", e)
        return {
            "question": question,
            "answer": "Search is currently unavailable.",
            "raw_results": [],
            "source": "search",
        }


def ask(question: str, db: Session) -> dict:
    """Main RAG entry point: natural language question -> answer dict.

    Returns:
        {
            "question": str,
            "answer": str,
            "raw_results": list[dict],
            "source": "sql" | "search"
        }
    """
    if not question or not question.strip():
        return {
            "question": question,
            "answer": "Please provide a question.",
            "raw_results": [],
            "source": "sql",
        }

    question = question.strip()

    if len(question) > MAX_QUESTION_LENGTH:
        question = question[:MAX_QUESTION_LENGTH]

    # Step 1: NL -> SQL
    try:
        sql = _generate_sql(question)
        logger.info("Generated SQL for question '%s': %s", question[:80], sql)
    except Exception as e:
        logger.warning("SQL generation failed: %s — falling back to search", e)
        return _fallback_search(question)

    # Step 2: Execute SQL
    try:
        results = _execute_sql(db, sql)
        logger.info("Query returned %d rows", len(results))
    except Exception as e:
        logger.warning("SQL execution failed: %s — falling back to search", e)
        return _fallback_search(question)

    # Step 3: Format answer
    try:
        answer = _format_answer(question, sql, results)
    except Exception as e:
        logger.warning("Answer formatting failed: %s", e)
        answer = f"Query returned {len(results)} results but answer formatting failed."

    return {
        "question": question,
        "answer": answer,
        "sql": sql,
        "raw_results": results[:50],
        "row_count": len(results),
        "source": "sql",
    }
