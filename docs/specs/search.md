# Search — Feature Spec

| | |
|---|---|
| **Location** | Header search bar (global) |
| **Status** | **Input exists, NOT wired to API** |
| **Priority** | **P0 — must fix** |

---

## What Needs to Be Done

1. Wire header search input to `GET /api/v1/search/?q=`
2. Show search results in a dropdown or results page
3. Add autocomplete suggestions from `GET /api/v1/search/suggest`

---

## API Contract

### GET /api/v1/search/?q=
Full-text search across all entities.
```
Query params:
  q (str, required): search term
  index (str, optional): vendors | products | orders | inventory | documents
  limit (int, 1-100, default 20)
```
```json
// Response
{
  "query": "sodium",
  "results": [
    { "index": "products", "id": 1, "name": "Sodium Chloride", "score": 0.95 },
    { "index": "vendors", "id": 3, "name": "Sigma-Aldrich", "score": 0.72 }
  ],
  "total": 15
}
```

### GET /api/v1/search/suggest
Autocomplete suggestions as user types.
```
Query params:
  q (str, required): partial input
  limit (int, 1-20, default 5)
```
```json
// Response
{
  "query": "sod",
  "suggestions": [
    "Sodium Chloride",
    "Sodium Hydroxide",
    "Sigma-Aldrich"
  ]
}
```

---

## Component Architecture

```
Header
└── SearchBar
    ├── SearchInput (with debounce)
    ├── SuggestionsDropdown (appears on focus + typing)
    │   └── SuggestionItem (click → navigate to entity)
    └── SearchResultsPage (optional — full results page)
```

## Data Flow

```typescript
const [query, setQuery] = useState('')
const debouncedQuery = useDebounce(query, 300)

// Suggestions (as user types)
const { data: suggestions } = useQuery({
  queryKey: ['search-suggest', debouncedQuery],
  queryFn: () => search.suggest(debouncedQuery),
  enabled: debouncedQuery.length >= 2,
})

// Full search (on Enter)
const { data: results } = useQuery({
  queryKey: ['search', submittedQuery],
  queryFn: () => search.query(submittedQuery),
  enabled: !!submittedQuery,
})
```

---

## User Interactions

| Action | Behavior |
|--------|----------|
| Type in search bar | After 2 chars + 300ms debounce, show suggestions |
| Click suggestion | Navigate to entity page (product → /products, vendor → /vendors) |
| Press Enter | Submit full search, show results grouped by entity type |
| Press Escape | Close suggestions dropdown |
| Clear input | Hide suggestions |

---

## Acceptance Criteria

- [ ] Search input calls suggest API after 2+ chars with debounce
- [ ] Suggestions dropdown shows results grouped by type
- [ ] Clicking suggestion navigates to correct entity page
- [ ] Enter submits full search
- [ ] Meilisearch integration returns relevant results
- [ ] No search when input is empty or < 2 chars
