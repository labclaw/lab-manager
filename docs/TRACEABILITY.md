# Lab Manager — Traceability Matrix

Every feature traces **both directions**: spec → code AND code → spec.
Nothing exists alone. If code has no spec, it's undocumented. If a spec has no test, it's unverified.

Last updated: 2026-03-19

---

## Document Hierarchy

```
docs/PRODUCT.md              WHY    — Vision, users, principles, non-goals
    ↓
docs/PAGES.md                WHAT   — 12 pages, user stories, API consumed per page
    ↓
docs/COVERAGE.md             WHERE  — 86 endpoints, wired status, priority queue (P0-P3)
    ↓
docs/specs/*.md              HOW    — Per-page: API contract, components, data flow, acceptance criteria
    ↓
web/src/__tests__/*.test.tsx  VERIFY — Tests mapped to acceptance criteria IDs
    ↓
web/src/pages/*.tsx          CODE   — Implementation that satisfies the spec
```

**Rule**: Work flows top-down. Spec before code. Test before (or with) implementation.

---

## Top-Down: Spec → Code Coverage

Every spec file and what code implements it.

| Spec | Page File | Route | Code Status | Acceptance Criteria Met |
|------|-----------|-------|-------------|------------------------|
| [dashboard.md](specs/dashboard.md) | DashboardPage.tsx | `/` | built, partial wiring | 1/8 (12%) |
| [documents.md](specs/documents.md) | DocumentsPage.tsx | `/documents` | built, read-only | 4/6 (67%) |
| [upload.md](specs/upload.md) | UploadPage.tsx | `/upload` | built, wired | 7/10 (70%) |
| [review.md](specs/review.md) | ReviewPage.tsx | `/review` | built, partial | 2/10 (20%) — **BUG: wrong endpoints** |
| [inventory.md](specs/inventory.md) | InventoryPage.tsx | `/inventory` | built, list only | 2/11 (18%) |
| [orders.md](specs/orders.md) | OrdersPage.tsx | `/orders` | built, list only | 1/9 (11%) |
| [products.md](specs/products.md) | — | `/products` | **NOT BUILT** | 0/10 (0%) |
| [vendors.md](specs/vendors.md) | — | `/vendors` | **NOT BUILT** | 0/9 (0%) |
| [settings.md](specs/settings.md) | inline App.tsx | `/settings` | placeholder | 0/7 (0%) |
| [alerts.md](specs/alerts.md) | inline App.tsx | `/alerts` | placeholder | 0/9 (0%) |
| [login.md](specs/login.md) | LoginPage.tsx | `/login` (guard) | built, working | 4/4 (100%) |
| [setup.md](specs/setup.md) | SetupPage.tsx | `/setup` (guard) | built, working | 4/4 (100%) |
| [search.md](specs/search.md) | Header.tsx | (global) | input exists, not wired | 0/6 (0%) |
| [components.md](specs/components.md) | components/*/*.tsx | (shared) | 6 built, 2 unused | — |

---

## Bottom-Up: Code → Spec Coverage

Every code file and what spec documents it.

### Pages (`web/src/pages/`)

| Code File | Spec | Documented? |
|-----------|------|-------------|
| DashboardPage.tsx | [dashboard.md](specs/dashboard.md) | yes |
| DocumentsPage.tsx | [documents.md](specs/documents.md) | yes |
| UploadPage.tsx | [upload.md](specs/upload.md) | yes |
| ReviewPage.tsx | [review.md](specs/review.md) | yes |
| InventoryPage.tsx | [inventory.md](specs/inventory.md) | yes |
| OrdersPage.tsx | [orders.md](specs/orders.md) | yes |
| LoginPage.tsx | [login.md](specs/login.md) | yes |
| SetupPage.tsx | [setup.md](specs/setup.md) | yes |

### Inline Pages (`App.tsx`)

| Code | Spec | Documented? |
|------|------|-------------|
| AlertsPage() | [alerts.md](specs/alerts.md) | yes |
| SettingsPage() | [settings.md](specs/settings.md) | yes |

### Components (`web/src/components/`)

| Code File | Spec | Documented? |
|-----------|------|-------------|
| layout/Header.tsx | [components.md](specs/components.md) | yes |
| layout/Sidebar.tsx | [components.md](specs/components.md) | yes |
| ui/ConfidenceBadge.tsx | [components.md](specs/components.md) | yes |
| ui/EmptyState.tsx | [components.md](specs/components.md) | yes |
| ui/ErrorBanner.tsx | [components.md](specs/components.md) | yes |
| ui/SkeletonTable.tsx | [components.md](specs/components.md) | yes |

### API Client (`web/src/lib/api.ts`)

| Module | Methods | Spec Coverage | Documented? |
|--------|---------|---------------|-------------|
| auth | login, me, logout | [login.md](specs/login.md) | yes |
| setup | status, complete | [setup.md](specs/setup.md) | yes |
| analytics | dashboard, spending | [dashboard.md](specs/dashboard.md) | yes |
| vendors | list, get | [vendors.md](specs/vendors.md) | yes |
| products | list, get | [products.md](specs/products.md) | yes |
| orders | list, get | [orders.md](specs/orders.md) | yes |
| inventory | list, get, lowStock, expiring | [inventory.md](specs/inventory.md) | yes |
| documents | list, get, reviewQueue, approve, reject, upload | [review.md](specs/review.md), [upload.md](specs/upload.md) | yes |
| search | query, suggest | [search.md](specs/search.md) | yes |
| alerts | list, acknowledge | [alerts.md](specs/alerts.md) | yes |

### Backend Routes (not in docs scope but cross-referenced)

| Route Module | Endpoints | COVERAGE.md? | Page Spec? |
|-------------|-----------|-------------|------------|
| vendors.py | 7 | yes | [vendors.md](specs/vendors.md) |
| products.py | 7 | yes | [products.md](specs/products.md) |
| orders.py | 11 | yes | [orders.md](specs/orders.md) |
| inventory.py | 13 | yes | [inventory.md](specs/inventory.md) |
| documents.py | 8 | yes | [documents.md](specs/documents.md), [upload.md](specs/upload.md), [review.md](specs/review.md) |
| equipment.py | 5 | yes | — (no page, future decision) |
| search.py | 2 | yes | [search.md](specs/search.md) |
| ask.py | 2 | yes | — (no page, needs spec) |
| analytics.py | 10 | yes | [dashboard.md](specs/dashboard.md) |
| export.py | 4 | yes | multiple page specs |
| alerts.py | 5 | yes | [alerts.md](specs/alerts.md) |
| audit.py | 2 | yes | — (no page, low priority) |
| telemetry.py | 3 | yes | — (background, no UI needed) |

---

## Known Bugs (spec ≠ code)

| ID | Location | Issue | Severity |
|----|----------|-------|----------|
| BUG-1 | ReviewPage.tsx / api.ts | Frontend calls `POST /documents/{id}/approve` and `/reject` but backend only has `POST /documents/{id}/review` with `action` param | **P0** |
| BUG-2 | Header.tsx | Search input exists, `onSearch` prop received, but never calls `search.query()` from api.ts | **P0** |
| BUG-3 | api.ts documents.approve/reject | Wrong endpoint paths — backend has single `/review` endpoint, not separate `/approve` `/reject` | **P0** (same root as BUG-1) |

---

## Priority Execution Order

### P0 — Broken (must fix before anything else)

| ID | Feature | Spec | Bugs | Test File | Status |
|----|---------|------|------|-----------|--------|
| P0-1 | Review approve/reject | [review.md](specs/review.md) | BUG-1, BUG-3 | `review.test.tsx` | **not started** |
| P0-2 | Search wiring | [search.md](specs/search.md) | BUG-2 | `search.test.tsx` | **not started** |

### P1 — Core actions (existing pages, unwired)

| ID | Feature | Spec | Test File | Status |
|----|---------|------|-----------|--------|
| P1-1 | Inventory actions | [inventory.md](specs/inventory.md) | `inventory.test.tsx` | **not started** |
| P1-2 | Orders create/receive | [orders.md](specs/orders.md) | `orders.test.tsx` | **not started** |
| P1-3 | Review field editing | [review.md](specs/review.md) | — | **not started** |
| P1-4 | Export CSV (all pages) | multiple specs | `export.test.tsx` | **not started** |
| P1-5 | Dashboard analytics | [dashboard.md](specs/dashboard.md) | `dashboard.test.tsx` | **not started** |

### P2 — New pages (API ready, no UI)

| ID | Feature | Spec | Test File | Status |
|----|---------|------|-----------|--------|
| P2-1 | Products page | [products.md](specs/products.md) | `products.test.tsx` | **not started** |
| P2-2 | Vendors page | [vendors.md](specs/vendors.md) | `vendors.test.tsx` | **not started** |
| P2-3 | Settings page | [settings.md](specs/settings.md) | `settings.test.tsx` | **not started** |
| P2-4 | Alerts page | [alerts.md](specs/alerts.md) | `alerts.test.tsx` | **not started** |

### P3 — Enhanced features

| ID | Feature | Spec | Status |
|----|---------|------|--------|
| P3-1 | Dashboard spending chart | [dashboard.md](specs/dashboard.md) | **not started** |
| P3-2 | Search autocomplete | [search.md](specs/search.md) | **not started** |
| P3-3 | RAG/Ask interface | — (needs spec) | **not specced** |

### Done

| ID | Feature | Spec | Status |
|----|---------|------|--------|
| done | Login | [login.md](specs/login.md) | working, 100% criteria |
| done | Setup wizard | [setup.md](specs/setup.md) | working, 100% criteria |
| done | Documents list | [documents.md](specs/documents.md) | read-only, 67% criteria |
| done | Upload | [upload.md](specs/upload.md) | wired, 70% criteria |

---

## Implementation Workflow

For each feature (in priority order):

```
1. READ spec           →  docs/specs/{page}.md
2. CHECK bugs          →  Known Bugs table above
3. WRITE test          →  web/src/__tests__/{page}.test.tsx
                          (test each acceptance criterion from spec)
4. RUN test            →  all fail (red)
5. IMPLEMENT code      →  web/src/pages/{page}.tsx + api.ts additions
6. RUN test            →  all pass (green)
7. UPDATE traceability →  mark status in this file
8. COMMIT              →  feat(web): wire {feature} per spec
```

---

## Spec Gaps (need specs before implementation)

| Feature | Code Exists? | API Exists? | Blocked by |
|---------|-------------|-------------|------------|
| RAG/Ask interface | no | yes (2 endpoints) | Design + UX decision |
| Audit log viewer | no | yes (2 endpoints) | Low priority |
| Equipment page | no | yes (5 endpoints) | Product decision: add to nav? |
| Telemetry dashboard | no | yes (3 endpoints) | Internal tool, not user-facing |

---

## API Client Coverage

Methods in `web/src/lib/api.ts` — what exists vs what's needed.

| Module | Existing Methods | Methods Needed | Spec |
|--------|-----------------|----------------|------|
| documents | list, get, reviewQueue, approve, reject, upload | **fix approve/reject → review(id, action)**, add update (PATCH) | review.md |
| inventory | list, get, lowStock, expiring | consume, transfer, adjust, dispose, open, history | inventory.md |
| orders | list, get | create, update, items, addItem, receive | orders.md |
| products | list, get | create, update, delete, inventory, orders | products.md |
| vendors | list, get | create, update, delete, products, orders | vendors.md |
| analytics | dashboard, spending | spendingByMonth, topProducts, vendorSummary, inventoryValue | dashboard.md |
| search | query, suggest | (exists, needs wiring in Header) | search.md |
| alerts | list, acknowledge | summary, check, resolve | alerts.md |
| export | — | inventory.csv, orders.csv, products.csv, vendors.csv | multiple |
