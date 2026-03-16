# Agent Handoff: Lab Manager Hardening Sprint

> Generated 2026-03-16. Read this file first before doing any work.

## What is this project?

Lab inventory management system for a 10-person neuroscience lab (MGH Shen Lab). FastAPI + SQLModel + PostgreSQL 17 + Meilisearch. OCR document intake pipeline using 3 VLMs (Claude Opus 4.6, Gemini 3.1 Pro, GPT-5.4) with consensus voting.

**Current state:** All features built (6,057 LOC, 87 tests, CI green), but NOT production-ready due to security and operational gaps.

## What was reviewed?

Three gstack reviews were completed on 2026-03-16:

1. **`/plan-ceo-review`** (HOLD SCOPE) — Full 10-section project health check
2. **`/review`** — Parallel code review (logic + security + performance) → 76 findings
3. **`/plan-eng-review`** (SMALL CHANGE) — Technical design for implementation

## What needs to be done?

10 TODO items in `TODOS.md` (project root). Split into 5 PRs:

```
PR-1  (TODO-2, 4, 6, 7)   ~1.5hr   Small independent fixes
PR-2  (TODO-3a)            ~1hr     RAG validation unit tests
PR-3  (TODO-1, 5)          ~3hr     Auth + health endpoint
PR-4  (TODO-8, 3b)         ~1.5hr   PG in CI + RAG execution tests
PR-5  (TODO-9, 10)         ~3hr     P3 nice-to-haves (optional)
```

**Total: ~10 hours. PRs must be done in order (PR-1 first, PR-5 last).**

---

## PR-1: Small Independent Fixes

### TODO-2: Read-only PostgreSQL user for RAG

**Problem:** `rag.py` executes LLM-generated SQL on the main read-write DB connection. Regex blocklist is bypassable.

**Design decision:** `_execute_sql()` creates its own connection from a readonly engine internally. No route signature changes.

**Files to change:**
- `src/lab_manager/config.py` — add `database_readonly_url: str = ""`
- `src/lab_manager/database.py` — add `get_readonly_engine()` (same pattern as `get_engine()`)
- `src/lab_manager/services/rag.py` — `_execute_sql()` uses `get_readonly_engine()` instead of passed `db` session
- `docker-compose.yml` — add init SQL to create `labmanager_ro` user with SELECT-only grants

**Init SQL for docker-compose:**
```sql
CREATE USER labmanager_ro WITH PASSWORD 'labmanager_ro';
GRANT CONNECT ON DATABASE labmanager TO labmanager_ro;
GRANT USAGE ON SCHEMA public TO labmanager_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO labmanager_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO labmanager_ro;
```

**Fallback:** If `DATABASE_READONLY_URL` not set, fall back to main engine + `SET TRANSACTION READ ONLY`. Log warning.

### TODO-4: PostgreSQL backup script

**Files to create:**
- `scripts/backup_db.sh` — daily `pg_dump` with 7-day rotation

```bash
#!/usr/bin/env bash
BACKUP_DIR="${BACKUP_DIR:-/backups/labmanager}"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
pg_dump "$DATABASE_URL" | gzip > "$BACKUP_DIR/labmanager_${TIMESTAMP}.sql.gz"
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete
```

### TODO-6: CSV formula injection escaping

**File:** `src/lab_manager/api/routes/export.py`

**Change:** In `_csv_response()`, before writing rows, escape cells starting with `=`, `+`, `-`, `@`, or tab by prefixing with `'`.

```python
_DANGEROUS_PREFIXES = ('=', '+', '-', '@', '\t')

def _escape_cell(value):
    if isinstance(value, str) and value and value[0] in _DANGEROUS_PREFIXES:
        return "'" + value
    return value
```

Apply to every cell value before `writer.writerows()`.

### TODO-7: Short-circuit pipeline on empty OCR

**File:** `src/lab_manager/intake/pipeline.py`

**Change:** After OCR (line 76), add:

```python
ocr_text = extract_text_from_image(image_path)
if not ocr_text or not ocr_text.strip():
    doc = Document(
        file_path=str(dest), file_name=image_path.name,
        ocr_text="", status=DocumentStatus.ocr_failed,
    )
    db.add(doc)
    db.commit()
    return doc
```

Note: `DocumentStatus.ocr_failed` may need to be added to the enum if it doesn't exist.

---

## PR-2: RAG Validation Unit Tests

### TODO-3a: Pure unit tests for `_validate_sql()`

**File to create:** `tests/test_rag_validation.py`

**Test cases:**
```
test_valid_select_passes
test_valid_join_passes
test_valid_cte_passes
test_forbidden_drop_rejected
test_forbidden_delete_rejected
test_forbidden_insert_rejected
test_forbidden_alter_rejected
test_forbidden_truncate_rejected
test_stacked_queries_rejected          (semicolon in middle)
test_comment_dash_rejected             (-- comment)
test_comment_block_rejected            (/* */ comment)
test_dollar_quoting_rejected           (DO $$ ... $$)
test_disallowed_table_rejected         (pg_shadow, pg_catalog)
test_allowed_tables_pass               (vendors, products, etc.)
test_case_insensitive_blocking         (DRoP, dElEtE)
test_must_start_with_select_or_with
```

No DB needed. No mocking needed. Just call `_validate_sql()` directly.

---

## PR-3: Authentication + Health Endpoint

### TODO-1: Basic authentication

**Design decision:** Merge auth + audit into ONE middleware to avoid FastAPI middleware ordering bugs.

**Files to change:**
- `src/lab_manager/models/staff.py` — add `password_hash: str | None` field
- `src/lab_manager/config.py` — already has `auth_enabled`, `admin_secret_key`
- `src/lab_manager/api/app.py` — replace `audit_user_middleware` with merged `auth_and_audit_middleware`
- `src/lab_manager/api/deps.py` — keep `verify_api_key()` as fallback for programmatic API access

**New middleware logic:**
```
auth_and_audit_middleware:
  1. Allowlist paths: /api/health, /admin/login, /admin/statics, /docs, /openapi.json
  2. If auth_enabled:
     a. Check session cookie → get staff_id → load Staff
     b. If no session or Staff.is_active=False → 401
     c. Set current_user from Staff.name (for audit)
  3. If not auth_enabled:
     a. Read X-User header (current behavior, for dev)
     b. Set current_user from header
  4. Continue to route
```

**New endpoints:**
- `POST /api/auth/login` — email + password → set session cookie
- `POST /api/auth/logout` — clear session cookie

**CRITICAL: Check `Staff.is_active` on every request, not just login.** This was flagged as a critical gap in the eng review.

### TODO-5: Health endpoint

**File:** `src/lab_manager/api/app.py` — enhance existing `/api/health`

**Design decision:** Check PG + Meilisearch. Gemini = config check only (no API call, saves money).

```python
@app.get("/api/health")
def health():
    checks = {}
    # PG: SELECT 1
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgresql"] = "ok"
    except Exception as e:
        checks["postgresql"] = str(e)
    # Meilisearch: client.health()
    try:
        from lab_manager.services.search import get_search_client
        get_search_client().health()
        checks["meilisearch"] = "ok"
    except Exception as e:
        checks["meilisearch"] = str(e)
    # Gemini: config check only
    checks["gemini"] = "ok" if get_settings().extraction_api_key else "not configured"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "ok" if all_ok else "degraded", "services": checks},
        status_code=200 if all_ok else 503,
    )
```

**Note:** `/api/health` must be in the auth allowlist (no login required).

---

## PR-4: PostgreSQL in CI + RAG Execution Tests

### TODO-8: Use PostgreSQL in CI tests

**File:** `tests/conftest.py`

**Change:** Check `DATABASE_URL` env var. If it points to PostgreSQL (CI), use it. Otherwise fall back to SQLite (local dev).

```python
db_url = os.environ.get("DATABASE_URL", "sqlite://")
if db_url.startswith("postgresql"):
    engine = create_engine(db_url)
else:
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
```

**Important:** CI workflow (`.github/workflows/ci.yml`) already has a PostgreSQL service. Just need to set `DATABASE_URL` env var in the test step.

### TODO-3b: RAG execution integration tests

**File to create:** `tests/test_rag_execution.py`

**Requires PostgreSQL (skip on SQLite):**
```python
@pytest.mark.skipif("sqlite" in os.environ.get("DATABASE_URL", "sqlite"), reason="PG only")
```

**Test cases:**
```
test_read_only_blocks_insert        — verify INSERT fails on readonly connection
test_statement_timeout_enforced     — verify long query is killed
test_savepoint_rollback_on_error    — verify bad SQL doesn't poison session
test_max_result_rows_limit          — verify fetchmany(200) cap
```

---

## PR-5: P3 Nice-to-haves (Optional)

### TODO-9: Structured logging
- Add `structlog` to dependencies
- Generate UUID per request in middleware, attach to all log lines
- Effort: M (~2hr)

### TODO-10: Dashboard query optimization
- Consolidate `dashboard_summary()` from 12+ COUNT queries to 1-2 CTEs
- File: `src/lab_manager/services/analytics.py`
- Effort: M (~1hr)

---

## Key Architecture Diagram

```
                     ┌─────────────────────────────────────┐
                     │           CLIENTS                    │
                     └──────────────┬──────────────────────┘
                                    │
                     ┌──────────────▼──────────────────────┐
                     │  auth_and_audit_middleware (PR-3)    │
                     │  ├── session cookie check            │
                     │  ├── Staff.is_active check           │
                     │  └── set current_user for audit      │
                     └──────────────┬──────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────┐
          │                         │                      │
┌─────────▼──────┐  ┌──────────────▼───────────┐  ┌──────▼──────────┐
│  API Routes    │  │  RAG /api/ask            │  │  SQLAdmin       │
│  (11 routers)  │  │  ├── Gemini NL→SQL       │  │  /admin/        │
│                │  │  ├── readonly engine (PR-1)│  │                │
│                │  │  └── fallback: Meilisearch│  │                │
└────────┬───────┘  └──────────────┬───────────┘  └────────────────┘
         │                         │
         │         ┌───────────────┼───────────────┐
         │         │               │               │
    ┌────▼─────┐ ┌─▼───────┐ ┌───▼────────┐ ┌───▼─────┐
    │PostgreSQL│ │PG Reader │ │Meilisearch │ │Gemini   │
    │(read-    │ │(SELECT   │ │(search)    │ │API      │
    │ write)   │ │ only)    │ │            │ │(NL→SQL) │
    └──────────┘ └──────────┘ └────────────┘ └─────────┘
         ↑ PR-1       ↑ PR-1
```

## Review Findings Summary (for context)

| Category | Critical | Important | Minor | Total |
|----------|----------|-----------|-------|-------|
| Logic    | 6 | 12 | 12 | 30 |
| Security | 6 | 10 | 7  | 23 |
| Performance | 6 | 10 | 7 | 23 |
| **Total** | **18** | **32** | **26** | **76** |

**Top 3 critical (all addressed by these PRs):**
1. RAG SQL injection → PR-1 (read-only DB user)
2. No authentication → PR-3 (session-based auth)
3. Concurrent inventory overdraw → already fixed (recent commit `f51cb79`)

## Files Reference

| File | What it does | Which PR touches it |
|------|-------------|-------------------|
| `TODOS.md` | All 10 TODO items | Reference only |
| `docs/superpowers/plans/2026-03-16-eng-review-todos.md` | Eng review details | Reference only |
| `docs/superpowers/plans/2026-03-16-full-review-fixes.md` | 31 additional issues from prior review | Reference (overlaps with TODOs) |
| `src/lab_manager/config.py` | Settings | PR-1, PR-3 |
| `src/lab_manager/database.py` | Engine/session factory | PR-1 |
| `src/lab_manager/services/rag.py` | NL→SQL RAG service | PR-1 |
| `src/lab_manager/api/app.py` | FastAPI app, middleware, health | PR-3 |
| `src/lab_manager/api/deps.py` | Auth dependencies | PR-3 |
| `src/lab_manager/models/staff.py` | Staff model | PR-3 |
| `src/lab_manager/api/routes/export.py` | CSV export | PR-1 |
| `src/lab_manager/intake/pipeline.py` | Document intake pipeline | PR-1 |
| `docker-compose.yml` | Services config | PR-1 |
| `tests/conftest.py` | Test fixtures | PR-4 |
| `scripts/backup_db.sh` | DB backup script | PR-1 (new) |
| `tests/test_rag_validation.py` | SQL validation tests | PR-2 (new) |
| `tests/test_rag_execution.py` | SQL execution tests | PR-4 (new) |

## Running the project

```bash
docker compose up -d          # PostgreSQL + Meilisearch
uv run alembic upgrade head   # Apply migrations
uv run uvicorn lab_manager.api.app:app --reload  # Dev server on :8000
uv run pytest                 # Tests (87 passing)
```

## Conventions

- **Commits:** Conventional Commits (`feat(scope):`, `fix(scope):`, `test:`, etc.)
- **Linter:** `ruff` (configured in pyproject.toml)
- **Package manager:** `uv`
- **Tests:** `pytest` + `pytest-asyncio`
- **Small commits:** each commit = one logical change
- **Small PRs:** one per PR execution step above
