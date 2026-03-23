# Changelog

All notable changes to LabClaw Lab Manager will be documented in this file.

## [0.1.8.1] - 2026-03-22

### Fixed
- Defensive API response parsing in `_response_text()` and `_ocr_nvidia()` — prevents crashes on malformed/empty API responses
- Command injection prevention in Claude/Codex OCR providers via `shlex.quote()`
- GLM5NIM provider: defensive response parsing + skip refinement on empty OCR
- `batch_ingest.py`: status logic bug (consensus docs now `processed` instead of always `needs_review`)
- `batch_ingest.py`: DB session leak on exception, JSON parse safety, 50MB file size check
- `full_benchmark.py`: ETA calculation fix on resume (division by zero guard)

## [0.1.8] - 2026-03-21

### Added
- **Tiered OCR detection**: `OCR_TIER` setting (`local`/`api`/`auto`) — local vLLM models as fast initial detection, API fallback
- **DeepSeek-OCR provider**: Dedicated 3B OCR model via vLLM (0.1-0.4 sec/page, 16GB VRAM)
- **PaddleOCR-VL provider**: Ultra-lightweight 0.9B model via vLLM (2-3GB VRAM, 109 languages)
- **Mistral OCR 3 provider**: Dedicated `/v1/ocr` API endpoint ($2/1k pages, 96.6% table accuracy)
- New config settings: `OCR_TIER`, `OCR_LOCAL_MODEL`, `OCR_LOCAL_URL`, `MISTRAL_API_KEY`
- 23 new tests for providers, tiered detection, and config

## [0.1.7] - 2026-03-20

### Fixed
- Fixed `lucide-react` icon library not resolving in frontend builds and tests (missing from node_modules)
- Removed unused `EmptyState` import in ReviewPage causing lint failure
- Fixed stale ref access in UploadPage effect cleanup (react-hooks/exhaustive-deps)

### Changed
- Cleaned up 27 stale branches (21 local + 6 remote) and 6 orphaned worktrees — all superseded by main
- Deleted `fix/inventory-session-type` branch (SQLModel `db.exec()` migration superseded by SQLAlchemy 2.0 `db.scalars()`/`db.execute()` already in main)
- All frontend tests now pass: 12/12 test files, 154/154 tests, lint clean, build clean
- Backend: 916 passed, 12 skipped

## [0.1.6] - 2026-03-20

### Fixed
- Restored fresh-install reliability for setup, auth, export, migration-aware startup, and review/search indexing flows
- Fixed pipeline import and startup regressions that broke clean Docker and self-hosted CI runs
- Added request-size and order-item quantity guards for oversized JSON bodies and unrealistic quantities
- Aligned frontend tests, upload tests, and API security regression coverage with the current `/api/v1/*` contract
- Moved GitHub Actions to the available self-hosted runner and fixed the secrets-scan install path for gitleaks

### Changed
- Defined `v0.1.6` as the minimum stable internal release
- Release CI now gates on the maintained core suite (`tests --ignore=tests/bdd`) plus frontend lint/build/test, while legacy BDD coverage remains under cleanup

## [0.1.5] - 2026-03-19

### Fixed
- Wheel builds now include the shipped static frontend assets required for the backend-served UI

### Changed
- Reworked release docs around local trial, one-command deployment, and first-run browser setup
- Added a local environment bootstrap script for evaluators who want to try Lab Manager on `localhost`
- Clarified that the React frontend is still an in-progress release surface

## [0.1.2] - 2026-03-16

### Added
- Login screen with email/password authentication form
- `/api/auth/me` endpoint for frontend session verification
- Logout button in navbar with current user name display
- Rejection reason modal — optional text stored as `review_notes`
- Auto-redirect to login on expired session (401 handling)
- User-aware document reviews (`reviewed_by` uses logged-in user name)

### Changed
- Toast notification duration increased from 3s to 5s

## [0.1.1] - 2026-03-16

### Fixed
- **SQLAdmin auth bypass**: Empty `API_KEY` allowed unauthenticated admin access
- **RAG password exposure**: Removed `password_hash` from NL-to-SQL schema
- **SQL injection**: Added `UNION`, `EXPLAIN`, `CALL`, `PREPARE`, `LISTEN`, `NOTIFY` to forbidden patterns
- **Unbounded queries**: Added `LIMIT(500)` to 3 alert check queries
- Path traversal validator added to `DocumentUpdate`
- CSV export: `-20C` freezer temps no longer corrupted by formula escaping
- `/api/auth/logout` added to auth allowlist
- Redundant `(ValueError, Exception)` catch simplified

## [0.1.0] - 2026-03-16

### Added
- FastAPI application with 52 API endpoints across 11 route modules
- PostgreSQL database with 10 tables (vendors, products, orders, inventory, documents, staff, locations, alerts, audit_log, consumption_log)
- Session cookie authentication (itsdangerous signed) with bcrypt password hashing
- API key fallback authentication for programmatic access
- SQLAdmin UI at `/admin/` with dedicated auth backend
- Read-only PostgreSQL user for RAG SQL queries (`DATABASE_READONLY_URL`)
- RAG NL-to-SQL via Gemini with SQL validation and Meilisearch fallback
- Meilisearch full-text search across products, vendors, orders, documents
- Document intake pipeline with OCR and multi-VLM extraction
- CSV export with formula injection escaping
- Structured logging with per-request UUID correlation (structlog)
- Health endpoint checking PostgreSQL, Meilisearch, and Gemini status
- Alert system: expiry, low stock, stale orders, pending review
- Audit trail via SQLAlchemy event listeners
- Dashboard analytics with consolidated scalar subqueries
- PostgreSQL backup script with 7-day rotation
- Docker Compose setup with init-readonly-user.sql
- 236 tests (54 RAG validation + 7 PG integration + full CRUD coverage)
