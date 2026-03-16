# Document Verification Agent — Design Spec

**Date**: 2026-03-16
**Status**: Reviewed
**Scope**: Automated verification of OCR-extracted data against vendor websites and public databases

## Problem

Pipeline v1 audit showed 53.4% accuracy with 28% critical errors. OCR-extracted fields (catalog numbers, product names, CAS numbers, prices, storage temps) cannot be trusted without verification. Manual checking of 279+ documents is impractical.

## Solution

A verification agent that autonomously searches vendor websites to cross-check extracted data, logs all evidence, and escalates only uncertain cases to human reviewers.

## Design Principles

1. **Correctness over speed** — real web searches, no mocking, honest "not_found" when data unavailable
2. **Maximum autonomy** — agent does all work it can; human only intervenes when agent is uncertain
3. **Full traceability** — every verification links back to source document and original scanned image
4. **Easy for both human and agent** — clear status workflow, structured evidence, direct file paths

---

## 1. Data Model: `verification_log` Table

### Schema

> **Note**: The SQL DDL below is illustrative. The actual table is defined via
> SQLModel + AuditMixin, which automatically adds `created_at`, `updated_at`,
> and `created_by`. The Alembic migration is auto-generated from the model.

```sql
CREATE TABLE verification_log (
    id SERIAL PRIMARY KEY,

    -- What was verified
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
    order_item_id INTEGER REFERENCES order_items(id) ON DELETE SET NULL,
    field_name VARCHAR(50) NOT NULL,         -- 'catalog_number', 'product_name', 'cas_number', 'unit_price', 'storage_temp'
    extracted_value TEXT NOT NULL,            -- value from OCR/extraction

    -- Traceability (denormalized, write-once — assumes scanned images are immutable)
    file_name VARCHAR(255) NOT NULL,         -- documents.file_name (for lookup)
    image_path VARCHAR(1000),                -- full path to original scanned image

    -- Verification result
    verified_value TEXT,                     -- value found on vendor website (NULL if not found)
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
        -- 'pending'     — not yet checked
        -- 'verified'    — extracted matches official source
        -- 'mismatch'    — extracted differs from official source
        -- 'not_found'   — could not find on vendor site
        -- 'needs_human' — agent uncertain, needs human decision

    -- Evidence chain
    vendor_name VARCHAR(255),                -- vendor searched
    source_url TEXT,                         -- product page URL where data was found
    source_snippet TEXT,                     -- relevant text excerpt from source page
    search_queries JSONB,                    -- list of search queries attempted (JSONB for indexability)
    agent_notes TEXT,                        -- agent reasoning for its decision
    confidence FLOAT,                        -- 0.0–1.0, agent self-assessed confidence

    -- Human resolution
    resolved_by VARCHAR(200),
    resolved_at TIMESTAMPTZ,
    resolution VARCHAR(30),                  -- 'accept_extracted', 'accept_verified', 'manual_fix'
    resolution_value TEXT,                   -- final corrected value (for manual_fix)
    resolution_notes TEXT,

    -- Timestamps (provided by AuditMixin: created_at, updated_at, created_by)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100),

    -- Prevent duplicate verification of same field on same document+item
    UNIQUE (document_id, order_item_id, field_name)
);

-- Indexes
CREATE INDEX ix_vlog_document_id ON verification_log(document_id);
CREATE INDEX ix_vlog_status ON verification_log(status);
CREATE INDEX ix_vlog_field_name ON verification_log(field_name);
```

### Constraints

```sql
CHECK (status IN ('pending', 'verified', 'mismatch', 'not_found', 'needs_human'))
CHECK (resolution IS NULL OR resolution IN ('accept_extracted', 'accept_verified', 'manual_fix'))
```

### `order_item_id` Semantics

- For **item-level fields** (catalog_number, product_name, unit_price, lot_number): `order_item_id` points to the specific line item the field belongs to. A document with 3 order items produces 3 separate catalog_number verification rows.
- For **document-level fields** (vendor_name): `order_item_id` is NULL. The field is verified once per document.
- If the document has no order items at all (e.g., standalone COA): all rows have `order_item_id = NULL`.

### SQLModel Definition

New file: `src/lab_manager/models/verification.py`

Python enums (matching existing pattern in `document.py`, `order.py`):
```python
class VerificationStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    mismatch = "mismatch"
    not_found = "not_found"
    needs_human = "needs_human"

class ResolutionAction(str, enum.Enum):
    accept_extracted = "accept_extracted"
    accept_verified = "accept_verified"
    manual_fix = "manual_fix"
```

Extends `AuditMixin`. Fields mirror the SQL schema above. Relationships:
- `document: Document` (via `document_id`, ondelete=RESTRICT)
- `order_item: Optional[OrderItem]` (via `order_item_id`, ondelete=SET NULL)

Unique constraint: `(document_id, order_item_id, field_name)` — CLI uses upsert logic (INSERT ON CONFLICT UPDATE) to allow re-runs without duplicates.

### Migration

New Alembic migration: `add_verification_log` table.

---

## 2. Verification Flow

### Per-Document Steps

```
For each document with extracted_data:
  1. Parse extracted_data JSON → list of verifiable fields
  2. Group fields by vendor+catalog_number (one product page serves multiple fields)
  3. For each unique vendor+catalog:
     a. Search: "{catalog_number}" site:{vendor_domain}
     b. If no results: "{catalog_number} {product_name}" {vendor_name}
     c. If no results: try vendor's own search page
     d. Fetch top result page
     e. Cache page content (same vendor+catalog reuses cache)
  4. For each field:
     a. Extract comparison value from cached page via Gemini
     b. Compare extracted vs. official
     c. Log result to verification_log
```

### Fields to Verify

| Field | Source | Match Logic |
|-------|--------|------------|
| `catalog_number` | Vendor product page | Exact match (normalize whitespace/hyphens) |
| `product_name` | Vendor product page | Fuzzy match via Gemini (abbreviations, synonyms OK) |
| `cas_number` | PubChem API + vendor page | Exact match (format: digits-digits-digit) |
| `unit_price` | Vendor page (if listed) | Numeric tolerance ±5% (prices vary by order size) |
| `storage_temp` | Vendor product page | Semantic match via Gemini ("−20°C" = "Store at -20C") |

### Vendor Domain Mapping

Maintained in a config dict, e.g.:
```python
VENDOR_DOMAINS = {
    "thermo fisher": "thermofisher.com",
    "sigma-aldrich": "sigmaaldrich.com",
    "fisher scientific": "fishersci.com",
    "vwr": "vwr.com",
    "corning": "corning.com",
    "bio-rad": "bio-rad.com",
    ...
}
```

Fuzzy-matched against `documents.vendor_name` using normalized lowercase + alias lookup from `vendors.aliases`.

---

## 3. Agent Decision Rules

### Decision Matrix

| Confidence | Match? | Status |
|-----------|--------|--------|
| ≥ 0.9 | Yes | `verified` (auto-pass) |
| 0.7–0.89 | Yes | `verified` (auto-pass, lower confidence noted) |
| 0.7–0.89 | No | `mismatch` (human review) |
| < 0.7 | Any | `needs_human` (agent uncertain) |
| N/A | Official value found, differs | `mismatch` (human review) |
| N/A | No data found at all | `not_found` (human review) |

### Auto-Verify (status = 'verified')

All conditions must be true:
- Official value found on vendor website
- Extracted value matches official value (per field-specific match logic)
- Agent confidence ≥ 0.7

### Mismatch (status = 'mismatch')

- Official value found but differs from extracted value
- Confidence ≥ 0.7 (agent is confident about the mismatch)
- Always log both values + evidence for human review

### Not Found (status = 'not_found')

- All search strategies exhausted
- No product page found, or page found but field not present
- `search_queries` JSONB records all attempts

### Needs Human (status = 'needs_human')

- Agent confidence < 0.7 (regardless of match/mismatch)
- Ambiguous match (could be correct or wrong)
- Multiple conflicting sources
- Vendor website structure unparseable

### Confidence Scoring

```
1.0  — exact string match on vendor page
0.9  — Gemini says "equivalent" with high confidence
0.7  — partial match or Gemini says "likely equivalent"
0.5  — found on non-official source (auto → needs_human)
0.3  — very ambiguous (auto → needs_human)
0.0  — no data found (auto → not_found)
```

---

## 4. Human Workflow

### Review Queue

Items with `status IN ('mismatch', 'not_found', 'needs_human')` appear in review queue.

Each review item shows:
- Extracted value (from OCR)
- Verified value (from vendor, if found)
- Source URL + snippet (clickable)
- Link to original scanned image (`image_path`)
- Agent notes explaining the situation

### Resolution Actions

| Action | When | Effect |
|--------|------|--------|
| `accept_extracted` | OCR was right, vendor data wrong/outdated | Keep extracted value |
| `accept_verified` | Vendor data is correct, OCR was wrong | Update extracted_data with verified value |
| `manual_fix` | Both wrong, or need different value | Store `resolution_value` as the correct value |

### Resolution Updates DB

When `accept_verified` or `manual_fix`:
1. Update `documents.extracted_data` JSON with corrected value
2. Update corresponding `order_items` / `products` fields
3. Log to `audit_log`

---

## 5. Technical Choices

### Web Search

- Primary: `WebSearch` tool or `googlesearch-python` library
- Fallback: direct vendor search page scraping

### Page Fetching

- `WebFetch` tool or `httpx` with timeout + retry
- Respect robots.txt
- Cache fetched pages in memory (dict keyed by URL)
- Max page size: 500KB text extraction

### LLM for Comparison

- Model: `gemini-2.5-flash` (this is the **API-compatible** name; CLI equivalent is `gemini-3.1-flash-preview`)
- This script uses the Google GenAI Python SDK directly (like `rag.py`), so API names apply
- Used for:
  - Extracting specific field values from product page text
  - Semantic comparison (product names, storage temps)
  - NOT used for: exact string matches (catalog_number, CAS)

### CAS Number Verification

- PubChem REST API: `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/IUPACName,MolecularFormula/JSON`
- Cross-reference CAS from vendor page with PubChem
- No API key required

### Rate Limiting

- 1-second delay between web searches
- 2-second delay between page fetches
- Configurable via CLI flags

### Caching

- Product page cache: `{vendor_domain}:{catalog_number}` → fetched page text
- Avoids re-fetching when verifying multiple fields from same product
- In-memory only (single run)

---

## 6. CLI Interface

### Script: `scripts/verify_documents.py`

```bash
# Verify all documents
uv run python scripts/verify_documents.py

# Verify specific document
uv run python scripts/verify_documents.py --document-id 42

# Verify only unverified items
uv run python scripts/verify_documents.py --status pending

# Dry run (search + compare but don't write to DB)
uv run python scripts/verify_documents.py --dry-run

# Limit to N documents (for testing)
uv run python scripts/verify_documents.py --limit 10

# Verbose output
uv run python scripts/verify_documents.py --verbose
```

### Output

Per-document progress:
```
[2026-03-16 14:30:01] Document 42: packing_list_thermofisher_001.pdf
  catalog_number: 10-500-C → VERIFIED (exact match, thermofisher.com/...)
  product_name: "DMEM High Glucose" → VERIFIED (Gemini: equivalent)
  cas_number: None → SKIPPED (no CAS in extraction)
  unit_price: 45.00 → MISMATCH (vendor: 42.50, diff: 5.9%)
  storage_temp: "2-8°C" → VERIFIED (Gemini: equivalent to "Refrigerated")
```

Summary at end:
```
Verification complete: 215 fields checked
  verified:    142 (66.0%)
  mismatch:     28 (13.0%)
  not_found:    31 (14.4%)
  needs_human:  14 (6.5%)
```

---

## 7. Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `src/lab_manager/models/verification.py` | SQLModel for `verification_log` |
| `alembic/versions/xxxx_add_verification_log.py` | Migration |
| `scripts/verify_documents.py` | CLI verification agent |
| `src/lab_manager/services/verification.py` | Core verification logic (search, fetch, compare) |
| `src/lab_manager/api/routes/verification.py` | API endpoints for review queue |
| `tests/test_verification.py` | Unit tests for comparison logic and SQL validation |

### Modified Files

| File | Change |
|------|--------|
| `src/lab_manager/models/__init__.py` | Import `VerificationLog`, `VerificationStatus`, `ResolutionAction` |
| `src/lab_manager/models/document.py` | Add `verification_logs: List["VerificationLog"] = Relationship(back_populates="document")` |
| `src/lab_manager/api/app.py` | Register verification router at `/api/verifications` |
| `src/lab_manager/services/rag.py` | Add `verification_log` to `_ALLOWED_TABLES`, append full DDL to `DB_SCHEMA`, update table list in `NL_TO_SQL_PROMPT` |

---

## 8. API Endpoints (Verification Review)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/verifications/` | List verification items (filterable by status, document_id, field_name) |
| `GET` | `/api/verifications/{id}` | Get single verification item with full evidence |
| `POST` | `/api/verifications/{id}/resolve` | Human resolution (accept_extracted / accept_verified / manual_fix) |
| `GET` | `/api/verifications/stats` | Summary counts by status |
| `POST` | `/api/verifications/run` | Trigger verification for specific document(s) — **async**: returns job_id, runs in background via `asyncio.create_task`. For single doc (`?document_id=42`) runs synchronously. |

---

## 9. Execution Order

1. **Layer 1: Data model** — `verification.py` model + migration (no dependencies)
2. **Layer 2: Core logic** — `services/verification.py` (search, fetch, compare functions)
3. **Layer 3: CLI** — `scripts/verify_documents.py` (uses Layer 2)
4. **Layer 4: API** — `routes/verification.py` (review queue endpoints)
5. **Layer 5: Integration** — update RAG schema, register router, tests

Layers 1-2 can be one PR. Layer 3 as second PR. Layers 4-5 as third PR.
