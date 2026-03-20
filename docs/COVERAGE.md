# Lab Manager — Feature Coverage Matrix

Last updated: 2026-03-20

## API-to-UI Coverage

### Authentication & Setup
| Endpoint | UI | Status |
|----------|-----|--------|
| `POST /api/auth/login` | LoginPage | wired |
| `GET /api/auth/me` | App.tsx | wired |
| `POST /api/auth/logout` | Sidebar | wired |
| `GET /api/setup/status` | App.tsx | wired |
| `POST /api/setup/complete` | SetupPage | wired |
| `GET /api/health` | — | no UI |
| `GET /api/config` | — | no UI |

### Documents (6 endpoints)
| Endpoint | UI | Status |
|----------|-----|--------|
| `POST /api/v1/documents/upload` | UploadPage | **not wired** — form exists but doesn't call API |
| `GET /api/v1/documents/` | DocumentsPage | wired |
| `POST /api/v1/documents/` | — | no UI (manual create) |
| `GET /api/v1/documents/{id}` | ReviewPage | wired |
| `PATCH /api/v1/documents/{id}` | ReviewPage | **not wired** — form exists but doesn't save |
| `POST /api/v1/documents/{id}/review` | ReviewPage | **partially wired** |
| `GET /api/v1/documents/stats` | DashboardPage | wired |

### Vendors (7 endpoints)
| Endpoint | UI | Status |
|----------|-----|--------|
| `GET /api/v1/vendors/` | DashboardPage (list only) | partial |
| `POST /api/v1/vendors/` | — | **no UI** |
| `GET /api/v1/vendors/{id}` | — | **no UI** |
| `PATCH /api/v1/vendors/{id}` | — | **no UI** |
| `DELETE /api/v1/vendors/{id}` | — | **no UI** |
| `GET /api/v1/vendors/{id}/products` | — | **no UI** |
| `GET /api/v1/vendors/{id}/orders` | — | **no UI** |

### Products (7 endpoints)
| Endpoint | UI | Status |
|----------|-----|--------|
| `GET /api/v1/products/` | — | **no UI** |
| `POST /api/v1/products/` | — | **no UI** |
| `GET /api/v1/products/{id}` | — | **no UI** |
| `PATCH /api/v1/products/{id}` | — | **no UI** |
| `DELETE /api/v1/products/{id}` | — | **no UI** |
| `GET /api/v1/products/{id}/inventory` | — | **no UI** |
| `GET /api/v1/products/{id}/orders` | — | **no UI** |

### Orders (11 endpoints)
| Endpoint | UI | Status |
|----------|-----|--------|
| `GET /api/v1/orders/` | OrdersPage | wired |
| `POST /api/v1/orders/` | — | **no UI** (New Requisition button exists, not wired) |
| `GET /api/v1/orders/{id}` | — | **no UI** |
| `PATCH /api/v1/orders/{id}` | — | **no UI** |
| `DELETE /api/v1/orders/{id}` | — | **no UI** |
| `GET /api/v1/orders/{id}/items` | — | **no UI** |
| `POST /api/v1/orders/{id}/items` | — | **no UI** |
| `GET /api/v1/orders/{id}/items/{item_id}` | — | **no UI** |
| `PATCH /api/v1/orders/{id}/items/{item_id}` | — | **no UI** |
| `DELETE /api/v1/orders/{id}/items/{item_id}` | — | **no UI** |
| `POST /api/v1/orders/{id}/receive` | — | **no UI** |

### Inventory (13 endpoints)
| Endpoint | UI | Status |
|----------|-----|--------|
| `GET /api/v1/inventory/` | InventoryPage | wired |
| `POST /api/v1/inventory/` | — | **no UI** |
| `GET /api/v1/inventory/{id}` | — | **no UI** |
| `PATCH /api/v1/inventory/{id}` | — | **no UI** |
| `DELETE /api/v1/inventory/{id}` | — | **no UI** |
| `GET /api/v1/inventory/{id}/history` | — | **no UI** |
| `POST /api/v1/inventory/{id}/consume` | — | **no UI** (button exists, not wired) |
| `POST /api/v1/inventory/{id}/transfer` | — | **no UI** |
| `POST /api/v1/inventory/{id}/adjust` | — | **no UI** |
| `POST /api/v1/inventory/{id}/dispose` | — | **no UI** |
| `POST /api/v1/inventory/{id}/open` | — | **no UI** |
| `GET /api/v1/inventory/low-stock` | DashboardPage | wired |
| `GET /api/v1/inventory/expiring` | DashboardPage | wired |

### Search (2 endpoints)
| Endpoint | UI | Status |
|----------|-----|--------|
| `GET /api/v1/search/?q=` | Header search bar | **not wired** — input exists, no API call |
| `GET /api/v1/search/suggest` | — | **no UI** |

### Ask / RAG (2 endpoints)
| Endpoint | UI | Status |
|----------|-----|--------|
| `GET /api/v1/ask/?q=` | — | **no UI** |
| `POST /api/v1/ask` | — | **no UI** |

### Analytics (10 endpoints)
| Endpoint | UI | Status |
|----------|-----|--------|
| `GET /api/v1/analytics/dashboard` | DashboardPage | wired |
| `GET /api/v1/analytics/spending/by-vendor` | — | **no UI** |
| `GET /api/v1/analytics/spending/by-month` | — | **no UI** |
| `GET /api/v1/analytics/inventory/value` | — | **no UI** |
| `GET /api/v1/analytics/inventory/report` | — | **no UI** |
| `GET /api/v1/analytics/products/top` | DashboardPage | wired |
| `GET /api/v1/analytics/orders/history` | — | **no UI** |
| `GET /api/v1/analytics/staff/activity` | — | **no UI** |
| `GET /api/v1/analytics/vendors/{id}/summary` | — | **no UI** |
| `GET /api/v1/analytics/documents/stats` | — | no UI (dashboard covers partial) |

### Export (4 endpoints)
| Endpoint | UI | Status |
|----------|-----|--------|
| `GET /api/v1/export/inventory.csv` | — | **no UI** (button exists, not wired) |
| `GET /api/v1/export/orders.csv` | — | **no UI** |
| `GET /api/v1/export/products.csv` | — | **no UI** |
| `GET /api/v1/export/vendors.csv` | — | **no UI** |

### Alerts (5 endpoints)
| Endpoint | UI | Status |
|----------|-----|--------|
| `GET /api/v1/alerts/` | App.tsx (badge count) | partial — no full page |
| `GET /api/v1/alerts/summary` | App.tsx (badge count) | partial |
| `POST /api/v1/alerts/check` | — | **no UI** |
| `POST /api/v1/alerts/{id}/acknowledge` | — | **no UI** |
| `POST /api/v1/alerts/{id}/resolve` | — | **no UI** |

### Audit (2 endpoints)
| Endpoint | UI | Status |
|----------|-----|--------|
| `GET /api/v1/audit/` | — | **no UI** |
| `GET /api/v1/audit/{table}/{record_id}` | — | **no UI** |

### Telemetry (3 endpoints)
| Endpoint | UI | Status |
|----------|-----|--------|
| `POST /api/v1/telemetry/event` | — | **no UI** (background tracking) |
| `GET /api/v1/telemetry/dau` | — | **no UI** |
| `GET /api/v1/telemetry/events` | — | **no UI** |

---

## Coverage Summary

| Category | Total Endpoints | Wired | Partial | Not Wired |
|----------|----------------|-------|---------|-----------|
| Auth/Setup | 7 | 5 | 0 | 2 |
| Documents | 7 | 3 | 1 | 3 |
| Vendors | 7 | 0 | 1 | 6 |
| Products | 7 | 0 | 0 | 7 |
| Orders | 11 | 1 | 0 | 10 |
| Inventory | 13 | 3 | 0 | 10 |
| Search | 2 | 0 | 0 | 2 |
| RAG/Ask | 2 | 0 | 0 | 2 |
| Analytics | 10 | 2 | 0 | 8 |
| Export | 4 | 0 | 0 | 4 |
| Alerts | 5 | 0 | 2 | 3 |
| Audit | 2 | 0 | 0 | 2 |
| Telemetry | 3 | 0 | 0 | 3 |
| **TOTAL** | **80** | **14** | **4** | **62** |

**UI coverage: 17.5% wired, 5% partial, 77.5% no UI**

---

## Page Completion Status

| Page | Design | Code | API Wired | Actions Work | Tests |
|------|--------|------|-----------|-------------|-------|
| Dashboard | done | done | partial | read-only | none |
| Documents | done | done | wired | read-only | none |
| Upload | done | done | **not wired** | **broken** | none |
| Review | done | done | **partial** | **partial** | none |
| Inventory | done | done | list only | **read-only** | none |
| Orders | done | done | list only | **read-only** | none |
| Products | **none** | **none** | — | — | — |
| Vendors | **none** | **none** | — | — | — |
| Settings | **none** | **placeholder** | — | — | — |
| Login | done | done | wired | working | none |
| Setup | done | done | wired | working | none |

---

## Priority Queue

### P0 — Broken (must fix)
1. UploadPage: wire file upload to `POST /api/v1/documents/upload`
2. ReviewPage: wire approve/reject to `POST /api/v1/documents/{id}/review`
3. Header: wire search bar to `GET /api/v1/search/`

### P1 — Core actions (existing pages, unwired)
4. InventoryPage: wire consume/transfer/adjust/dispose actions
5. OrdersPage: wire create order, receive shipment
6. ReviewPage: wire field editing to `PATCH /api/v1/documents/{id}`
7. All list pages: wire export CSV buttons

### P2 — New pages (API ready)
8. Products page: full CRUD
9. Vendors page: full CRUD
10. Settings page: lab profile, locations, staff

### P3 — Enhanced features
11. Dashboard: spending chart, full analytics
12. Alerts: fold into dashboard as widget
13. Search: autocomplete suggestions
14. RAG/Ask: natural language query interface
