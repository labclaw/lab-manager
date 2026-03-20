# Lab Manager — Page Architecture

Master registry of all pages. **If a page isn't here, it doesn't exist.**

Last updated: 2026-03-20

## Navigation Structure

### Current Sidebar (implemented)
```
───────────────────────
  Lab Manager
  Laboratory
───────────────────────
  Dashboard          /
  Documents          /documents
  Review Queue       /review
  Inventory          /inventory
  Orders             /orders
  Upload             /upload
───────────────────────
  Admin
  Sign Out
───────────────────────
```

### Target Sidebar (planned)
```
───────────────────────
  Lab Manager
  Laboratory
───────────────────────
  Dashboard          /
  ─────────────────────
  Documents          /documents
  Upload             /upload
  Review Queue       /review         (badge: pending count)
  ─────────────────────
  Inventory          /inventory
  Orders             /orders
  ─────────────────────
  Products           /products        ← not built
  Vendors            /vendors         ← not built
  ─────────────────────
  Settings           /settings        ← placeholder
───────────────────────
  [User Name]
  Sign Out
───────────────────────
```

### Auth Guards (not in sidebar — conditional renders before router)
- `/login` — shown when not authenticated
- `/setup` — shown when `needs_setup=true`

---

## Page Registry

### 1. Dashboard

| | |
|---|---|
| **Route** | `/` |
| **Purpose** | Single-glance lab health: KPIs, alerts, recent activity, spending |
| **Stitch Screen** | `Refined Main Dashboard (Standardized)` |
| **Spec** | `docs/specs/dashboard.md` |
| **Status** | Built — needs spec alignment |

**User Stories:**
- As a lab manager, I see total documents processed, approval rate, and pending reviews
- As a PI, I see monthly spending trends and low-stock alerts
- As anyone, I see recent activity and can navigate to key actions

**API Endpoints (currently wired):**
- `GET /api/v1/analytics/dashboard` — summary KPIs
- `GET /api/v1/inventory/low-stock` — low stock alerts
- `GET /api/v1/inventory/expiring` — expiring items
- `GET /api/v1/vendors/` — vendor data for charts
- `GET /api/v1/documents/` — document type distribution

**API Endpoints (planned, not yet wired):**
- `GET /api/v1/analytics/spending/by-month` — spending chart
- `GET /api/v1/alerts/summary` — alert badge counts
- `GET /api/v1/analytics/products/top` — top products

**Key Components:**
- KPI cards (documents, approval rate, vendors, low stock)
- Spending trend chart (by month)
- Low stock / expiring alerts table
- Recent documents list
- Quick action buttons (Upload, New Order)

**States:** Loading skeleton, Populated, Empty (fresh install)

---

### 2. Documents

| | |
|---|---|
| **Route** | `/documents` |
| **Purpose** | Browse all uploaded documents with status, search, and filtering |
| **Stitch Screen** | `Documents Management` |
| **Spec** | `docs/specs/documents.md` |
| **Status** | Built — needs spec alignment |

**User Stories:**
- As a lab manager, I browse all documents filtered by status (pending/approved/rejected)
- As a lab manager, I search documents by vendor name or file name
- As a lab manager, I click a document to see extraction details

**API Endpoints:**
- `GET /api/v1/documents/` — list with filters (status, document_type, vendor_name, search)
- `GET /api/v1/documents/{id}` — document details
- `GET /api/v1/documents/stats` — processing statistics

**Key Components:**
- Status filter tabs (All / Approved / Needs Review / Rejected)
- Document table (file name, vendor, type, confidence, status, date)
- Search bar
- Pagination

**States:** Loading, Populated, Empty, Filtered-empty

---

### 3. Upload

| | |
|---|---|
| **Route** | `/upload` |
| **Purpose** | Drag-and-drop document intake for invoices, COAs, packing lists |
| **Stitch Screen** | `Document Upload — Lab Manager` |
| **Spec** | `docs/specs/upload.md` |
| **Status** | Built — upload wired to API |

**User Stories:**
- As a lab manager, I drag-and-drop or click to upload document images/PDFs
- As a lab manager, I see upload progress and processing status
- As a lab manager, I'm redirected to review queue after upload

**API Endpoints:**
- `POST /api/v1/documents/upload` — upload file (image/PDF, <50MB)

**Key Components:**
- Drag-and-drop zone (accepts image/*, application/pdf)
- File list with upload progress
- Processing status indicators
- "Go to Review" CTA after upload

**States:** Empty (drop zone), Uploading, Processing, Complete, Error (bad file type/size)

---

### 4. Review Queue

| | |
|---|---|
| **Route** | `/review` |
| **Purpose** | Human-in-the-loop verification of AI-extracted data |
| **Stitch Screen** | `Refined Review Queue (Standardized)` |
| **Spec** | `docs/specs/review.md` |
| **Status** | Built — approve/reject partially wired |

**User Stories:**
- As a lab manager, I see all documents pending review in a queue
- As a lab manager, I view original document alongside extracted fields
- As a lab manager, I edit extracted fields (vendor, items, quantities, lot numbers)
- As a lab manager, I approve (creates order + inventory) or reject with reason

**API Endpoints:**
- `GET /api/v1/documents/?status=needs_review` — review queue
- `GET /api/v1/documents/{id}` — document details with extracted_data
- `POST /api/v1/documents/{id}/review` — approve or reject
- `PATCH /api/v1/documents/{id}` — update extracted fields

**Key Components:**
- Document queue list (left panel)
- Document preview (center — image/PDF viewer)
- Extracted data form (right panel — editable fields)
- Approve / Reject buttons with keyboard shortcuts
- Confidence indicators per field
- Line items table (editable)

**States:** Loading, Queue populated, Queue empty, Reviewing (split view), Submitting

---

### 5. Inventory

| | |
|---|---|
| **Route** | `/inventory` |
| **Purpose** | Browse, search, and manage lab inventory items |
| **Stitch Screen** | `Lab Manager — Inventory Management` |
| **Spec** | `docs/specs/inventory.md` |
| **Status** | Built — CRUD actions not wired |

**User Stories:**
- As a researcher, I search for an item to check if it's in stock
- As a lab manager, I see all items with stock level, location, and expiry
- As a lab manager, I consume, transfer, adjust, or dispose items
- As a lab manager, I filter by location, status, or low-stock
- As a lab manager, I export inventory to CSV

**API Endpoints:**
- `GET /api/v1/inventory/` — list with filters (product_id, location_id, status, search)
- `GET /api/v1/inventory/{id}` — item details
- `POST /api/v1/inventory/{id}/consume` — log consumption
- `POST /api/v1/inventory/{id}/transfer` — move to location
- `POST /api/v1/inventory/{id}/adjust` — adjust quantity
- `POST /api/v1/inventory/{id}/dispose` — mark disposed
- `POST /api/v1/inventory/{id}/open` — mark opened
- `GET /api/v1/inventory/{id}/history` — consumption log
- `GET /api/v1/inventory/low-stock` — low stock items
- `GET /api/v1/inventory/expiring` — expiring items
- `GET /api/v1/export/inventory.csv` — CSV export

**Key Components:**
- Inventory table (item name, lot #, vendor, location, stock badge, actions)
- Filter bar (location, status, category)
- Search
- Action buttons per row (consume, transfer, adjust, dispose)
- Item detail drawer/modal (full history)
- Stats cards (storage %, monthly spend, active orders, audit due)
- Pagination
- Export CSV button

**States:** Loading, Populated, Empty, Filtered-empty

---

### 6. Orders

| | |
|---|---|
| **Route** | `/orders` |
| **Purpose** | Full procurement lifecycle: draft → order → ship → receive |
| **Stitch Screen** | `Orders Tracking (Dark)` |
| **Spec** | `docs/specs/orders.md` |
| **Status** | Built — CRUD actions not wired |

**User Stories:**
- As a lab manager, I see active orders with tracking progress
- As a lab manager, I create a new order (select vendor, add items)
- As a lab manager, I receive a shipment (creates inventory records)
- As a lab manager, I filter by active/past/drafts
- As a lab manager, I export orders to CSV

**API Endpoints:**
- `GET /api/v1/orders/` — list with filters (vendor_id, status, po_number, date range)
- `POST /api/v1/orders/` — create order
- `GET /api/v1/orders/{id}` — order details
- `PATCH /api/v1/orders/{id}` — update order
- `POST /api/v1/orders/{id}/receive` — receive shipment → create inventory
- `GET /api/v1/orders/{id}/items` — list order items
- `POST /api/v1/orders/{id}/items` — add item to order
- `GET /api/v1/export/orders.csv` — CSV export

**Key Components:**
- Tab bar (Active / Past / Drafts)
- Featured order card (with progress tracker: Ordered → Shipped → Out for Delivery → Received)
- Order cards grid
- Stats cards (monthly spend, delivery success, items in transit)
- New Requisition button
- Pagination

**States:** Loading, Populated, Empty (per tab), Creating order

---

### 7. Products

| | |
|---|---|
| **Route** | `/products` |
| **Purpose** | Product catalog — what the lab buys, from whom, at what price |
| **Stitch Screen** | *Not yet created* |
| **Spec** | `docs/specs/products.md` |
| **Status** | **Not built — API exists, no UI** |

**User Stories:**
- As a lab manager, I browse the product catalog with search and filters
- As a lab manager, I add a new product (name, catalog #, vendor, category, CAS #, storage)
- As a lab manager, I see product details: current inventory, order history, pricing
- As a researcher, I search for a product to check availability

**API Endpoints:**
- `GET /api/v1/products/` — list with filters (vendor_id, category, catalog_number, search)
- `POST /api/v1/products/` — create product
- `GET /api/v1/products/{id}` — product details
- `PATCH /api/v1/products/{id}` — update product
- `GET /api/v1/products/{id}/inventory` — inventory for product
- `GET /api/v1/products/{id}/orders` — order history for product
- `GET /api/v1/export/products.csv` — CSV export

**Key Components:**
- Product table (name, catalog #, vendor, category, stock level, price)
- Filter bar (vendor, category, hazardous, controlled)
- Search
- Add Product form/modal
- Product detail view (inventory tab, orders tab, info tab)
- Export CSV button

**States:** Loading, Populated, Empty, Creating, Editing

---

### 8. Vendors

| | |
|---|---|
| **Route** | `/vendors` |
| **Purpose** | Supplier directory — who the lab buys from |
| **Stitch Screen** | *Not yet created* |
| **Spec** | `docs/specs/vendors.md` |
| **Status** | **Not built — API exists, no UI** |

**User Stories:**
- As a lab manager, I browse all vendors with search
- As a lab manager, I add a new vendor (name, website, phone, email)
- As a lab manager, I see vendor details: products supplied, order history, spending
- As a lab manager, I export vendor list to CSV

**API Endpoints:**
- `GET /api/v1/vendors/` — list with filters (name, search)
- `POST /api/v1/vendors/` — create vendor
- `GET /api/v1/vendors/{id}` — vendor details
- `PATCH /api/v1/vendors/{id}` — update vendor
- `GET /api/v1/vendors/{id}/products` — products from vendor
- `GET /api/v1/vendors/{id}/orders` — orders from vendor
- `GET /api/v1/analytics/vendors/{id}/summary` — vendor summary stats
- `GET /api/v1/export/vendors.csv` — CSV export

**Key Components:**
- Vendor cards or table (name, contact, product count, order count, total spent)
- Search
- Add Vendor form/modal
- Vendor detail view (products tab, orders tab, spending tab)
- Export CSV button

**States:** Loading, Populated, Empty, Creating, Editing

---

### 9. Settings

| | |
|---|---|
| **Route** | `/settings` |
| **Purpose** | System configuration — lab profile, locations, staff, preferences |
| **Stitch Screen** | *Not yet created* |
| **Spec** | `docs/specs/settings.md` |
| **Status** | **Placeholder — no real UI** |

**User Stories:**
- As an admin, I configure lab name, subtitle, logo
- As an admin, I manage storage locations (rooms, buildings, temperature zones)
- As an admin, I manage staff accounts (add/deactivate users, set roles)
- As an admin, I set alert thresholds (low stock levels, expiry warning days)
- As an admin, I toggle dark/light theme

**API Endpoints:**
- `GET /api/config` — get lab config
- Staff CRUD (needs new endpoints)
- Location CRUD (needs new endpoints)
- Alert configuration (needs new endpoints)

**Tabs:**
1. **Lab Profile** — name, subtitle, logo, timezone
2. **Locations** — CRUD for storage locations (room, building, temperature)
3. **Staff** — CRUD for staff members (name, email, role, active)
4. **Alerts** — threshold configuration
5. **Appearance** — theme toggle, density

**States:** Loading, Populated (per tab)

---

### 10. Alerts

| | |
|---|---|
| **Route** | `/alerts` |
| **Purpose** | View and manage system alerts (low stock, expiring, stale orders) |
| **Stitch Screen** | *Not yet created* |
| **Spec** | — (needs spec) |
| **Status** | Built — basic placeholder in App.tsx |

**User Stories:**
- As a lab manager, I see all active alerts (low stock, expiring items, stale orders)
- As a lab manager, I acknowledge or resolve alerts

**API Endpoints:**
- `GET /api/v1/alerts/` — list alerts with filters
- `GET /api/v1/alerts/summary` — alert counts by type/severity
- `POST /api/v1/alerts/check` — trigger alert generation
- `POST /api/v1/alerts/{id}/acknowledge` — mark acknowledged
- `POST /api/v1/alerts/{id}/resolve` — mark resolved

**Key Components:**
- Alert list (type, severity, message, entity link, timestamp)
- Filter by type/severity/status
- Acknowledge/resolve buttons

**States:** Loading, Populated, Empty

---

### 11. Login

| | |
|---|---|
| **Route** | `/login` (conditional guard — renders before router when not authenticated) |
| **Purpose** | Authentication gate |
| **Stitch Screen** | `Login — Lab Manager` |
| **Spec** | `docs/specs/login.md` |
| **Status** | Built |

**User Stories:**
- As any user, I log in with email and password
- As any user, I see helpful error messages on failed login

**API Endpoints:**
- `POST /api/auth/login` — authenticate

**Key Components:**
- Email input, Password input, Remember me checkbox, Submit button
- Error message display
- Lab Manager branding

**States:** Default, Submitting, Error

---

### 12. Setup Wizard

| | |
|---|---|
| **Route** | `/setup` (conditional guard — renders before router when `needs_setup=true`) |
| **Purpose** | First-run configuration — create admin account |
| **Stitch Screen** | `One-Click Setup Wizard` |
| **Spec** | `docs/specs/setup.md` |
| **Status** | Built |

**User Stories:**
- As a first-time deployer, I create the admin account (name, email, password)
- As a first-time deployer, I'm redirected to login after setup

**API Endpoints:**
- `GET /api/setup/status` — check if setup needed
- `POST /api/setup/complete` — create admin user

**Key Components:**
- Lab name, Admin name, Email, Password inputs
- Validation messages
- Submit button

**States:** Default, Submitting, Validation error, Complete

---

## Special States (not routes)

| State | Stitch Screen | When Shown |
|-------|--------------|------------|
| **Error** | `Lab Manager — Error State` | API failure, network error, 500 |
| **Loading Skeleton** | `Lab Manager — Loading Skeleton State` | Initial page load |
| **Empty State** | `Inventory — Empty State` | No data for a list view |

---

## Summary

| # | Page | Route | Backend | Frontend | Stitch | Priority |
|---|------|-------|---------|----------|--------|----------|
| 1 | Dashboard | `/` | done | done | done | wire spending chart |
| 2 | Documents | `/documents` | done | done | done | - |
| 3 | Upload | `/upload` | done | done | done | - |
| 4 | Review Queue | `/review` | done | done | done | wire approve/reject |
| 5 | Inventory | `/inventory` | done | done | done | wire CRUD actions |
| 6 | Orders | `/orders` | done | done | done | wire CRUD actions |
| 7 | Products | `/products` | done | **not built** | **not designed** | **HIGH** |
| 8 | Vendors | `/vendors` | done | **not built** | **not designed** | **HIGH** |
| 9 | Settings | `/settings` | partial | **placeholder** | **not designed** | MEDIUM |
| 10 | Alerts | `/alerts` | done | **placeholder** | **not designed** | MEDIUM |
| 11 | Login | `/login` (guard) | done | done | done | - |
| 12 | Setup | `/setup` (guard) | done | done | done | - |

**Immediate priorities:**
1. Wire existing pages to their API actions (Review, Inventory, Orders)
2. Build Products page (API ready, no UI)
3. Build Vendors page (API ready, no UI)
4. Build Settings page (partial API, needs Location/Staff CRUD endpoints)
5. Build Alerts page (API ready, placeholder UI)
