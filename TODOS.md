# TODOS — Lab Manager

> CEO-mode review (2026-03-16). **Agent handoff doc:** `docs/superpowers/plans/2026-03-16-agent-handoff.md` (start here).
> Eng review: `docs/superpowers/plans/2026-03-16-eng-review-todos.md`. Prior code review: `docs/superpowers/plans/2026-03-16-full-review-fixes.md`.

## P1 — Must fix before production deploy

### TODO-1: Basic authentication layer ✅ (PR-3, #6)
- Session cookie auth (itsdangerous signed), bcrypt password hashing, timing-safe login
- Merged auth+audit middleware: session cookies → API key fallback → dev-mode X-User
- Login/logout endpoints, set_staff_password.py CLI tool

### TODO-2: Read-only PostgreSQL user for RAG queries ✅ (PR-1, #4)
- Dedicated `labmanager_ro` user with SELECT-only grants on 8 tables
- `DATABASE_READONLY_URL` config, fallback to main engine + READ ONLY with warning log
- `docker/init-readonly-user.sql` for Docker Compose setup

### TODO-3: RAG SQL validation unit tests ✅ (PR-2 + PR-4, #5 + #7)
- 54 unit tests for `_validate_sql()` attack patterns (PR-2)
- 7 PG-only integration tests for `_execute_sql()` with real read-only enforcement (PR-4)
- Covers: forbidden keywords, stacked queries, comment injection, dollar quoting, Unicode bypass, dangerous functions, disallowed tables, statement timeout

### TODO-4: PostgreSQL backup script ✅ (PR-1, #4)
- `scripts/backup_db.sh` — daily pg_dump with 7-day rotation, gzip compression

## P2 — Should fix before production deploy

### TODO-5: Health endpoint with explicit service errors ✅ (PR-3, #6)
- `GET /api/health` checks PostgreSQL (SELECT 1), Meilisearch, Gemini config
- Returns 200 (all ok) or 503 (degraded) with per-service status
- Generic "error" messages — no exception string leakage

### TODO-6: CSV formula injection escaping ✅ (PR-1, #4)
- Cells starting with `=`, `+`, `-`, `@`, `\t` prefixed with `'`
- Applied to all CSV export endpoints

### TODO-7: Short-circuit pipeline on empty OCR text ✅ (PR-1, #4)
- Empty/whitespace-only OCR → `status='ocr_failed'`, skip VLM extraction
- Added `DocumentStatus.ocr_failed` enum value

### TODO-8: Use PostgreSQL in CI tests ✅ (PR-4, #7)
- Dual-engine conftest: auto-detects DATABASE_URL, PG for CI, SQLite for local dev
- `db_engine` fixture exposed for PG-only tests
- `pytestmark = pytest.mark.skipif(not _IS_PG)` pattern for PG-only tests

## P3 — Nice to have

### TODO-9: Structured logging with request_id ✅ (PR-5, #8)
- structlog with per-request UUID correlation via contextvars
- X-Request-ID response header on all responses (including 401)
- Contextvar cleanup in try/finally — no stale IDs leak between requests

### TODO-10: Dashboard query optimization ✅ (PR-5, #8)
- Consolidated 8 separate COUNT queries → 1 round-trip using scalar subqueries
- Works on both SQLite and PostgreSQL

## v0.1.1–v0.1.2 (2026-03-16) — Security hardening + UX

### TODO-11: Pre-release security hardening ✅ (PR #10, v0.1.1)
- SQLAdmin empty-password bypass guard
- RAG password_hash exposure prevention (removed from DB_SCHEMA)
- UNION/EXPLAIN/CALL/PREPARE/LISTEN/NOTIFY added to SQL forbidden patterns
- LIMIT(500) on 3 unbounded alert queries
- Path traversal validator on DocumentUpdate
- CSV escape fix for lab temperatures (-20C)
- Logout added to auth allowlist

### TODO-12: Login UI + review workflow ✅ (PR #11, v0.1.2)
- Login screen with email/password form + error display
- /api/auth/me endpoint for session verification
- Logout button in navbar with user name
- Rejection reason modal (review_notes)
- Auto-redirect to login on 401

## CEO Review (2026-03-18) — Pre-open-source

### TODO-13: escapeHtml() for all innerHTML calls (XSS prevention) ✅ (fix/xss-innerhtml)
- escapeHtml() exists in api.js and is applied to all API string values before innerHTML
- Fixed bug: `if (!s)` → `if (s == null || s === "")` so numeric 0 is handled correctly
- dashboard.js: added escapeHtml() to all card/alert template interpolations
- orders.js / inventory.js: parseInt() for page numbers from API responses
- Added 2 API-level XSS tests in test_api_security.py (vendor/product names with HTML chars)
- Priority: P2 | Effort: S | Depends on: nothing

### TODO-14: Duplicate order detection (PO# matching)
- No dedup check when creating orders from approved documents
- Same PO number can create multiple order records
- Add PO# uniqueness check in review UI before order creation
- Priority: P2 | Effort: M | Depends on: nothing

## Future — Post v0.1.2

### P1: Data editing before approval
- Allow scientists to correct OCR errors in extracted data before creating orders
- Prevents polluted orders from day one

### P2: Bulk review operations
- Select multiple documents, approve/reject in batch
- Critical for initial 279-document backlog

### P3: Better pagination
- Jump-to-page, total page count display
- Current Prev/Next only is slow for 9+ pages

### P4: Search improvements
- Empty-state guidance ("Did you mean...?" / suggest filters)
- Search analytics (track which queries fail)

### P5: RAG query visualization
- Show generated SQL to advanced users for debugging

### P6: Universal ingestion endpoint (AI-native "add anything")
- `POST /api/ingest` — upload photo, text, or file → AI classifies + extracts → human confirms → routes to correct table
- Two-step: upload → IngestRecord (pending) → confirm → Equipment/Document/Product
- Reuses existing VLM extraction pattern, AuditMixin, parse_json_response()
- Effort: L | Depends on: Equipment module (PR-15)

### P7: BDD shared step definitions (DRY cleanup)
- Extract common vendor/product/order creation steps into `tests/bdd/step_defs/common.py`
- Currently duplicated in 4+ step def files — any API schema change requires fixing all of them
- Also convert `test_alerts.py` setup entities (vendor, product, inventory, document) from `db.add()` to API calls for consistency (alert creation itself stays DB-direct — no API endpoint)
- Effort: M | Depends on: nothing

## Cross-reference: Existing review-fixes plan

The following 31 issues are tracked in `docs/superpowers/plans/2026-03-16-full-review-fixes.md`:
- **8 Critical:** C1-C8 (unique constraints, session commit, admin auth, prompt mismatch, file path leak, pipeline errors, dedup, SQL bypass)
- **13 Important:** I1-I12, PM3 (nullable FK, CHECK constraints, decimal types, file_name unique, API key location, path traversal, pagination, analytics limit, input validation, dead code, test coverage)
- **10 Minor:** M1-M7, PM1-PM2, PM4 (timestamps, JSONB, po_number index, model config, MIME types, substring matching, sync batching, extra JSONB, CAS validation, soft delete)

Some items overlap (e.g., SQL injection defense = C8 + TODO-2). The read-only DB user (TODO-2) is the architectural fix; C8's regex hardening is defense-in-depth.
