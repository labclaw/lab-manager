# Settings — Page Spec

| | |
|---|---|
| **Route** | `/settings` |
| **Status** | **Placeholder — no real UI** |
| **Priority** | **P2 — partial API, needs Location/Staff CRUD endpoints** |
| **Stitch Screen** | *Not yet created* |

---

## What Needs to Be Done

1. Design and build tabbed settings page
2. Lab Profile tab: wire to `GET /api/config` (read-only for now)
3. Locations tab: CRUD for StorageLocation (API exists in models, needs routes)
4. Staff tab: CRUD for Staff (model exists, needs routes)
5. Alerts tab: threshold configuration (needs new endpoints)
6. Appearance tab: theme toggle (already works via localStorage)

### Backend work needed

The following endpoints need to be **created** before this page can be fully wired:
- `GET /api/v1/locations/` — list storage locations
- `POST /api/v1/locations/` — create location
- `PATCH /api/v1/locations/{id}` — update location
- `DELETE /api/v1/locations/{id}` — delete location
- `GET /api/v1/staff/` — list staff
- `POST /api/v1/staff/` — create staff member
- `PATCH /api/v1/staff/{id}` — update staff
- `DELETE /api/v1/staff/{id}` — deactivate staff

---

## Existing API

### GET /api/config
Lab configuration (currently read-only).
```json
// Response (current)
{
  "lab_name": "Lab Manager",
  "lab_subtitle": "Laboratory",
  "version": "0.1.5"
}
```

### StorageLocation model (exists in DB, no routes yet)
```
Fields:
  id (int, PK)
  name (str, 255)
  building (str, 255)
  room (str, 100)
  temperature_zone (str, 50): ambient | 4C | -20C | -80C
  notes (str, text)
```

### Staff model (referenced in audit, no routes yet)
```
Fields:
  id (int, PK)
  email (str, 255, unique)
  name (str, 255)
  role (str, 50): admin | manager | researcher | viewer
  is_active (bool)
```

---

## Component Architecture

```
SettingsPage
├── Header ("Settings")
├── TabNav
│   ├── Lab Profile
│   ├── Locations
│   ├── Staff
│   ├── Alerts
│   └── Appearance
├── TabContent
│   ├── LabProfileTab
│   │   ├── LabNameInput
│   │   ├── LabSubtitleInput
│   │   ├── TimezoneSelect
│   │   └── SaveButton
│   ├── LocationsTab
│   │   ├── LocationTable (name, building, room, temp zone)
│   │   ├── AddLocationButton → Modal
│   │   └── EditLocationButton → Modal
│   ├── StaffTab
│   │   ├── StaffTable (name, email, role, active badge)
│   │   ├── AddStaffButton → Modal
│   │   ├── EditRoleButton
│   │   └── DeactivateButton
│   ├── AlertsTab
│   │   ├── LowStockThreshold (input)
│   │   ├── ExpiryWarningDays (input)
│   │   └── SaveButton
│   └── AppearanceTab
│       ├── ThemeToggle (light/dark)
│       └── DensitySelect (compact/comfortable)
```

---

## User Interactions

| Action | Behavior |
|--------|----------|
| Switch tab | Show corresponding settings panel |
| Edit lab name | Update config (needs PATCH endpoint) |
| Add location | Modal → create location |
| Edit location | Modal → update location |
| Delete location | Confirm → delete (fails if inventory uses it) |
| Add staff | Modal → create staff member |
| Change staff role | Dropdown → update |
| Deactivate staff | Toggle → update is_active |
| Toggle theme | Switch dark/light, save to localStorage |

---

## UI States

| State | Condition | Display |
|-------|-----------|---------|
| Loading | Fetching config | Skeleton form |
| Populated | Data loaded | Forms with current values |
| Saving | Mutation in progress | Save button disabled + spinner |
| Error | Save failed | Error toast |

---

## Implementation Note

This page is **blocked** on backend work for Location and Staff CRUD routes. Implementation order:
1. Build Appearance tab first (no API needed — localStorage only)
2. Build Lab Profile tab (read-only from GET /api/config)
3. Backend: add Location CRUD routes
4. Build Locations tab
5. Backend: add Staff CRUD routes
6. Build Staff tab
7. Backend: add alert threshold config
8. Build Alerts tab

---

## Acceptance Criteria

- [ ] Tabbed layout with 5 tabs
- [ ] Appearance tab toggles light/dark theme
- [ ] Lab Profile tab shows current config
- [ ] Locations tab lists all storage locations with CRUD
- [ ] Staff tab lists all staff with role management
- [ ] Alerts tab configures low-stock and expiry thresholds
- [ ] All forms show success/error feedback
