# Review Queue — Page Spec

| | |
|---|---|
| **Route** | `/review` |
| **Status** | Built — **approve/reject partially wired, field editing NOT wired** |
| **Priority** | **P0 — must fix approve/reject; P1 — wire field editing** |
| **Stitch Screen** | `Refined Review Queue (Standardized)` |

---

## What Needs to Be Done

1. **P0**: Ensure approve/reject calls `POST /api/v1/documents/{id}/review` correctly
2. **P1**: Wire extracted field editing to `PATCH /api/v1/documents/{id}`
3. **P1**: Show original document preview (image/PDF viewer)
4. Side-by-side layout: document preview (left) + extracted data form (right)

---

## API Contract

### GET /api/v1/documents/?status=needs_review
Review queue — documents awaiting human verification.
```
Query: page=1, page_size=100, status=needs_review
```
```json
// Response: paginated Document[] with extracted_data
```

### GET /api/v1/documents/{id}
Full document details including extracted data.
```json
// Response
{
  "id": 42,
  "file_name": "invoice.pdf",
  "file_path": "uploads/20260319_invoice.pdf",
  "document_type": "invoice",
  "vendor_name": "Sigma-Aldrich",
  "ocr_text": "raw OCR text...",
  "extracted_data": {
    "vendor": { "name": "Sigma-Aldrich", "confidence": 0.95 },
    "po_number": { "value": "PO-2026-001", "confidence": 0.88 },
    "items": [
      {
        "catalog_number": "S1234",
        "description": "Sodium Chloride",
        "quantity": 5,
        "unit": "kg",
        "unit_price": 45.00,
        "lot_number": "LOT-ABC",
        "confidence": 0.91
      }
    ]
  },
  "extraction_confidence": 0.91,
  "status": "needs_review"
}
```

### POST /api/v1/documents/{id}/review
Approve or reject a document.
```json
// Request
{
  "action": "approve",        // "approve" | "reject"
  "reviewed_by": "admin",     // current user
  "review_notes": "optional"  // required for reject
}
```
```json
// Response: updated Document
// On approve: auto-creates vendor + order + inventory records from extracted_data
```

### PATCH /api/v1/documents/{id}
Update extracted fields before approval.
```json
// Request — partial update
{
  "vendor_name": "Corrected Vendor Name",
  "extracted_data": { /* updated fields */ }
}
```

---

## Component Architecture

```
ReviewPage
├── QueueList (left sidebar — scrollable list of pending documents)
│   └── QueueItem (file name, vendor, confidence badge, date)
├── DocumentPreview (center panel — image/PDF viewer)
│   └── ImageViewer | PDFViewer (based on file type)
├── ExtractionForm (right panel — editable fields)
│   ├── VendorField (name, editable, confidence indicator)
│   ├── PONumberField (editable)
│   ├── LineItemsTable (editable rows: catalog#, description, qty, unit, price, lot#)
│   │   └── LineItemRow (per-field confidence colors)
│   └── NotesField (reviewer notes)
├── ActionBar (bottom)
│   ├── ApproveButton (keyboard shortcut: Cmd+Enter)
│   ├── RejectButton (keyboard shortcut: Cmd+Backspace)
│   └── SaveDraftButton (save edits without approve/reject)
└── EmptyState (when queue is empty: "All caught up!")
```

## Data Flow

```typescript
// Queue
const { data: queue } = useQuery({
  queryKey: ['review-queue'],
  queryFn: () => documents.list(1, 100, 'needs_review'),
})

// Selected document
const [selectedId, setSelectedId] = useState<number | null>(null)
const { data: doc } = useQuery({
  queryKey: ['document', selectedId],
  queryFn: () => documents.get(selectedId!),
  enabled: !!selectedId,
})

// Mutations
const reviewMutation = useMutation({
  mutationFn: ({ id, action, notes }: ReviewParams) =>
    documents.review(id, { action, reviewed_by: currentUser, review_notes: notes }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['review-queue'] })
    // Auto-select next document in queue
  },
})

const updateMutation = useMutation({
  mutationFn: ({ id, data }: UpdateParams) => documents.update(id, data),
})
```

---

## User Interactions

| Action | Behavior |
|--------|----------|
| Click queue item | Load document preview + extracted data |
| Edit extracted field | Mark field as modified (visual indicator) |
| Click Approve (or Cmd+Enter) | Call review API with action=approve, advance to next |
| Click Reject (or Cmd+Backspace) | Open notes modal, then call review API with action=reject |
| Edit + Approve | PATCH extracted_data first, then approve |
| Queue empty | Show "All caught up!" empty state |

### Keyboard shortcuts
- `Cmd+Enter` / `Ctrl+Enter` — Approve current document
- `Cmd+Backspace` / `Ctrl+Backspace` — Reject current document
- `↑` / `↓` — Navigate queue list

---

## UI States

| State | Condition | Display |
|-------|-----------|---------|
| Loading | Fetching queue | Skeleton list + skeleton form |
| Queue populated | Documents in review | Split view: queue | preview | form |
| Reviewing | Document selected | Full split view with data |
| Submitting | Approve/reject in progress | Button disabled, spinner |
| Queue empty | No pending documents | Celebratory empty state |
| Error | API failure | Error toast, retry button |

---

## Business Logic Notes

- **Approval creates records**: When a document is approved, the backend auto-creates:
  - Vendor (if new, matched by name)
  - Order (with PO number from extraction)
  - Order items (from line items)
  - This is handled server-side — the frontend just calls review with action=approve
- **Confidence colors**: Per-field confidence from extraction
  - Green: > 0.80
  - Yellow: 0.60 - 0.80
  - Red: < 0.60
- **Human-in-the-loop**: Core principle — AI extracts, human verifies. No auto-approve.

---

## Acceptance Criteria

- [ ] Queue shows all documents with status=needs_review
- [ ] Selecting a document shows preview + extracted data side-by-side
- [ ] Extracted fields are editable (vendor name, PO#, line items)
- [ ] Confidence indicators show per-field extraction confidence
- [ ] Approve button calls `POST /documents/{id}/review` with action=approve
- [ ] Reject button requires notes, calls review with action=reject
- [ ] After approve/reject, queue auto-advances to next document
- [ ] Keyboard shortcuts work (Cmd+Enter, Cmd+Backspace)
- [ ] Empty queue shows "All caught up!" state
- [ ] Edited fields are saved via PATCH before approve
