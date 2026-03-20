# Lab Manager — Traceability Matrix

Every feature traces from product requirement → page spec → acceptance criteria → test → code.

Nothing exists alone. If code has no spec, it's unplanned. If a spec has no test, it's unverified.

Last updated: 2026-03-19

---

## Document Hierarchy

```
docs/PRODUCT.md          WHY    — Vision, users, principles, non-goals
    ↓
docs/PAGES.md            WHAT   — 12 pages, user stories, API consumed per page
    ↓
docs/COVERAGE.md         WHERE  — 86 endpoints, wired status, priority queue (P0-P3)
    ↓
docs/specs/*.md          HOW    — Per-page: API contract, components, data flow, acceptance criteria
    ↓
web/src/__tests__/*.test.tsx  VERIFY — Tests mapped to acceptance criteria IDs
    ↓
web/src/pages/*.tsx      CODE   — Implementation that satisfies the spec
```

**Rule**: Work flows top-down. Spec before code. Test before (or with) implementation.

---

## Priority Execution Order

### P0 — Broken (must fix before anything else)

| ID | Feature | Spec | Acceptance Criteria | Test File | Status |
|----|---------|------|--------------------:|-----------|--------|
| P0-1 | Review approve/reject | [review.md](specs/review.md) | 10 criteria | `review.test.tsx` | **not started** |
| P0-2 | Search wiring | [search.md](specs/search.md) | 6 criteria | `search.test.tsx` | **not started** |

### P1 — Core actions (existing pages, unwired)

| ID | Feature | Spec | Acceptance Criteria | Test File | Status |
|----|---------|------|--------------------:|-----------|--------|
| P1-1 | Inventory actions | [inventory.md](specs/inventory.md) | 11 criteria | `inventory.test.tsx` | **not started** |
| P1-2 | Orders create/receive | [orders.md](specs/orders.md) | 9 criteria | `orders.test.tsx` | **not started** |
| P1-3 | Review field editing | [review.md](specs/review.md) | (included in P0-2) | — | **not started** |
| P1-4 | Export CSV (all pages) | multiple specs | 4 criteria | `export.test.tsx` | **not started** |
| P1-5 | Dashboard analytics | [dashboard.md](specs/dashboard.md) | 8 criteria | `dashboard.test.tsx` | **not started** |

### P2 — New pages (API ready, no UI)

| ID | Feature | Spec | Acceptance Criteria | Test File | Status |
|----|---------|------|--------------------:|-----------|--------|
| P2-1 | Products page | [products.md](specs/products.md) | 10 criteria | `products.test.tsx` | **not started** |
| P2-2 | Vendors page | [vendors.md](specs/vendors.md) | 9 criteria | `vendors.test.tsx` | **not started** |
| P2-3 | Settings page | [settings.md](specs/settings.md) | 7 criteria | `settings.test.tsx` | **not started** |

### P3 — Enhanced features

| ID | Feature | Spec | Acceptance Criteria | Test File | Status |
|----|---------|------|--------------------:|-----------|--------|
| P3-1 | Dashboard spending chart | [dashboard.md](specs/dashboard.md) | (included in P1-5) | — | **not started** |
| P3-2 | Alerts widget | — (needs spec) | — | — | **not specced** |
| P3-3 | Search autocomplete | [search.md](specs/search.md) | (included in P0-3) | — | **not started** |
| P3-4 | RAG/Ask interface | — (needs spec) | — | — | **not specced** |

### Done

| ID | Feature | Spec | Status |
|----|---------|------|--------|
| ✓ | Login | [login.md](specs/login.md) | working |
| ✓ | Setup wizard | [setup.md](specs/setup.md) | working |
| ✓ | Documents list | [documents.md](specs/documents.md) | read-only working |
| ✓ | Upload | [upload.md](specs/upload.md) | wired, needs polish |

---

## Implementation Workflow

For each feature (in priority order):

```
1. READ spec           →  docs/specs/{page}.md
2. WRITE test          →  web/src/__tests__/{page}.test.tsx
                          (test each acceptance criterion from spec)
3. RUN test            →  all fail (red)
4. IMPLEMENT code      →  web/src/pages/{page}.tsx + api.ts additions
5. RUN test            →  all pass (green)
6. UPDATE traceability →  mark status in this file
7. COMMIT              →  feat(web): wire {feature} per spec
```

This is BDD: spec defines behavior → test verifies behavior → code implements behavior.

---

## Spec Gaps (need specs before implementation)

| Feature | Why no spec | Blocked by |
|---------|-------------|------------|
| Alerts page | Route exists (`/alerts`), placeholder in App.tsx | Needs full spec: page vs dashboard widget |
| RAG/Ask interface | No design yet | Design + UX decision |
| Audit log viewer | Low priority | Not in current roadmap |
| Equipment page | 5 API endpoints exist, no UI | Product decision: add to nav or not |

---

## API Client Coverage

The `web/src/lib/api.ts` client needs additions for unwired features:

| Module | Existing Methods | Methods Needed |
|--------|-----------------|----------------|
| documents | list, get, reviewQueue, approve, reject, upload | update (PATCH) |
| inventory | list, get, lowStock, expiring | consume, transfer, adjust, dispose, open, history |
| orders | list, get | create, update, items, addItem, receive |
| products | list, get | create, update, delete, inventory, orders |
| vendors | list, get | create, update, delete, products, orders |
| analytics | dashboard, spending | spendingByMonth, topProducts, vendorSummary, inventoryValue |
| search | query, suggest | (check if wired) |
| alerts | list, acknowledge | summary, check, resolve |
| export | — | inventory.csv, orders.csv, products.csv, vendors.csv |
