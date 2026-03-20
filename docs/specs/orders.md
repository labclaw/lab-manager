# Orders — Page Spec

| | |
|---|---|
| **Route** | `/orders` |
| **Status** | Built — **list only, create/receive NOT wired** |
| **Priority** | **P1 — wire create order, receive shipment** |
| **Stitch Screen** | `Orders Tracking (Dark)` |

---

## What Needs to Be Done

1. Wire "New Requisition" button → create order flow
2. Wire order detail view → `GET /orders/{id}` + `GET /orders/{id}/items`
3. Wire "Receive Shipment" action → `POST /orders/{id}/receive`
4. Wire CSV export → `GET /export/orders.csv`
5. Compute real stats (spending, delivery rate, in-transit) from API data

---

## API Contract

### GET /api/v1/orders/
List orders with filters.
```
Query params:
  page, page_size
  vendor_id (int)
  status: pending | shipped | received | cancelled | deleted
  po_number (str)
  date_from, date_to (date)
  received_by (str)
  sort_by: order_date | status | total_amount | po_number
  sort_dir: asc | desc
```
```json
// Response
{
  "items": [{
    "id": 1,
    "po_number": "PO-2026-001",
    "vendor_id": 3,
    "vendor_name": "Sigma-Aldrich",
    "order_date": "2026-03-10",
    "ship_date": "2026-03-12",
    "received_date": null,
    "status": "shipped",
    "total_amount": 1250.00,
    "item_count": 5,
    "document_id": 42
  }],
  "total": 50, "page": 1, "page_size": 20, "pages": 3
}
```

### POST /api/v1/orders/
Create a new order.
```json
// Request
{
  "po_number": "PO-2026-002",
  "vendor_id": 3,
  "order_date": "2026-03-19",
  "status": "pending",
  "notes": "Rush order for lab experiment"
}
```
```json
// Response (201) — may include duplicate warning
{
  "id": 51,
  "po_number": "PO-2026-002",
  "vendor_id": 3,
  "status": "pending",
  "_duplicate_warning": {  // only if duplicate PO# found
    "message": "Duplicate PO number found",
    "existing_orders": [{ "id": 10, "status": "received" }]
  }
}
```

### GET /api/v1/orders/{id}
Order details.

### GET /api/v1/orders/{id}/items
Order line items.
```json
// Response
{
  "items": [{
    "id": 1,
    "catalog_number": "S1234",
    "description": "Sodium Chloride 500g",
    "quantity": 5.0000,
    "unit": "ea",
    "unit_price": 45.0000,
    "lot_number": "LOT-ABC",
    "product_id": 12
  }],
  "total": 5, "page": 1, "page_size": 20, "pages": 1
}
```

### POST /api/v1/orders/{id}/items
Add item to order.
```json
// Request
{
  "catalog_number": "S1234",
  "description": "Sodium Chloride 500g",
  "quantity": 5,
  "unit": "ea",
  "unit_price": 45.00,
  "product_id": 12
}
```

### POST /api/v1/orders/{id}/receive
Receive a shipment — creates inventory records.
```json
// Request
{
  "items": [
    {
      "order_item_id": 1,
      "product_id": 12,
      "quantity": 5,
      "lot_number": "LOT-ABC",
      "unit": "ea",
      "expiry_date": "2027-12-31"
    }
  ],
  "location_id": 2,
  "received_by": "admin"
}
```
```json
// Response (201): InventoryItem[] created
```

### GET /api/v1/export/orders.csv
Download orders as CSV.
```
Query: ?vendor_id=3&date_from=2026-01-01&date_to=2026-03-19
```

---

## Component Architecture

```
OrdersPage
├── Header ("Orders" + "New Requisition" button)
├── TabBar (Active | Past | Drafts)
├── FeaturedOrderCard (first shipped/ordered — full progress tracker)
│   └── ProgressTracker (Ordered → Shipped → Out for Delivery → Received)
├── OrderCardsGrid
│   └── OrderCard (PO#, vendor, date, status badge, progress bar)
├── StatsCards (Monthly Spend, Delivery Success, Items in Transit)
├── ExportCSVButton
└── Pagination

Modals/Drawers:
├── CreateOrderModal
│   ├── VendorSelect (searchable dropdown)
│   ├── PONumberInput
│   ├── OrderDatePicker
│   └── DuplicateWarning (shown if API returns _duplicate_warning)
├── OrderDetailDrawer
│   ├── OrderInfo (PO#, vendor, dates, status)
│   ├── ItemsTable (line items with add/edit/remove)
│   └── ReceiveButton
└── ReceiveShipmentModal
    ├── ItemsList (pre-filled from order items)
    ├── LotNumberInputs (per item)
    ├── ExpiryDateInputs (per item)
    ├── LocationSelect
    └── ReceivedByInput
```

## Data Flow

```typescript
const [activeTab, setActiveTab] = useState<'active' | 'past' | 'drafts'>('active')
const [page, setPage] = useState(1)

const { data } = useQuery({
  queryKey: ['orders', page, activeTab],
  queryFn: () => orders.list(page, 20),
})

// Client-side tab filtering
const filtered = data?.items.filter(o => {
  if (activeTab === 'active') return !['received', 'cancelled'].includes(o.status)
  if (activeTab === 'past') return ['received', 'cancelled'].includes(o.status)
  return false // drafts: future feature
})

// Mutations
const createMutation = useMutation({
  mutationFn: orders.create,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['orders'] }),
})

const receiveMutation = useMutation({
  mutationFn: ({ id, body }) => orders.receive(id, body),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['orders'] })
    queryClient.invalidateQueries({ queryKey: ['inventory'] })
  },
})
```

### API client additions needed

```typescript
// In api.ts — orders module, add:
create: (body: OrderCreate) => post('/orders/', body),
update: (id: number, body: OrderUpdate) => patch(`/orders/${id}`, body),
items: (id: number, page?: number) => get(`/orders/${id}/items`, { page }),
addItem: (id: number, body: OrderItemCreate) => post(`/orders/${id}/items`, body),
receive: (id: number, body: ReceiveBody) => post(`/orders/${id}/receive`, body),
```

---

## User Interactions

| Action | Behavior |
|--------|----------|
| Click "New Requisition" | Open CreateOrderModal |
| Submit create form | POST order → show duplicate warning if applicable → close modal |
| Click order card | Open OrderDetailDrawer with items |
| Click "Receive" on order | Open ReceiveShipmentModal, pre-fill from order items |
| Submit receive | POST receive → creates inventory → toast success |
| Click tab | Filter orders client-side, reset page |
| Click "Export CSV" | Download CSV |
| Click "Track Package" | Future: open tracking URL |

---

## UI States

| State | Condition | Display |
|-------|-----------|---------|
| Loading | Fetching | Skeleton cards |
| Active tab populated | Orders in progress | Featured card + grid |
| Active tab empty | No active orders | "No active orders" message |
| Past tab populated | Completed orders | Order cards without progress tracker |
| Creating | Create modal open | Form with vendor search |
| Receiving | Receive modal open | Pre-filled item list |
| Submitting | Mutation in progress | Button disabled + spinner |

---

## Business Logic Notes

- **Status progress**: pending (0) → ordered (1) → shipped (2) → out_for_delivery (3) → received (4)
- **Receive creates inventory**: Each received item becomes an InventoryItem in the selected location
- **Duplicate PO warning**: Non-blocking — show warning but allow creation
- **Stats cards**: Currently hardcoded ("98.4% delivery", "+12%"). Should compute from real data.

---

## Acceptance Criteria

- [ ] "New Requisition" opens create order form with vendor selector
- [ ] Create order calls POST /orders/ and handles duplicate PO warning
- [ ] Order detail drawer shows order info + line items
- [ ] "Receive Shipment" opens modal pre-filled from order items
- [ ] Receive submits to POST /orders/{id}/receive, creates inventory records
- [ ] Tab filtering works (active/past/drafts)
- [ ] Progress tracker shows correct step based on order status
- [ ] Stats cards compute from real API data (not hardcoded)
- [ ] Export CSV downloads orders
