# Changelog

All notable changes to LabClaw Lab Manager will be documented in this file.

## [0.1.3] - 2026-03-17

### Added
- **Full SPA UI**: 9 vanilla JS view modules (dashboard, documents, review, inventory, orders, search, app, API client, shared components) with hash-based routing
- **Dashboard**: KPI stat cards, vendor/type bar charts, alert banners (low stock + expiring)
- **Document review**: Inline edit mode for OCR-extracted data, Save & Approve, Reject with reason
- **Bulk review**: Checkbox selection with bulk approve/reject (Promise.allSettled for partial failure handling)
- **Inventory management**: Consume, transfer, adjust, dispose, open actions with modals and activity history
- **Order workflow**: Detail panel with line items, receive shipment flow creating inventory
- **Global search**: Autocomplete dropdown, grouped results by entity type, nav bar integration
- **CSS design system**: Shared styles, responsive layout, detail panel, modal system, toast notifications
- **78 BDD UI test scenarios**: Playwright-based browser tests across 8 feature files
- Docker entrypoint script with auto-migration on startup
- `get_or_404()` helper and `BusinessError` domain exception hierarchy

### Changed
- Split monolithic auth+audit middleware into separate auth (outer) and audit (inner) middleware for clearer separation of concerns
- Session cookie max-age reduced from 7 days to 24 hours
- Content-Security-Policy updated to allow `script-src 'unsafe-inline'` and `connect-src 'self'` for SPA
- Caddyfile domain made configurable via `$DOMAIN` env var
- Pin `uv==0.7.12` in Dockerfile for reproducible builds
- `.gstack/` added to `.gitignore`
- `DocumentUpdate.status` now validates against allowed status values
- RAG `_ALLOWED_TABLES` now includes `staff` (password_hash blocked by `_FORBIDDEN_COLUMNS`)

### Fixed
- 14 design findings fixed (D+ → B+ design score): table headers, touch targets, snake_case labels, panel visibility on mobile, font inheritance, abbreviation handling
- Detail panel hidden on mobile/tablet when closed (visibility:hidden vs overflow-x:hidden for fixed elements)
- Detail panel closes on view switch (no stale content)
- Close button touch target increased to 44px minimum
- SQLAdmin `password_hash` excluded from detail/edit views

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
