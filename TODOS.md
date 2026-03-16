# TODOS — Lab Manager

> CEO-mode review (2026-03-16). **Agent handoff doc:** `docs/superpowers/plans/2026-03-16-agent-handoff.md` (start here).
> Eng review: `docs/superpowers/plans/2026-03-16-eng-review-todos.md`. Prior code review: `docs/superpowers/plans/2026-03-16-full-review-fixes.md`.

## P1 — Must fix before production deploy

### TODO-1: Basic authentication layer
- **What:** Add username/password login with session cookies, using existing Staff table.
- **Why:** X-User header is honor-system — anyone on the lab network can spoof any user in audit logs. Audit trail integrity is zero without auth.
- **Effort:** M (~2hr)
- **Depends on:** Staff model already has `name`, `email`, `role`, `is_active` fields.
- **How to apply:** Add login/logout endpoints, session middleware, protect all routes. Remove X-User header trust.

### TODO-2: Read-only PostgreSQL user for RAG queries
- **What:** Create a PostgreSQL user with SELECT-only grants. RAG `_execute_sql()` uses this connection instead of the main read-write connection.
- **Why:** Regex-based SQL blocklist is fundamentally bypassable (unicode normalization, comment injection, dollar-quoting). A DB-level read-only user is the only defense that can't be bypassed.
- **Effort:** S (~30min)
- **Depends on:** Database setup / Docker Compose changes.
- **How to apply:** Add `DATABASE_READONLY_URL` to config, create `labmanager_ro` user in init SQL, use separate engine in `rag.py`.

### TODO-3: RAG SQL validation unit tests
- **What:** Test `_validate_sql()` with known attack patterns: unicode bypass, comment injection (`/* */`, `--`), dollar-quoting, case tricks, `UNION` injection.
- **Why:** The highest-risk codepath in the system has zero tests. Even with read-only user (TODO-2), tests document known attack vectors.
- **Effort:** S (~1hr)
- **Depends on:** None (pure unit tests, mock Gemini).

### TODO-4: PostgreSQL backup script
- **What:** Daily `pg_dump` to local backup directory with 7-day rotation. Add `scripts/backup_db.sh` and document cron setup.
- **Why:** Database contains 279 processed documents extracted via expensive VLM processing. Losing this data means re-running the entire intake pipeline ($$$).
- **Effort:** S (~15min)
- **Depends on:** None.

## P2 — Should fix before production deploy

### TODO-5: Health endpoint with explicit service errors
- **What:** Add `GET /api/health` checking PostgreSQL + Meilisearch + Gemini API availability. Return 503 with service name when downstream is down. Search/RAG endpoints return explicit errors instead of empty results.
- **Why:** Silent failures violate zero-silent-failures principle. Users can't distinguish "no results" from "search is broken."
- **Effort:** S (~1hr)
- **Depends on:** None.

### TODO-6: CSV formula injection escaping
- **What:** Prefix CSV cells starting with `=`, `+`, `-`, `@`, or tab with a single quote (`'`). Standard defense against Excel formula injection.
- **Why:** OCR could extract formula-like text from scanned documents. Low risk but trivial fix.
- **Effort:** S (~15min)
- **Depends on:** None.
- **File:** `src/lab_manager/api/routes/export.py`

### TODO-7: Short-circuit pipeline on empty OCR text
- **What:** If OCR returns empty/whitespace-only text, set `status='ocr_failed'`, skip VLM extraction. Don't waste 3 API calls on blank pages.
- **Why:** Saves API costs, keeps review queue clean.
- **Effort:** S (~15min)
- **Depends on:** None.
- **File:** `src/lab_manager/intake/pipeline.py`

### TODO-8: Use PostgreSQL in CI tests
- **What:** Update `tests/conftest.py` to use `DATABASE_URL` env var when set (CI has PostgreSQL service). Keep SQLite as local fallback.
- **Why:** Tests use SQLite but production uses PostgreSQL. JSONB, CHECK constraints, FOR UPDATE all behave differently. CI already has PostgreSQL configured but tests don't use it.
- **Effort:** S (~30min)
- **Depends on:** CI already configured with PostgreSQL service.

## P3 — Nice to have

### TODO-9: Structured logging with request_id
- **What:** Add structlog or python-json-logger. Generate UUID per request, attach to all log lines as `{request_id, user, timestamp, level}`.
- **Why:** When debugging a production issue, need to correlate log lines across middleware → route → service → DB. Currently impossible.
- **Effort:** M (~2hr)
- **Depends on:** None.

### TODO-10: Dashboard query optimization
- **What:** Consolidate `dashboard_summary()` from 12+ separate COUNT queries into 1-2 combined queries with subqueries or CTEs.
- **Why:** At scale (10K+ records), 12 round-trips to PostgreSQL will make the dashboard visibly slow. Not a current problem at 300 records.
- **Effort:** M (~1hr)
- **Depends on:** None.
- **File:** `src/lab_manager/services/analytics.py`

## Cross-reference: Existing review-fixes plan

The following 31 issues are tracked in `docs/superpowers/plans/2026-03-16-full-review-fixes.md`:
- **8 Critical:** C1-C8 (unique constraints, session commit, admin auth, prompt mismatch, file path leak, pipeline errors, dedup, SQL bypass)
- **13 Important:** I1-I12, PM3 (nullable FK, CHECK constraints, decimal types, file_name unique, API key location, path traversal, pagination, analytics limit, input validation, dead code, test coverage)
- **10 Minor:** M1-M7, PM1-PM2, PM4 (timestamps, JSONB, po_number index, model config, MIME types, substring matching, sync batching, extra JSONB, CAS validation, soft delete)

Some items overlap (e.g., SQL injection defense = C8 + TODO-2). The read-only DB user (TODO-2) is the architectural fix; C8's regex hardening is defense-in-depth.
