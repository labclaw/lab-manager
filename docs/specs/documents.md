# Documents — Page Spec

| | |
|---|---|
| **Route** | `/documents` |
| **Status** | Built — wired (read-only) |
| **Priority** | — (functional for browsing) |
| **Stitch Screen** | `Documents Management` |

---

## What Needs to Be Done

Page is functional for browsing. Future enhancements:
1. Add CSV export button → `GET /api/v1/export/documents.csv` (no endpoint exists yet)
2. Add delete action per document
3. Add bulk actions (approve/reject multiple)

---

## API Contract

### GET /api/v1/documents/
List documents with filters.
```
Query params:
  page (int, default 1)
  page_size (int, default 20)
  status (str): pending | extracted | needs_review | approved | rejected
  document_type (str): invoice | packing_list | coa | quote | other
  vendor_name (str): partial match
  extraction_model (str)
  search (str): full-text search
  sort_by (str): created_at | file_name | vendor_name | status | extraction_confidence
  sort_dir (str): asc | desc
```
```json
// Response
{
  "items": [{
    "id": 1,
    "file_name": "invoice_001.pdf",
    "document_type": "invoice",
    "vendor_name": "Sigma-Aldrich",
    "extraction_confidence": 0.92,
    "status": "approved",
    "created_at": "2026-03-15T10:00:00"
  }],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "pages": 5
}
```

### GET /api/v1/documents/{id}
Document details with extracted_data JSON.

### GET /api/v1/documents/stats
Processing statistics for header cards.
```json
// Response
{
  "total": 100,
  "by_status": { "approved": 75, "needs_review": 20, "rejected": 5 },
  "by_type": { "invoice": 60, "packing_list": 30, "coa": 10 },
  "total_orders_created": 50,
  "total_items_extracted": 200,
  "total_vendors_matched": 12,
  "top_vendors": [{ "name": "Sigma", "count": 30 }]
}
```

---

## Component Architecture

```
DocumentsPage
├── StatsCards (total, approved, pending, rejected counts)
├── StatusFilterTabs (All | Approved | Needs Review | Rejected)
├── SearchBar (text input → search param)
├── DocumentTable
│   ├── Row (file name, vendor, type, confidence bar, status badge, date)
│   └── RowActions (view → /review/{id}, delete)
└── Pagination (page nav with total count)
```

## Data Flow

```typescript
const [page, setPage] = useState(1)
const [status, setStatus] = useState<string>('all')
const [search, setSearch] = useState('')

const { data } = useQuery({
  queryKey: ['documents', page, status, search],
  queryFn: () => documents.list(page, 20, status === 'all' ? undefined : status, search),
})
```

---

## User Interactions

| Action | Behavior |
|--------|----------|
| Click status tab | Filter list by status, reset to page 1 |
| Type in search | Debounce 300ms, filter by search term, reset to page 1 |
| Click document row | Navigate to `/review` with document selected |
| Click pagination | Load next/prev page |

---

## UI States

| State | Condition | Display |
|-------|-----------|---------|
| Loading | Fetching | Skeleton table rows |
| Populated | Items returned | Document table with pagination |
| Empty | No documents at all | Upload prompt with link to `/upload` |
| Filtered-empty | Filter/search returns 0 | "No documents match" with clear filter button |

---

## Acceptance Criteria

- [ ] Status filter tabs filter documents by status
- [ ] Search bar filters by file name and vendor name
- [ ] Confidence column shows color-coded bar (green >80%, yellow 60-80%, red <60%)
- [ ] Clicking a row navigates to review page
- [ ] Pagination works correctly with total count
- [ ] Empty state prompts user to upload
