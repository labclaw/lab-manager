# Vendors — Page Spec

| | |
|---|---|
| **Route** | `/vendors` |
| **Status** | **NOT built — API exists, no UI** |
| **Priority** | **P2 — new page, full CRUD** |
| **Stitch Screen** | *Not yet created* |

---

## What Needs to Be Done

Build entire page from scratch:
1. Vendor directory table/cards with search
2. Add Vendor form/modal
3. Edit Vendor form/modal
4. Vendor detail view (products tab, orders tab, spending tab)
5. CSV export

---

## API Contract

### GET /api/v1/vendors/
List vendors.
```
Query params:
  page, page_size
  name (str): exact match
  search (str): partial match on name
  sort_by: name | created_at
  sort_dir: asc | desc
```
```json
// Response
{
  "items": [{
    "id": 1,
    "name": "Sigma-Aldrich",
    "aliases": ["Sigma", "MilliporeSigma"],
    "website": "https://www.sigmaaldrich.com",
    "phone": "+1-800-325-3010",
    "email": "orders@sigmaaldrich.com",
    "notes": "Primary chemical supplier",
    "created_at": "2026-01-15T10:00:00"
  }],
  "total": 12, "page": 1, "page_size": 20, "pages": 1
}
```

### POST /api/v1/vendors/
Create a vendor.
```json
// Request
{
  "name": "Fisher Scientific",     // unique, required
  "aliases": ["Fisher", "Thermo Fisher"],
  "website": "https://fishersci.com",
  "phone": "+1-800-766-7000",
  "email": "orders@fishersci.com",
  "notes": "Life science reagents"
}
```

### GET /api/v1/vendors/{id}
Vendor details.

### PATCH /api/v1/vendors/{id}
Update vendor (partial).

### DELETE /api/v1/vendors/{id}
Delete vendor. Fails if products or orders reference it (RESTRICT FK).

### GET /api/v1/vendors/{id}/products
Products supplied by this vendor.
```json
// Response: paginated Product[]
```

### GET /api/v1/vendors/{id}/orders
Orders placed with this vendor.
```json
// Response: paginated Order[]
```

### GET /api/v1/analytics/vendors/{id}/summary
Vendor spending and activity summary.
```json
// Response
{
  "vendor_id": 1,
  "vendor_name": "Sigma-Aldrich",
  "total_orders": 25,
  "total_products": 42,
  "total_spent": 15000.00,
  "avg_order_value": 600.00,
  "last_order_date": "2026-03-10"
}
```

### GET /api/v1/export/vendors.csv
Download vendor list as CSV.

---

## Component Architecture

```
VendorsPage
├── Header ("Vendors" + "Add Vendor" button + "Export CSV" button)
├── SearchBar
├── VendorTable (or VendorCards — card layout for smaller lists)
│   ├── VendorRow/Card
│   │   ├── Name + Aliases
│   │   ├── Contact (phone, email, website)
│   │   ├── ProductCount
│   │   ├── OrderCount
│   │   ├── TotalSpent
│   │   └── ActionMenu (edit, view, delete)
│   └── EmptyRow
├── Pagination
└── VendorDetailDrawer (tabbed)
    ├── InfoTab (all vendor fields, edit button)
    ├── ProductsTab (list from /vendors/{id}/products)
    ├── OrdersTab (list from /vendors/{id}/orders)
    └── SpendingTab (summary from /analytics/vendors/{id}/summary)

Modals:
├── AddVendorModal (name, aliases, website, phone, email, notes)
├── EditVendorModal (pre-filled)
└── DeleteConfirmDialog
```

## Data Flow

```typescript
const [page, setPage] = useState(1)
const [search, setSearch] = useState('')

const { data } = useQuery({
  queryKey: ['vendors', page, search],
  queryFn: () => vendors.list(page, 20, { search }),
})

const createMutation = useMutation({
  mutationFn: vendors.create,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['vendors'] }),
})

// Detail queries (loaded when drawer opens)
const { data: vendorProducts } = useQuery({
  queryKey: ['vendor-products', selectedId],
  queryFn: () => vendors.products(selectedId!),
  enabled: !!selectedId,
})

const { data: vendorSummary } = useQuery({
  queryKey: ['vendor-summary', selectedId],
  queryFn: () => analytics.vendorSummary(selectedId!),
  enabled: !!selectedId,
})
```

### API client additions needed

```typescript
// In api.ts — vendors module, add:
create: (body: VendorCreate) => post('/vendors/', body),
update: (id: number, body: VendorUpdate) => patch(`/vendors/${id}`, body),
delete: (id: number) => del(`/vendors/${id}`),
products: (id: number, page?: number) => get(`/vendors/${id}/products`, { page }),
orders: (id: number, page?: number) => get(`/vendors/${id}/orders`, { page }),

// In api.ts — analytics module, add:
vendorSummary: (id: number) => get(`/analytics/vendors/${id}/summary`),
```

---

## User Interactions

| Action | Behavior |
|--------|----------|
| Click "Add Vendor" | Open AddVendorModal |
| Submit add form | POST /vendors/ → refresh list |
| Click vendor row | Open VendorDetailDrawer |
| Click "Edit" | Open EditVendorModal |
| Click "Delete" | Confirm → DELETE (shows error if products/orders exist) |
| Type in search | Debounce 300ms, filter list |
| Click "Export CSV" | Download vendors.csv |
| Click Products tab | Load /vendors/{id}/products |
| Click Orders tab | Load /vendors/{id}/orders |
| Click Spending tab | Load /analytics/vendors/{id}/summary |

---

## UI States

| State | Condition | Display |
|-------|-----------|---------|
| Loading | Fetching | Skeleton table/cards |
| Populated | Vendors exist | Vendor list with search |
| Empty | No vendors | "No vendors yet" + add button |
| Search-empty | Search returns 0 | "No vendors match" + clear |
| Creating | Add modal open | Form |
| Detail open | Drawer visible | Tabbed detail view |

---

## Acceptance Criteria

- [ ] Vendor table/cards load with pagination
- [ ] Search filters vendors by name
- [ ] "Add Vendor" creates vendor with all fields
- [ ] Duplicate name shows error from API (409 Conflict)
- [ ] Vendor detail drawer shows info, products, orders, spending tabs
- [ ] Edit vendor updates fields via PATCH
- [ ] Delete vendor with confirmation (error if FK exists)
- [ ] Export CSV downloads file
- [ ] Aliases displayed as tags/chips
