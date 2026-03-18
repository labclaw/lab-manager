"""RAG service: natural language Q&A over lab inventory via Gemini + SQL."""

from __future__ import annotations

import functools
import logging
import re

from google import genai
from sqlalchemy import text
from sqlalchemy.orm import Session

from lab_manager.config import get_settings
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
    aliases JSON,           -- list of alternate names
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
    updated_at TIMESTAMPTZ
);

CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    room VARCHAR(100),
    building VARCHAR(100),
    temperature INTEGER,      -- storage temp in Celsius
    description TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    created_by VARCHAR(100)
);

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    file_path VARCHAR(1000) NOT NULL,
    file_name VARCHAR(255) UNIQUE NOT NULL,
    document_type VARCHAR(50),   -- 'packing_list', 'invoice', 'coa', 'shipping_label'
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
    status VARCHAR(30) DEFAULT 'pending',  -- 'pending', 'shipped', 'received', 'cancelled'
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
    quantity FLOAT DEFAULT 1,
    unit VARCHAR(50),
    lot_number VARCHAR(100),
    batch_number VARCHAR(100),
    unit_price FLOAT,
    product_id INTEGER REFERENCES products(id),
    extra JSON,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    created_by VARCHAR(100)
);

CREATE TABLE inventory (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    location_id INTEGER REFERENCES locations(id),
    lot_number VARCHAR(100),
    quantity_on_hand FLOAT DEFAULT 0,
    unit VARCHAR(50),
    expiry_date DATE,
    opened_date DATE,
    status VARCHAR(30) DEFAULT 'available',  -- 'available', 'low', 'expired', 'depleted'
    notes TEXT,
    received_by VARCHAR(200),
    order_item_id INTEGER REFERENCES order_items(id),
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    created_by VARCHAR(100)
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
- Only query these tables: vendors, products, staff, locations, documents, orders, order_items, inventory.
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

# Allowed table names for FROM/JOIN clauses
_ALLOWED_TABLES = {
    "vendors",
    "products",
    "locations",
    "documents",
    "orders",
    "order_items",
    "inventory",
    "staff",
}

# Allow only SELECT (including WITH/CTE)
_ALLOWED_START = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)

# Extract table names from FROM/JOIN clauses
_TABLE_REF_PATTERN = re.compile(
    r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_.]*)", re.IGNORECASE
)


@functools.lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    """Create (and cache) a Gemini API client."""
    settings = get_settings()
    api_key = settings.extraction_api_key
    if not api_key:
        import os

        api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "No Gemini API key found. Set GEMINI_API_KEY or EXTRACTION_API_KEY."
        )
    return genai.Client(api_key=api_key)


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


def _generate_sql(client: genai.Client, question: str) -> str:
    """Ask Gemini to translate a natural language question to SQL."""
    prompt = NL_TO_SQL_PROMPT.format(schema=DB_SCHEMA, question=question)
    response = client.models.generate_content(
        model=_get_model(),
        contents=prompt,
    )
    raw = response.text.strip()

    # Gemini sometimes wraps in ```sql ... ```
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
        with readonly_engine.connect() as conn, conn.begin():
            conn.execute(text(f"SET LOCAL statement_timeout = '{SQL_TIMEOUT_S}s'"))
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = [
                dict(zip(columns, row)) for row in result.fetchmany(MAX_RESULT_ROWS)
            ]
            return _serialize_rows(rows)
    else:
        # Fallback: main engine with application-level READ ONLY
        db.execute(text("SET TRANSACTION READ ONLY"))
        db.execute(text(f"SET LOCAL statement_timeout = '{SQL_TIMEOUT_S}s'"))
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


def _format_answer(
    client: genai.Client, question: str, sql: str, results: list[dict]
) -> str:
    """Ask Gemini to format query results into a human-readable answer."""
    # Truncate results for the prompt if too many rows
    display_results = results[:50]
    prompt = FORMAT_ANSWER_PROMPT.format(
        question=question,
        sql=sql,
        results=display_results,
    )
    response = client.models.generate_content(
        model=_get_model(),
        contents=prompt,
    )
    return response.text.strip()


def _fallback_search(question: str) -> dict:
    """Fall back to Meilisearch full-text search when SQL generation fails."""
    try:
        from lab_manager.services.search import search

        hits = search(question, index="products", limit=20)
        if not hits:
            hits = search(question, index="order_items", limit=20)

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

    try:
        client = _get_client()
    except RuntimeError as e:
        logger.error("Gemini client init failed: %s", e)
        return _fallback_search(question)

    # Step 1: NL -> SQL
    try:
        sql = _generate_sql(client, question)
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
        answer = _format_answer(client, question, sql, results)
    except Exception as e:
        logger.warning("Answer formatting failed: %s", e)
        answer = f"Query returned {len(results)} results but answer formatting failed."

    return {
        "question": question,
        "answer": answer,
        "raw_results": [],
        "row_count": len(results),
        "source": "sql",
    }
