# Changelog

All notable changes to LabClaw Lab Manager will be documented in this file.

## [0.2.0] - 2026-03-25

First milestone release. Promotes the full 0.1.x development series (239 PRs, 400+ commits) to a stable baseline for multi-lab deployment.

### Highlights
- **52 API endpoints** across 11 route modules with session cookie + API key auth
- **OCR document intake** with multi-VLM extraction, tiered local/API detection, consensus pipeline
- **React frontend** with persistent chat, Cloud Brain skills, analytics, settings, review queue
- **Production CI/CD**: GitHub Actions, GHCR Docker publish, CodeQL security scanning
- **160 Playwright E2E tests** + 900+ backend unit/integration tests
- **Cost-aware LLM routing** via LiteLLM with extraction eval harness and iterative refinement
- **One-click vendor reorder** with 17+ vendor website integrations

### Changes since v0.1.9
- fix(ci): add retry loop to Docker publish verify step (#239)
- fix(security): sanitize test fixtures and pin CI action SHAs (#238)

## [0.1.9] - 2026-03-26

Consolidates all development since v0.1.7 (354 commits). The 0.1.8.x series was never formally tagged — this release captures everything.

### Added
- **Tiered OCR detection** with local models: DeepSeek-OCR, PaddleOCR-VL, Mistral OCR 3 (#162)
- **Unified LLM client** with LiteLLM config file support (#176)
- **Analytics page** with tabbed vendor, document, and inventory insights (#188)
- **Vendor name normalization** to reduce duplicates (#192)
- **One-click reorder** with vendor website integration for 17+ vendors (#194)
- **Settings page** with lab profile, AI config, notifications (#196)
- **Persistent chat history** with conversation management (#197)
- **Cloud Brain page** for scientific AI skills integration (#198)
- **Extraction eval harness**, query planning, iterative refinement (#205)
- **Cost-aware routing**, pipeline hooks, proactive notifications (#212)
- **Comprehensive E2E test suite**: 160 Playwright tests (#206)
- **GitHub automation**: dependabot, templates, labels, stale bot (#201)
- **GHCR Docker image publish** workflow (#177)
- 190 new unit tests for 5 low-coverage modules (93% to 98%) (#170)

### Fixed
- **Security**: address critical and high-severity vulnerabilities (#208)
- **Security**: remove competitive market research from public repo (#235)
- **Security**: pin litellm<=1.82.6 against supply chain attack (#186)
- CI port conflicts and BDD test isolation (#161)
- Deploy readiness: serialize CI, visible loading, TestClient lifecycle (#163)
- Defensive OCR parsing, injection prevention, status logic (#164)
- Default models switched to NVIDIA (benchmark-backed) (#167)
- Production readiness: Decimal types, Equipment constraints, infra scripts
- 8 critical+high UI bugs: search crash, routing, mobile nav (#182)
- 10 visual design fixes: unified colors, theme, layout (#183)
- Comprehensive visual polish for VC demo (#187)
- Light backgrounds everywhere, inventory guidance, orders UX (#189)
- Documents page polish: badges, confidence bars, vendor names (#191)
- Generalize deployment-specific references in configs and scripts (#193)
- Remove dark mode entirely, force light theme (#195)
- Settings page with real data (#204)
- Normalize API URLs with trailing slash to prevent 307 redirects

### Performance
- Ask AI cache + scalar shortcut, indexes, redirect fix (#184)

### CI/CD
- Production-grade CI/CD pipeline (#199)
- Switch to GitHub-hosted runners (#200, #203)
- Bump actions/checkout, setup-node, setup-uv, upload-artifact, codeql-action (#171-#175)
- Bump docker/metadata-action 5.7.0 to 6.0.0 (#222)
- Bump docker/login-action 3.4.0 to 4.0.0 (#218)
- Bump github/codeql-action 3.33.0 to 4.34.1 (#221)

### Refactored
- Simplify code quality: imports, N+1, DRY (#213)
- Differentiate Analytics from Dashboard: insights not duplication (#190)

### Other
- Remove all deployment-specific data and references (#166)
- Prepare lab-manager for open-source release (#185)

## [0.1.8.3] - 2026-03-23

### Added
- **E2E edge case tests**: 97 new e2e tests covering error handling, edge cases, and API validation
  - Inventory: pagination, sorting, expiring endpoint, negative quantity, filtering, history, transfer, dispose
  - Orders: pagination, receive endpoint, items CRUD, status transitions, validation, search/filter
  - Documents: upload validation, CRUD edge cases, review workflow, filtering, stats, upload formats
  - Auth: login edge cases, session management, password change, protected endpoints, setup flow, user management, token auth

### Changed
- E2E fixtures changed from session-scoped to function-scoped for better test isolation
- Test entities now use unique suffixes to avoid collisions in parallel test runs

## [0.1.8.2] - 2026-03-23

### Added
- **E2E edge case tests**: 97 new e2e tests covering error handling, edge cases, and API validation
  - Inventory: pagination, sorting, expiring endpoint, negative quantity, filtering, history, transfer, dispose
  - Orders: pagination, receive endpoint, items CRUD, status transitions, validation, search/filter
  - Documents: upload validation, CRUD edge cases, review workflow, filtering, stats, upload formats
  - Auth: login edge cases, session management, password change, protected endpoints, setup flow, user management, token auth, rate limiting

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
