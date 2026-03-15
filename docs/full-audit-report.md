# Lab Manager Full Audit Report

**Date**: 2026-03-14
**Scope**: Full project review — code quality, security, OCR benchmarks, pipeline accuracy, data quality
**Codebase**: 6,793 lines Python (5,412 src + 1,381 tests), 62 files, 75 API endpoints

---

## 1. Executive Summary

Lab Manager is a lab inventory management system with OCR document intake for MGH Shen Lab (neuroscience). It ingests 279 scanned documents (packing lists, invoices, COAs, shipping labels) from 12+ vendors, extracts structured data via VLMs, and manages inventory through a FastAPI web app.

**Overall verdict: Fix before deploy.** The application layer (API, CRUD, audit, search) is solid and well-tested. The document intake pipeline — the core differentiator — has algorithm bugs, zero test coverage, and a 53.4% accuracy baseline. Security is minimal (no auth). Data quality issues affect financial reporting.

| Dimension | Status | Score |
|-----------|--------|-------|
| Architecture & Design | Good | 7/10 |
| Code Quality (App Layer) | Good | 7/10 |
| Code Quality (Pipeline) | Needs Work | 4/10 |
| Test Coverage (App) | Good | 8/10 |
| Test Coverage (Pipeline) | Critical Gap | 1/10 |
| Security | Not Production-Ready | 3/10 |
| OCR Quality | Gemini Dominant | See benchmarks |
| Pipeline Accuracy (v1) | Failing | 53.4% |
| Data Completeness | Partial | See data quality |

---

## 2. Architecture Overview

```
Layer 1 (CORE):     PostgreSQL 17 — 12 tables, 2 migrations, ACID, audit trail
Layer 2 (APP):      FastAPI + SQLModel + SQLAdmin + Meilisearch + Alembic
Layer 3 (AI):       OCR (Qwen3-VL/Gemini Flash) → VLM extraction → consensus → human review
```

### Stack
- Python 3.12+, FastAPI, SQLModel, PostgreSQL 17, Alembic, SQLAdmin
- Meilisearch for full-text search, Gemini NL→SQL for RAG
- Docker Compose (db + search + app)
- uv package manager, pytest + pytest-asyncio + testcontainers

### Database Tables (12)
vendors, products, orders, order_items, inventory_items, documents, staff, locations, alerts, audit_log, consumption_log, + alembic_version

### API Surface (75 endpoints across 11 route modules)
- Vendors (7), Products (7), Orders (11), Inventory (13), Documents (7)
- Search (2), RAG/Ask (4), Analytics (10), Export (4), Alerts (5), Audit (2)
- Plus: admin panel, health check, static file serving

---

## 3. Critical Issues (Must Fix)

### 3.1 Connection Pool Leak
**File**: `src/lab_manager/database.py:13-15`

`get_engine()` creates a new SQLAlchemy engine on every call. Since `get_db()` calls `get_engine()` per HTTP request, every request creates a new connection pool. Under load, this exhausts PostgreSQL's `max_connections` (default 100) and crashes the app.

**Fix**: Make engine a module-level singleton with pool configuration:
```python
_engine = None
def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, pool_size=10, max_overflow=20, pool_pre_ping=True)
    return _engine
```

### 3.2 Zero Authentication
**Files**: `api/app.py:29-31`, `api/admin.py:108`

- API auth relies on an unverified `X-User` header — anyone can impersonate any user
- SQLAdmin panel at `/admin/` has zero authentication — full CRUD on all tables
- `/scans/` serves all lab documents (invoices, POs, vendor info) publicly

**Impact**: Audit trail is untrustworthy, data can be modified by anyone on the network.

### 3.3 RAG SQL Injection Risk
**File**: `services/rag.py:269-273`

LLM-generated SQL is executed via `db.execute(text(sql))` with only regex-based validation. Bypass vectors include:
- Stacked queries: `SELECT 1; DROP TABLE vendors` (semicolons within body not rejected)
- PostgreSQL I/O functions not in blocklist
- Prompt injection via user question → LLM outputs destructive SQL

**Fix**: Execute on a read-only database role (`SET TRANSACTION READ ONLY`), not regex filtering.

### 3.4 Consensus Algorithm Bug — Wrong Model Priority
**File**: `src/lab_manager/intake/consensus.py:96-100`

```python
# All disagree — prefer opus, then gemini, then gpt
for model in sorted(values.keys()):  # BUG: alphabetical sort
```

`sorted()` produces alphabetical order: codex → gemini → opus. The intended priority is opus → gemini → codex (reversed). In 3-way disagreements, the wrong model's answer wins silently.

### 3.5 Consensus Tie Detection Missing
**File**: `src/lab_manager/intake/consensus.py:84-86`

When two groups both have equal vote counts (e.g., 2 models each), `max()` picks one arbitrarily. No `needs_human` flag is set. The field is auto-resolved with no indication of ambiguity.

### 3.6 Auto-Approve Uses Uncalibrated Confidence
**File**: `src/lab_manager/intake/pipeline.py:97-100`

v1 pipeline auto-approves orders at confidence >= 0.95. The audit proved this threshold has a **24.6% false positive rate** — 52 out of 211 auto-approved documents contain critical errors. This directly contradicts the project's "human-in-the-loop is mandatory" principle.

### 3.7 Float for Money
**Files**: `models/order.py:42` (`unit_price: float`), `models/inventory.py:24` (`quantity_on_hand: float`)

Floating-point arithmetic accumulates rounding errors. `$19.99 × 3 = $59.970000000000006`. In `inventory.py:143`, `if item.quantity_on_hand == 0` fails after float subtraction, leaving "depleted" items with phantom quantities.

**Fix**: Use `Decimal` in Python + `sa.Numeric(precision=12, scale=4)` in PostgreSQL.

### 3.8 Hardcoded Database Credentials
**Files**: `config.py:13`, `alembic.ini:2`

Default `DATABASE_URL` contains hardcoded credentials (`labmanager:labmanager`). If env var is not set, app silently connects with known default password.

---

## 4. Important Issues (Should Fix Soon)

| # | Location | Issue |
|---|----------|-------|
| 1 | All models | Zero `Relationship()` definitions — every related query is N+1 |
| 2 | All foreign keys | No `ON DELETE` behavior — parent deletion causes IntegrityError |
| 3 | `static/index.html:413` | DOM XSS: `file_name`, `vendor_name` rendered via template literals without `escapeHtml()` in list views |
| 4 | `app.py:70` | `/scans/` serves all lab documents publicly |
| 5 | `rag.py:20` | Model hardcoded to `gemini-2.5-flash` (missing `-preview` suffix, outdated) |
| 6 | `config.py:22` | Default `extraction_model` is `gemini-2.5-flash-preview` — should be `gemini-3.1-flash-preview` |
| 7 | Pipeline v1 vs v2 | Two parallel pipelines, API still uses v1 single-model path |
| 8 | `schemas.py` vs `validator.py` | Extractor prompt says "package" is valid doc type, validator rejects it |
| 9 | `analytics.py:201` | `func.strftime` is SQLite-only, fails on PostgreSQL |
| 10 | `models/order.py:24` | Status/type fields are free-form strings, no enum or check constraint |
| 11 | `api/pagination.py:14` | `query.count()` does full table scan per paginated request |
| 12 | `validator.py:61` | Checks `qty == 0` but not negative quantities |
| 13 | `deps.py` vs `database.py` | `get_db()` duplicated in two files |
| 14 | `services/inventory.py:8` | Service imports `HTTPException` — couples service to web framework |
| 15 | `alerts.py:247` | Alert checking runs 18 queries per single API call (3 runs × 6 queries) |

---

## 5. OCR Benchmark Results

### Benchmark 1: 160 Documents (ocr_benchmark.py)

| Model | Success | Avg Jaccard | Avg Edit Dist | Speed | >=0.90 sim |
|-------|---------|-------------|---------------|-------|------------|
| **Gemini 2.5 Flash API** | **158/160 (98.8%)** | **0.920** | **504** | **8.0s** | **75.9%** |
| Claude Sonnet 4.6 | 156/160 (97.5%) | 0.770 | 797 | 27.3s | 18.6% |
| Gemini CLI | 38/160 (23.8%) | 0.781 | 555 | 31.2s | 13.1% |

### Benchmark 2: 40 Documents (run_ocr_benchmark.py, SOTA models)

| Model | Success | Avg Jaccard | Avg Edit Dist | Speed |
|-------|---------|-------------|---------------|-------|
| **Gemini 2.5 Pro API** | **39/40 (97.5%)** | **0.917** | **382** | **15.6s** |
| Opus 4.6 | 40/40 (100%) | 0.745 | 936 | 28.3s |
| Gemini 3.1 Pro CLI | 0/40 | — | — | skill conflict |
| Codex GPT-5.4 | 0/40 | — | — | CLI broken |

### Quality Distribution (160 docs)

| Similarity Range | Gemini Flash | Claude Sonnet | Gap |
|-----------------|--------------|---------------|-----|
| >= 0.95 | 44.9% | 10.3% | +34.6 |
| >= 0.90 | 75.9% | 18.6% | +57.3 |
| < 0.70 (poor) | 1.3% | 26.9% | -25.6 |

### Root Causes for Claude's Lower OCR Quality

1. **Preamble noise** (85% of docs): Adds "Here is the full transcription:" despite prompt saying "output plain text only"
2. **Text inflation** (+59%): Markdown headers, separators, verbose formatting
3. **Field misreads**: PO number accuracy 82% vs Gemini 88%

### OCR Recommendation

| Pipeline Stage | Recommended Model | Reason |
|---------------|-------------------|--------|
| Stage 0: OCR | Gemini 2.5 Flash API | Fastest (8s), highest fidelity (0.920), cheapest |
| Stage 1: Extraction | Opus 4.6 + Gemini 3.1 Pro + GPT-5.4 | Reasoning ability matters here, not transcription |

---

## 6. Pipeline v1 Accuracy Audit (279 Documents)

### Overall Results

| Metric | Value |
|--------|-------|
| Total documents | 279 |
| Correct (no errors) | 149 (53.4%) |
| Minor errors only | 52 (18.6%) |
| **Critical errors** | **78 (28.0%)** |

### Confidence Calibration (Broken)

| Metric | Value |
|--------|-------|
| Auto-approved (conf >= 0.95) | 211 docs |
| Of those with critical errors | 52 (24.6% false positive) |
| High-confidence accuracy | 57.3% (should be >95%) |
| Average confidence | 0.954 |
| Median confidence | 1.0 |

**Conclusion**: Confidence scores are not correlated with accuracy. The model reports high confidence even on incorrect extractions.

### Top Error Categories

| Rank | Error Type | Count | Rate |
|------|-----------|-------|------|
| 1 | Document type misclassification | 41 | 14.7% |
| 2 | Order number error | 33 | 11.8% |
| 3 | Vendor identification error | 30 | 10.8% |
| 4 | Lot/batch confusion | 20 | 7.2% |
| 5 | Reference number error | 17 | 6.1% |
| 6 | Date interpretation error | 14 | 5.0% |
| 7 | Quantity error | 14 | 5.0% |
| 8 | Description error | 12 | 4.3% |
| 9 | Items extraction error | 8 | 2.9% |
| 10 | Catalog number error | 7 | 2.5% |

### Document Type Accuracy

| Type | Docs | Correct | Accuracy |
|------|------|---------|----------|
| packing_list | 236 | 134 | 56.8% |
| invoice | 17 | 8 | 47.1% |
| package | 15 | 3 | 20.0% |
| shipping_label | 4 | 1 | 25.0% |

### Known Error Patterns

- **COA → packing_list**: Certificate of Analysis misclassified
- **PO/order/tracking confusion**: PO-108037796 vs PO-10803796 (extra digit)
- **Address as vendor name**: "529 N. Baldwin Park Blvd" extracted as vendor
- **Template text as data**: "PROVIDER: Organization providing the ORIGINAL MATERIAL"
- **VCAT as lot number**: VCAT reference codes mistaken for lot/batch numbers
- **Vendor name variants**: "Milttenyi" / "Miltenyi", "xife technologies" / "Life Technologies"

---

## 7. Data Quality Assessment

### Database Statistics

| Entity | Count | Notes |
|--------|-------|-------|
| Vendors | 81 | Deduplicated from ~122 raw (8 Sigma-Aldrich variants) |
| Products | 215 | Deduplicated from 309 order items |
| Orders | 211 | Unique POs |
| Order Items | 309 | |
| Documents | 279 | Scanned lab supply docs |
| Staff | 26 | Extracted from signatures, has duplicates |
| Locations | 7 | Fridges, freezers, shelves |

### Data Gaps

| Issue | Impact | Severity |
|-------|--------|----------|
| `unit_price` missing on 86.4% of order items (267/309) | All spending analytics show $0 | High |
| Vendor name duplicates (8 variants of Sigma-Aldrich) | Splits analytics by vendor | Medium |
| Staff name duplicates ("Pei Wang" / "Wang Pei" / "Wangpei") | Audit trail attribution inaccurate | Medium |
| `min_stock_level` unset on all 215 products | Low-stock alerts non-functional | Medium |
| 7 documents with null/unknown document type | Skipped in type-specific analytics | Low |
| 4 non-purchasing docs (MTA, legal agreements) in pipeline | Noise in extraction metrics | Low |

---

## 8. Test Coverage

### Summary

| Module | Tests | Coverage |
|--------|-------|----------|
| API CRUD (vendors, orders, inventory, documents) | 40+ | Good |
| Audit trail | 8 | Good |
| Analytics/Export | 10+ | Good |
| Alerts | 8+ | Good |
| Config | 3 | Good |
| Models | 5 | Adequate |
| Intake schemas | 2 | Minimal |
| Intake extractor | 1 | Minimal (mocked) |
| **Intake consensus** | **0** | **Zero** |
| **Intake validator** | **0** | **Zero** |
| **Intake OCR** | **0** | **Zero** |
| **Intake pipeline** | **0** | **Zero** |
| **All providers** | **0** | **Zero** |

**87 tests, all passing.** But the entire document intake pipeline — the project's core value proposition — has effectively 3 tests (2 schema construction + 1 mocked extractor).

---

## 9. Security Assessment

| Category | Status | Finding |
|----------|--------|---------|
| Authentication | Missing | `X-User` header unverified, SQLAdmin unauthenticated |
| Authorization | Missing | No role-based access, no permission checks |
| SQL Injection | Risk | RAG service executes LLM-generated SQL with regex-only filtering |
| XSS | Partial | `escapeHtml()` exists but not applied to all dynamic content in list views |
| CSRF | N/A | No session-based auth to protect |
| Credential Management | Weak | Hardcoded defaults in config.py and alembic.ini |
| File Access | Open | `/scans/` serves all lab documents without auth |
| Data Validation | Partial | No enum constraints on status/type fields |
| Audit Integrity | Weak | Audit `changed_by` from unverified header, can be spoofed |

---

## 10. What's Done Well

1. **Architecture layering**: Clear separation — database is the foundation, AI is an enhancement layer
2. **Audit trail**: SQLAlchemy event-driven audit captures diffs in `before_flush`, writes in `after_flush` — handles PK timing correctly
3. **Application test coverage**: 87 tests covering API CRUD, audit, analytics, alerts — all passing
4. **Pagination consistency**: Uniform `page`/`page_size`/`filter`/`sort` pattern across all list endpoints
5. **Soft-delete pattern**: Consistently applied (except order items)
6. **Meilisearch integration**: Declarative index configuration, proper faceting
7. **Multi-model consensus design**: The 3-VLM consensus concept is architecturally sound (execution has bugs)
8. **Validation rules**: Catches real error patterns discovered in the audit (VCAT codes, address-as-vendor)
9. **Human-in-the-loop philosophy**: Documented and designed for, even if v1 pipeline violates it
10. **Documentation**: CLAUDE.md is comprehensive, audit results are detailed

---

## 11. Prioritized Fix Roadmap

### Phase 1: Critical (Before Any Deployment)
1. `database.py` — Singleton engine with pool configuration
2. `consensus.py:96` — Fix model priority sort (alphabetical → explicit order)
3. `consensus.py:84` — Add tie detection, flag as `needs_human`
4. `pipeline.py:97` — Remove auto-approve or gate behind explicit flag
5. Add basic authentication (API key minimum) to API, admin, and `/scans/`
6. `rag.py` — Execute SQL on read-only database role
7. `models/order.py` — Change `unit_price` and `quantity` from float to Decimal

### Phase 2: Important (Before Production Use)
8. Write `test_consensus.py` — unanimous, majority, tie, all-disagree, single-model, all-fail
9. Write `test_validator.py` — each rule, edge cases
10. Add `Relationship()` definitions to all models
11. Add `ON DELETE CASCADE/RESTRICT` to foreign keys
12. Fix `analytics.py:201` — `strftime` → `to_char` for PostgreSQL
13. Integrate v2 pipeline into API (replace v1 single-model path)
14. Reconcile document_type between extractor prompt, schema, and validator
15. Update model defaults: `gemini-2.5-flash` → `gemini-3.1-flash-preview`

### Phase 3: Polish (Before Scale)
16. Add enum/check constraints on status/type string fields
17. Fix `escapeHtml()` coverage in frontend list views
18. Optimize alert checking (cache results, avoid triple execution)
19. Replace `query.count()` with window function or `has_more` pagination
20. Add `sort_by` allowlist and LIKE wildcard escaping
21. Use JSONB instead of JSON for audit_log.changes
22. Staff name normalization (fuzzy match dedup)
23. Product `min_stock_level` wizard for scientists
24. Backfill `unit_price` from original scans

---

## 12. Key Metrics Summary

```
Codebase:          6,793 lines Python, 62 files
API Endpoints:     75 (11 route modules)
Database Tables:   12 (2 migrations)
Tests:             87 passing, 0 failing
Pipeline Accuracy: 53.4% (v1), unknown (v2, untested)
Critical Errors:   28.0% of documents
Confidence FPR:    24.6% at 0.95 threshold
OCR Best Model:    Gemini 2.5 Flash API (0.920 Jaccard)
OCR Worst Model:   Claude Sonnet 4.6 (0.770 Jaccard)
Security:          No authentication
Data Completeness: unit_price 13.6%, min_stock_level 0%
```
