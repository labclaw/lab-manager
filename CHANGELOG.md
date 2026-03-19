# Changelog

All notable changes to LabClaw Lab Manager will be documented in this file.

## [0.1.5] - 2026-03-19

### Added
- Lab equipment module with VLM photo extraction (#15)
- Separated lab-specific data (equipment) from generic product model (#16)
- First-run setup wizard — `POST /api/setup/complete` creates first admin user, `GET /api/setup/status` checks initialization state
- Configurable lab branding (lab name, logo, primary color) via setup wizard
- API v1 prefix — all resource endpoints now under `/api/v1/` with typed response models (#31)
- PO# duplicate detection on order creation (TODO-14) (#33)
- Installer script and DigitalOcean deployment automation (#42)
- CI coverage enforcement and CodeQL security scanning (#29)

### Changed
- Auth defaults hardened — `SECURE_COOKIES=True`, rate limiting on login, `X-User` header spoofing prevention (#30)
- Admin credential boundaries tightened (#20)
- Frontend wired with react-router and react-query; error UI for failed requests (#27)
- React SPA routing with `dist/` serving and catch-all middleware (#21)
- Pre-commit hooks for code quality (ruff, trailing whitespace) (#28)
- Comprehensive BDD scenario coverage for all API modules (#35)

### Fixed
- **XSS**: `escapeHtml` applied to all `innerHTML` interpolations (#32)
- **Security**: password_hash hidden from SQLAdmin detail/edit views
- **Intake**: consensus pipeline bug fixes (edge cases in majority voting) (#23)
- **DB**: RAG schema updated, stale staff references cleaned up (#24)
- **Test**: SQLite threading issues in BDD tests resolved (#34)
- **Test**: 100% test coverage achieved with BDD fix (#36)
- **Setup**: email/name validation, email removed from logs, TOCTOU race fixed (#43)
- **Setup**: stale settings cache after wizard, cloud-init compatibility (#40)

## [0.1.4] - 2026-03-19

### Added
- Document upload endpoint — `POST /api/documents/upload` with file isolation
- Upload, inventory, and orders frontend views
- Stitch dark theme for frontend UI
- PWA support — `manifest.json`, service worker, app icons, installable routes
- Cloudflare Tunnel integration and shenlab-docs static mount in Docker

### Changed
- Frontend JS extracted into modular files (`app.js`, `router.js`)
- Caddyfile CSP updated for Tailwind CDN, Google Fonts, camera access

### Fixed
- Duplicate `/uploads` static mount removed
- Upload filenames sanitized to prevent path traversal
- API errors surfaced to users instead of silent failures
- Frontend pagination aligned with API response format
- NaN% display prevented on empty database dashboards

## [0.1.3] - 2026-03-17

### Added
- Production deployment — Caddy TLS termination, secure secrets, disk monitoring, non-root Docker (#14)
- BDD test infrastructure with 27 scenarios across 5 domains (vendors, orders, inventory, documents, alerts)
- Domain exception hierarchy, middleware split, route hardening

### Changed
- Docker image build order corrected, user home directory fixed
- Config tolerates extra env vars without error; Docker env override prevented
- `/api/auth/me` returns default user when auth disabled

### Fixed
- **Security**: RAG SQL validation hardened, SQLAdmin auth tightened
- **Security**: `password_hash` no longer exposed in SQLAdmin detail/edit views
- **Deploy**: RLock deadlock in startup, auth parameterized for deploy environments, Caddy wildcard handling
- **Deploy**: env vars, auto-migration on boot, uv version pinned
- **QA**: responsive CSS for mobile layout, inline scripts allowed in CSP for SPA
- **QA**: scan images viewable in Docker via shenlab-docs mount
- **Test**: read-only transaction rollback before RAG test cleanup
- **Lint**: all ruff errors and format violations resolved

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
