# Alerts — Page Spec

| | |
|---|---|
| **Route** | `/alerts` |
| **Status** | **Placeholder** — inline component in App.tsx, no real UI |
| **Priority** | P2 — API ready, needs UI |
| **Stitch Screen** | *Not yet created* |

---

## What Needs to Be Done

1. Build full alerts page (currently just "Alerts page coming soon" text)
2. Or: integrate as dashboard widget instead of standalone page (design decision needed)
3. Wire to all 5 alert API endpoints

---

## API Contract

### GET /api/v1/alerts/
List alerts with filters.
```
Query params:
  alert_type: expired | expiring_soon | out_of_stock | low_stock | pending_review | stale_orders
  severity: critical | warning | info
  acknowledged (bool)
  resolved (bool)
  page, page_size
```
```json
// Response
{
  "items": [{
    "id": 1,
    "alert_type": "low_stock",
    "severity": "warning",
    "message": "Sodium Chloride below reorder level (2 remaining, min 5)",
    "entity_type": "inventory_item",
    "entity_id": 42,
    "is_acknowledged": false,
    "acknowledged_by": null,
    "acknowledged_at": null,
    "is_resolved": false,
    "created_at": "2026-03-19T10:00:00"
  }],
  "total": 15, "page": 1, "page_size": 20, "pages": 1
}
```

### GET /api/v1/alerts/summary
Alert counts by type and severity.
```json
// Response
{
  "total": 15,
  "by_severity": { "critical": 2, "warning": 8, "info": 5 },
  "by_type": { "low_stock": 4, "expiring_soon": 3, "expired": 2, "pending_review": 6 },
  "unacknowledged": 10
}
```

### POST /api/v1/alerts/check
Trigger alert generation (scans current state for new alerts).
```json
// Response
{ "new_alerts": 3, "summary": { /* same as /summary */ } }
```

### POST /api/v1/alerts/{id}/acknowledge
Mark alert as seen. Also auto-resolves.
```json
// Request (optional)
{ "acknowledged_by": "admin" }
```

### POST /api/v1/alerts/{id}/resolve
Mark alert as resolved.

---

## Component Architecture

```
AlertsPage
├── AlertSummaryCards (critical count, warning count, info count)
├── FilterBar
│   ├── TypeFilter (dropdown: all types)
│   ├── SeverityFilter (dropdown: critical/warning/info)
│   └── StatusFilter (all / unacknowledged / resolved)
├── AlertTable
│   ├── AlertRow
│   │   ├── SeverityBadge (red/yellow/blue)
│   │   ├── TypeIcon
│   │   ├── Message
│   │   ├── EntityLink (click → navigate to related item)
│   │   ├── Timestamp
│   │   └── ActionButtons (acknowledge, resolve)
│   └── EmptyRow
├── Pagination
└── CheckAlertsButton ("Scan for new alerts")
```

## Data Flow

```typescript
const [filters, setFilters] = useState({ type: null, severity: null, resolved: false })

const { data } = useQuery({
  queryKey: ['alerts', filters],
  queryFn: () => alerts.list(filters),
})

const { data: summary } = useQuery({
  queryKey: ['alerts-summary'],
  queryFn: alerts.summary,
})

const acknowledgeMutation = useMutation({
  mutationFn: (id: number) => alerts.acknowledge(id),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
})

const resolveMutation = useMutation({
  mutationFn: (id: number) => alerts.resolve(id),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
})
```

### API client additions needed

```typescript
// In api.ts — alerts module, add:
summary: () => get('/alerts/summary'),
check: () => post('/alerts/check'),
resolve: (id: number) => post(`/alerts/${id}/resolve`),
```

---

## User Interactions

| Action | Behavior |
|--------|----------|
| Click severity filter | Filter alerts list |
| Click type filter | Filter by alert type |
| Click "Acknowledge" | POST acknowledge, refresh list |
| Click "Resolve" | POST resolve, refresh list |
| Click entity link | Navigate to related page (e.g., inventory item) |
| Click "Scan for alerts" | POST check, refresh list + summary |

---

## UI States

| State | Condition | Display |
|-------|-----------|---------|
| Loading | Fetching | Skeleton table |
| Populated | Alerts exist | Alert table with filters |
| Empty | No alerts | Celebratory "No alerts!" message |
| Scanning | Check in progress | Spinner on scan button |

---

## Acceptance Criteria

- [ ] Alert list loads from `GET /alerts/` with pagination
- [ ] Filter by type, severity, acknowledged/resolved status
- [ ] Summary cards show counts by severity
- [ ] "Acknowledge" button calls POST and updates list
- [ ] "Resolve" button calls POST and updates list
- [ ] "Scan for alerts" triggers POST /check
- [ ] Entity links navigate to related inventory/order/document
- [ ] Severity badges color-coded (red=critical, yellow=warning, blue=info)
- [ ] Default view shows unresolved alerts only
