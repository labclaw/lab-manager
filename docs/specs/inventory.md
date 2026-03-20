# Inventory — Page Spec

| | |
|---|---|
| **Route** | `/inventory` |
| **Status** | Built — **list only, CRUD actions NOT wired** |
| **Priority** | **P1 — wire consume/transfer/adjust/dispose actions** |
| **Stitch Screen** | `Lab Manager — Inventory Management` |

---

## What Needs to Be Done

1. Wire action buttons per row: consume, transfer, adjust, dispose, open
2. Wire item detail drawer/modal with history
3. Wire CSV export button
4. Add filter bar (location, status, category)
5. Wire search to filter API

---

## API Contract

### GET /api/v1/inventory/
List inventory items with filters.
```
Query params:
  page, page_size (pagination)
  product_id (int)
  location_id (int)
  status: available | opened | depleted | disposed | expired
  expiring_before (date)
  search (str)
  sort_by: created_at | quantity_on_hand | expiry_date | status
  sort_dir: asc | desc
```
```json
// Response
{
  "items": [{
    "id": 1,
    "product_id": 5,
    "product_name": "Sodium Chloride",
    "vendor_name": "Sigma-Aldrich",
    "location_id": 2,
    "location_name": "Room 301 Freezer",
    "lot_number": "LOT-2026-001",
    "quantity_on_hand": 4.5000,
    "unit": "kg",
    "expiry_date": "2027-06-01",
    "opened_date": null,
    "status": "available",
    "received_by": "admin"
  }],
  "total": 300, "page": 1, "page_size": 20, "pages": 15
}
```

### POST /api/v1/inventory/{id}/consume
Log consumption of inventory.
```json
// Request
{
  "quantity": 0.5,        // > 0, must not exceed quantity_on_hand
  "consumed_by": "admin",
  "purpose": "Experiment #42"
}
```
```json
// Response: ConsumptionLog entry
```

### POST /api/v1/inventory/{id}/transfer
Move item to different location.
```json
// Request
{ "location_id": 3, "transferred_by": "admin" }
```

### POST /api/v1/inventory/{id}/adjust
Correct quantity (physical count differs from DB).
```json
// Request
{ "new_quantity": 3.0, "reason": "Physical count correction", "adjusted_by": "admin" }
```

### POST /api/v1/inventory/{id}/dispose
Mark item as disposed.
```json
// Request
{ "reason": "Expired", "disposed_by": "admin" }
```

### POST /api/v1/inventory/{id}/open
Mark sealed item as opened (starts shelf-life countdown).
```json
// Request
{ "opened_by": "admin" }
```

### GET /api/v1/inventory/{id}/history
Consumption/action history for an item.
```json
// Response: ConsumptionLog[]
// Each log: { action, quantity, performed_by, purpose, timestamp }
```

### GET /api/v1/export/inventory.csv
Download full inventory as CSV.
```
Query: ?location_id=1 (optional filter)
Response: CSV file download
```

---

## Component Architecture

```
InventoryPage
├── StatsCards (storage %, monthly spend, active orders, audit due)
├── FilterBar
│   ├── LocationFilter (dropdown)
│   ├── StatusFilter (dropdown)
│   └── SearchInput (text)
├── InventoryTable
│   ├── TableHeader (sortable columns)
│   ├── InventoryRow
│   │   ├── ProductName + CatalogNumber
│   │   ├── LotNumber
│   │   ├── VendorName
│   │   ├── LocationBadge
│   │   ├── QuantityBadge (color by stock level)
│   │   ├── ExpiryDate (red if <30 days)
│   │   └── ActionMenu (consume, transfer, adjust, dispose, open, history)
│   └── EmptyRow ("No items match filters")
├── Pagination
├── ExportCSVButton
└── ItemDetailDrawer (opened on row click or "history")
    ├── ItemInfo (all fields)
    └── HistoryTimeline (consumption logs)

Modals:
├── ConsumeModal (quantity input, purpose input)
├── TransferModal (location dropdown)
├── AdjustModal (new quantity, reason)
├── DisposeModal (reason)
└── ConfirmDialog (for dispose action)
```

## Data Flow

```typescript
const [page, setPage] = useState(1)
const [filters, setFilters] = useState({ location_id: null, status: null, search: '' })

const { data } = useQuery({
  queryKey: ['inventory', page, filters],
  queryFn: () => inventory.list(page, 20, filters),
})

// Action mutations
const consumeMutation = useMutation({
  mutationFn: ({ id, body }: { id: number; body: ConsumeBody }) =>
    inventory.consume(id, body),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['inventory'] }),
})
// Similar for transfer, adjust, dispose, open
```

### API client additions needed

```typescript
// In api.ts — inventory module, add:
consume: (id: number, body: ConsumeBody) => post(`/inventory/${id}/consume`, body),
transfer: (id: number, body: TransferBody) => post(`/inventory/${id}/transfer`, body),
adjust: (id: number, body: AdjustBody) => post(`/inventory/${id}/adjust`, body),
dispose: (id: number, body: DisposeBody) => post(`/inventory/${id}/dispose`, body),
open: (id: number, body: OpenBody) => post(`/inventory/${id}/open`, body),
history: (id: number) => get(`/inventory/${id}/history`),
```

---

## User Interactions

| Action | Behavior |
|--------|----------|
| Click "Consume" on row | Open ConsumeModal → enter quantity + purpose → POST consume |
| Click "Transfer" on row | Open TransferModal → select location → POST transfer |
| Click "Adjust" on row | Open AdjustModal → enter new qty + reason → POST adjust |
| Click "Dispose" on row | Open ConfirmDialog → enter reason → POST dispose |
| Click "Open" on row | POST open (mark as opened) |
| Click row | Open ItemDetailDrawer with full info + history |
| Click "Export CSV" | Download CSV via `GET /export/inventory.csv` |
| Change filter | Update query, reset to page 1 |

---

## UI States

| State | Condition | Display |
|-------|-----------|---------|
| Loading | Fetching | Skeleton table |
| Populated | Items exist | Full table with actions |
| Empty | No inventory | "No inventory yet" + link to orders |
| Filtered-empty | Filters return 0 | "No items match" + clear filters |
| Action submitting | Mutation in progress | Modal button disabled + spinner |
| Action success | Mutation complete | Toast notification + table refresh |
| Action error | Mutation failed | Error message in modal |

---

## Acceptance Criteria

- [ ] Inventory table loads from `GET /inventory/` with pagination
- [ ] Filter bar filters by location, status, search
- [ ] "Consume" action opens modal, submits to API, updates table
- [ ] "Transfer" action opens modal with location picker, submits
- [ ] "Adjust" action opens modal with new quantity + reason, submits
- [ ] "Dispose" action confirms, then submits
- [ ] "Open" action marks item as opened
- [ ] Item detail drawer shows full info + consumption history
- [ ] Export CSV downloads file
- [ ] Quantity badge shows red for low stock, green for adequate
- [ ] Expiry date shows red highlight if < 30 days
