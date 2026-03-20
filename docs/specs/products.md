# Products — Page Spec

| | |
|---|---|
| **Route** | `/products` |
| **Status** | **NOT built — API exists, no UI** |
| **Priority** | **P2 — new page, full CRUD** |
| **Stitch Screen** | *Not yet created* |

---

## What Needs to Be Done

Build entire page from scratch:
1. Product catalog table with search, filters, pagination
2. Add Product form/modal
3. Edit Product form/modal
4. Product detail view (inventory tab, orders tab, info tab)
5. CSV export

---

## API Contract

### GET /api/v1/products/
List products with filters.
```
Query params:
  page, page_size
  vendor_id (int)
  category (str)
  catalog_number (str)
  search (str): searches name, catalog_number, cas_number
  include_inactive (bool, default false)
  sort_by: name | catalog_number | category | created_at
  sort_dir: asc | desc
```
```json
// Response
{
  "items": [{
    "id": 1,
    "catalog_number": "S7653",
    "name": "Sodium Chloride, ACS Reagent",
    "vendor_id": 3,
    "vendor_name": "Sigma-Aldrich",
    "category": "Chemicals",
    "cas_number": "7647-14-5",
    "storage_temp": "-20°C",
    "unit": "500g",
    "is_hazardous": false,
    "is_controlled": false,
    "is_active": true,
    "min_stock_level": 2.0000,
    "max_stock_level": 10.0000,
    "reorder_quantity": 5.0000,
    "shelf_life_days": 730
  }],
  "total": 150, "page": 1, "page_size": 20, "pages": 8
}
```

### POST /api/v1/products/
Create a product.
```json
// Request
{
  "catalog_number": "S7653",      // unique with vendor_id
  "name": "Sodium Chloride",
  "vendor_id": 3,                 // required, FK
  "category": "Chemicals",
  "cas_number": "7647-14-5",      // validated: ^\d{2,7}-\d{2}-\d$
  "storage_temp": "-20°C",
  "unit": "500g",
  "is_hazardous": false,
  "is_controlled": false,
  "min_stock_level": 2,
  "max_stock_level": 10,
  "reorder_quantity": 5,
  "shelf_life_days": 730,
  "storage_requirements": "Keep dry, sealed container",
  "hazard_info": ""
}
```

### GET /api/v1/products/{id}
Product detail with computed fields.

### PATCH /api/v1/products/{id}
Update product (partial).

### DELETE /api/v1/products/{id}
Soft-delete product. Fails if inventory items reference it (RESTRICT).

### GET /api/v1/products/{id}/inventory
Inventory items for this product.
```json
// Response: paginated InventoryItem[]
```

### GET /api/v1/products/{id}/orders
Order items containing this product.
```json
// Response: paginated OrderItem[]
```

### GET /api/v1/export/products.csv
Download product catalog as CSV.

---

## Component Architecture

```
ProductsPage
├── Header ("Products" + "Add Product" button + "Export CSV" button)
├── FilterBar
│   ├── VendorFilter (dropdown from vendors.list)
│   ├── CategoryFilter (dropdown — values from product data)
│   ├── HazardousToggle (checkbox)
│   ├── ControlledToggle (checkbox)
│   └── SearchInput
├── ProductTable
│   ├── TableHeader (sortable: name, catalog#, vendor, category, stock)
│   ├── ProductRow
│   │   ├── Name + CatalogNumber
│   │   ├── VendorName
│   │   ├── Category badge
│   │   ├── StockLevel indicator (computed from inventory)
│   │   ├── HazardBadge (if hazardous)
│   │   └── ActionMenu (edit, view, delete)
│   └── EmptyRow
├── Pagination
└── ProductDetailDrawer (tabbed)
    ├── InfoTab (all product fields, edit button)
    ├── InventoryTab (list from /products/{id}/inventory)
    └── OrdersTab (list from /products/{id}/orders)

Modals:
├── AddProductModal (full form)
├── EditProductModal (pre-filled form)
└── DeleteConfirmDialog
```

## Data Flow

```typescript
const [page, setPage] = useState(1)
const [filters, setFilters] = useState({
  vendor_id: null, category: null, search: '',
  is_hazardous: null, is_controlled: null
})

const { data } = useQuery({
  queryKey: ['products', page, filters],
  queryFn: () => products.list(page, 20, filters),
})

const createMutation = useMutation({
  mutationFn: products.create,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['products'] }),
})

const updateMutation = useMutation({
  mutationFn: ({ id, body }) => products.update(id, body),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['products'] }),
})

const deleteMutation = useMutation({
  mutationFn: products.delete,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['products'] }),
})
```

### API client additions needed

```typescript
// In api.ts — products module, add:
create: (body: ProductCreate) => post('/products/', body),
update: (id: number, body: ProductUpdate) => patch(`/products/${id}`, body),
delete: (id: number) => del(`/products/${id}`),
inventory: (id: number, page?: number) => get(`/products/${id}/inventory`, { page }),
orders: (id: number, page?: number) => get(`/products/${id}/orders`, { page }),
```

---

## User Interactions

| Action | Behavior |
|--------|----------|
| Click "Add Product" | Open AddProductModal |
| Submit add form | POST /products/ → refresh table |
| Click product row | Open ProductDetailDrawer |
| Click "Edit" on product | Open EditProductModal |
| Click "Delete" on product | Confirm dialog → DELETE /products/{id} |
| Change filter/search | Update query, reset to page 1 |
| Click column header | Sort by that column |
| Click "Export CSV" | Download products.csv |
| Click Inventory tab in drawer | Load /products/{id}/inventory |
| Click Orders tab in drawer | Load /products/{id}/orders |

---

## UI States

| State | Condition | Display |
|-------|-----------|---------|
| Loading | Fetching | Skeleton table |
| Populated | Products exist | Full table with filters |
| Empty | No products | "No products yet" + add button |
| Filtered-empty | Filters return 0 | "No products match" + clear filters |
| Creating | Add modal open | Form with vendor dropdown |
| Editing | Edit modal open | Pre-filled form |
| Deleting | Delete confirm | Confirmation dialog |

---

## Validation Rules

- `catalog_number` + `vendor_id` must be unique (409 Conflict from API)
- `cas_number` format: `^\d{2,7}-\d{2}-\d$` (e.g., "7647-14-5")
- `min_stock_level`, `max_stock_level`, `reorder_quantity` ≥ 0
- `shelf_life_days` ≥ 0
- `vendor_id` must reference existing vendor

---

## Acceptance Criteria

- [ ] Products table loads with pagination
- [ ] Filter by vendor, category, hazardous, controlled, search
- [ ] "Add Product" creates product with all required fields
- [ ] CAS number validated client-side before submit
- [ ] Duplicate catalog#/vendor shows error from API
- [ ] Product detail drawer shows info, inventory, and orders tabs
- [ ] Edit product updates fields via PATCH
- [ ] Delete product with confirmation (shows error if inventory exists)
- [ ] Export CSV downloads file
- [ ] Sort by column headers
