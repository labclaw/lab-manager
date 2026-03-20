# Dashboard — Page Spec

| | |
|---|---|
| **Route** | `/` |
| **Status** | Built — needs spec alignment |
| **Priority** | P1 — wire spending chart, full analytics |
| **Stitch Screen** | `Refined Main Dashboard (Standardized)` |

---

## What Needs to Be Done

The dashboard currently shows basic KPIs and lists. It needs:
1. Wire spending-by-month chart to `GET /api/v1/analytics/spending/by-month`
2. Wire top products widget to `GET /api/v1/analytics/products/top`
3. Add alert summary badge from `GET /api/v1/alerts/summary`
4. Add quick action buttons (Upload → `/upload`, New Order → `/orders`)

---

## API Contract

### GET /api/v1/analytics/dashboard
Summary KPI cards.
```json
// Response
{
  "total_documents": 100,
  "documents_approved": 75,
  "documents_pending_review": 20,
  "total_orders": 50,
  "total_inventory_items": 300,
  "total_vendors": 12
}
```

### GET /api/v1/analytics/spending/by-month
Monthly spending chart data.
```
Query: ?months=12 (1-120, default 12)
```
```json
// Response
[{ "month": "2026-01", "total": 12500.00 }, ...]
```

### GET /api/v1/inventory/low-stock
Items below reorder level.
```json
// Response: InventoryItem[] with product details
```

### GET /api/v1/inventory/expiring
Items expiring within N days.
```
Query: ?days=30 (default 30)
```
```json
// Response: InventoryItem[] with expiry_date
```

### GET /api/v1/alerts/summary
Alert badge counts.
```json
// Response
{ "total": 5, "critical": 1, "warning": 3, "info": 1 }
```

### GET /api/v1/analytics/products/top
Most-ordered products.
```
Query: ?limit=10 (1-100)
```
```json
// Response
[{ "product_id": 1, "name": "...", "count": 42 }, ...]
```

---

## Component Architecture

```
DashboardPage
├── KPICards (4 cards: documents, approval rate, vendors, low stock)
├── SpendingChart (line/bar chart, spending by month)
├── AlertsWidget (low stock + expiring items table)
├── RecentDocuments (last 5 documents, link to /documents)
├── TopProducts (top 5 products by order count)
└── QuickActions (Upload button → /upload, New Order → /orders)
```

## Data Flow

```typescript
// TanStack Query hooks
const { data: stats } = useQuery({ queryKey: ['dashboard'], queryFn: analytics.dashboard })
const { data: spending } = useQuery({ queryKey: ['spending'], queryFn: () => analytics.spendingByMonth(12) })
const { data: lowStock } = useQuery({ queryKey: ['low-stock'], queryFn: inventory.lowStock })
const { data: expiring } = useQuery({ queryKey: ['expiring'], queryFn: () => inventory.expiring(30) })
const { data: alerts } = useQuery({ queryKey: ['alerts-summary'], queryFn: alerts.summary })
const { data: topProducts } = useQuery({ queryKey: ['top-products'], queryFn: () => analytics.topProducts(10) })
```

---

## User Interactions

| Action | Behavior |
|--------|----------|
| Click KPI card | Navigate to relevant page (/documents, /inventory, /vendors) |
| Click low-stock item | Navigate to `/inventory` filtered by item |
| Click "Upload" quick action | Navigate to `/upload` |
| Click "New Order" quick action | Navigate to `/orders` (future: open create modal) |
| Click document in recent list | Navigate to `/review` or `/documents/{id}` |

---

## UI States

| State | Condition | Display |
|-------|-----------|---------|
| Loading | Initial fetch | Skeleton cards + skeleton table |
| Populated | Data loaded | Full dashboard |
| Empty | Fresh install (0 records) | Welcome message + setup prompts |
| Partial error | One query fails | Show available data, error badge on failed widget |

---

## Acceptance Criteria

- [ ] KPI cards show real data from `/analytics/dashboard`
- [ ] Spending chart renders 12-month trend from `/analytics/spending/by-month`
- [ ] Low stock table shows items from `/inventory/low-stock`
- [ ] Expiring items table shows items from `/inventory/expiring`
- [ ] Alert badge in header shows count from `/alerts/summary`
- [ ] Quick action buttons navigate to correct routes
- [ ] Loading state shows skeleton for each widget independently
- [ ] Empty state shows onboarding message when no data exists
