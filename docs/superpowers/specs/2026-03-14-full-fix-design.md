# Lab Manager Full Fix & Improvement Spec

**Date**: 2026-03-14
**Scope**: 4 independent sub-projects addressing all 32 audit findings

## Sub-project 1: Database & Infrastructure

### Files Modified
- `src/lab_manager/database.py` — singleton engine, pool config
- `src/lab_manager/api/deps.py` — delete duplicate get_db, import from database
- `src/lab_manager/models/order.py` — float→Decimal for unit_price, quantity
- `src/lab_manager/models/inventory.py` — float→Decimal for quantity_on_hand, fix == 0
- `src/lab_manager/models/consumption.py` — float→Decimal if applicable
- All models — add Relationship() with back_populates
- All FKs — add ondelete behavior
- `src/lab_manager/models/order.py`, `alert.py`, `inventory.py` — string→Enum for status/type
- `src/lab_manager/models/audit.py` — JSON→JSONB
- `src/lab_manager/models/base.py` — add server_default=func.now()
- `alembic/versions/` — new migration for all schema changes
- Update tests constructing models with float values

## Sub-project 2: Security Hardening

### Files Modified
- `src/lab_manager/config.py` — add api_key, remove hardcoded DB default
- `alembic.ini` — remove hardcoded URL
- `src/lab_manager/api/deps.py` — add verify_api_key dependency
- `src/lab_manager/api/app.py` — apply auth, protect /scans/
- `src/lab_manager/api/admin.py` — add AuthenticationBackend
- `src/lab_manager/services/rag.py` — read-only session, semicolon rejection, no SQL in response
- `src/lab_manager/static/index.html` — escapeHtml on all dynamic content
- `.env.example` — document all required env vars

## Sub-project 3: Pipeline v2 Fixes + Tests

### Files Modified
- `src/lab_manager/intake/consensus.py` — fix priority sort, add tie detection
- `src/lab_manager/intake/pipeline.py` — remove auto-approve
- `src/lab_manager/intake/schemas.py` — Literal type for document_type
- `src/lab_manager/intake/validator.py` — negative qty check, configurable threshold
- `src/lab_manager/config.py` — update extraction_model default (done by sub-project 2)
- `tests/test_consensus.py` — new, ~15 tests
- `tests/test_validator.py` — new, ~12 tests

## Sub-project 4: Data Quality & Polish

### Files Modified
- `src/lab_manager/services/analytics.py` — strftime→to_char
- `src/lab_manager/services/alerts.py` — cache check results
- `src/lab_manager/api/pagination.py` — optional has_more mode
- `src/lab_manager/services/inventory.py` — domain exceptions
- `src/lab_manager/services/search.py` — warning level logging
- `src/lab_manager/models/alert.py` — composite index
- API routes — sort_by allowlist, LIKE wildcard escaping
- `src/lab_manager/api/routes/orders.py` — soft-delete order items

## Execution Order

Sub-projects 1, 2, 3 run in parallel. Sub-project 4 runs after 1 completes.
