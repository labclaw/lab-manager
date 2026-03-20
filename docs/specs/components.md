# Shared Components — Spec

Reusable UI components used across multiple pages.

Last updated: 2026-03-19

---

## Layout Components

### Header (`components/layout/Header.tsx`)

| | |
|---|---|
| **Used by** | App.tsx (global — every authenticated page) |
| **Status** | Built |

**Props:** `title`, `onSearch`, `darkMode`, `onToggleDarkMode`

**Contains:**
- Search input (global search bar)
- Notifications button (badge from alerts)
- Dark/light mode toggle
- User name display

**Known issues:**
- Search input exists but `onSearch` is not wired to `GET /api/v1/search/`
- Notifications button exists but not wired to alerts

---

### Sidebar (`components/layout/Sidebar.tsx`)

| | |
|---|---|
| **Used by** | App.tsx (global — every authenticated page) |
| **Status** | Built |

**Contains:**
- Lab name + subtitle branding
- Navigation links (6 items: Dashboard, Documents, Review, Inventory, Orders, Upload)
- Active route highlighting
- Sign out button

**Known issues:**
- Missing nav links for Products, Vendors, Settings (planned pages)

---

## UI Components

### ConfidenceBadge (`components/ui/ConfidenceBadge.tsx`)

| | |
|---|---|
| **Used by** | ReviewPage |
| **Purpose** | Color-coded confidence indicator for AI extraction results |
| **Status** | Built |

**Props:** `confidence: number` (0-1)

**Behavior:**
- Green: confidence > 0.80
- Yellow: confidence 0.60 - 0.80
- Red: confidence < 0.60

---

### EmptyState (`components/ui/EmptyState.tsx`)

| | |
|---|---|
| **Used by** | (imported but not yet used in any page) |
| **Purpose** | Placeholder for list views with no data |
| **Status** | Built, unused |

**Props:** `icon`, `title`, `description`, `action` (optional CTA button)

**Spec references:** Used in multiple page specs for empty/filtered-empty states.

---

### ErrorBanner (`components/ui/ErrorBanner.tsx`)

| | |
|---|---|
| **Used by** | App.tsx (global error display) |
| **Purpose** | Dismissible error notification banner |
| **Status** | Built |

**Props:** `message`, `onDismiss`

---

### SkeletonTable (`components/ui/SkeletonTable.tsx`)

| | |
|---|---|
| **Used by** | (imported but not yet used in any page) |
| **Purpose** | Loading placeholder for table views |
| **Status** | Built, unused |

**Props:** `rows`, `columns`

**Spec references:** Referenced in multiple page specs for loading states.

---

## Component Coverage Matrix

| Component | Built | Used in Code | Referenced in Spec | Gap |
|-----------|-------|-------------|-------------------|-----|
| Header | yes | App.tsx | PAGES.md | search not wired |
| Sidebar | yes | App.tsx | PAGES.md | missing nav items |
| ConfidenceBadge | yes | ReviewPage | review.md | — |
| EmptyState | yes | none | multiple specs | not wired to any page |
| ErrorBanner | yes | App.tsx | — | add to spec |
| SkeletonTable | yes | none | multiple specs | not wired to any page |
