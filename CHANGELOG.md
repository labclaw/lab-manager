# Changelog

All notable changes to LabClaw Lab Manager will be documented in this file.

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
