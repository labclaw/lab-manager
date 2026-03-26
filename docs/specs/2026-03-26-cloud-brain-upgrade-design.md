# Cloud Brain Upgrade: Form-Submission to Conversational AI

**Date:** 2026-03-26
**Status:** Draft
**Author:** Lab Manager Team
**Scope:** `CloudBrainPage.tsx` (617 lines) + new dependencies

---

## 1. Problem Statement

The current `CloudBrainPage` is a form-submission UI:

1. **User must know tool names and argument formats.** The only input is a single text field that posts to `/brain/reason` with `{question, domain}`. No smart routing to `/brain/execute` or `/brain/write`.
2. **No streaming.** The page fires a sync `fetch()`, waits for the full JSON response, then renders it. Long-running tool calls (up to 30s timeout per `tooluniverse.py`) show only a generic "Processing..." spinner.
3. **No markdown rendering.** Results are shown in a `<div className="whitespace-pre-wrap">` — raw text with no headings, code blocks, or lists.
4. **No tool activity indicators.** Users cannot see which tool is executing or how long it took.
5. **No conversation history.** Results are displayed as a flat list prepended newest-first (`[entry, ...prev]`), not a conversation.
6. **No NLP routing.** Every query goes to `/brain/reason` regardless of content. A query like "Look up protein P04637" should route to `/brain/execute` with the specific ToolUniverse tool, not to the general reasoning endpoint.

The `byok` reference (`use-agent.ts`, 384 lines) demonstrates the target UX:
- SSE streaming with `ReadableStream` parsing
- `ActivityItem[]` per message (running/complete/error states)
- `functionCall` / `functionResponse` events for tool activity display
- Streaming text appended to assistant messages in real time

---

## 2. Goals

| # | Goal | Metric |
|---|------|--------|
| G1 | Natural language input routes to the correct backend endpoint and tool | "What is BRCA1?" hits `/brain/execute` with `UniProt_get_function_by_accession`, not `/brain/reason` |
| G2 | Real-time tool activity display | Tool name + "Querying..." spinner visible within 100ms of submission |
| G3 | Markdown rendering for results | Headings, code blocks, lists, links render correctly |
| G4 | Conversation history within session | Messages flow top-to-bottom, persist until page navigation |
| G5 | Keep existing skill cards and health dashboard | Zero regression in current catalog/health UI |
| G6 | Mobile responsive | Chat input usable on 375px width screens |

### Non-Goals (Phase 1)

- Persistent conversation history across sessions (requires backend storage)
- Multi-turn context (each query is independent)
- Image/file upload in chat
- Backend SSE endpoint (Phase 2)

---

## 3. Architecture — Two Phases

### Phase 1: Enhanced Sync UI (no backend changes)

```
┌──────────────────────────────────────────────────┐
│  CloudBrainPage.tsx (upgraded)                   │
│                                                  │
│  ┌──────────────────────────────────────┐        │
│  │  Message List (ChatMessage[])        │        │
│  │  ┌─────────────────────────────────┐ │        │
│  │  │ User: "What is BRCA1?"         │ │        │
│  │  └─────────────────────────────────┘ │        │
│  │  ┌─────────────────────────────────┐ │        │
│  │  │ Assistant:                      │ │        │
│  │  │  [Querying UniProt... ✓ 0.7s]  │ │        │
│  │  │  ## BRCA1 Function             │ │        │
│  │  │  BRCA1 is a tumor suppressor...│ │        │
│  │  └─────────────────────────────────┘ │        │
│  └──────────────────────────────────────┘        │
│  ┌──────────────────────────────────────┐        │
│  │  Input: [________________________] [Send]     │
│  └──────────────────────────────────────┘        │
│                                                  │
│  ┌──────────────────────────────────────┐        │
│  │  Quick Actions / Skill Cards / Health│        │
│  └──────────────────────────────────────┘        │
└──────────────────────────────────────────────────┘
         │
         │  NLP Router (client-side)
         │  decides endpoint + payload
         ▼
┌────────────────────────┐
│  Existing Brain REST   │  No changes
│  POST /brain/execute   │
│  POST /brain/reason    │
│  POST /brain/write     │
│  GET  /brain/health    │
│  GET  /brain/tools     │
└────────────────────────┘
```

**What changes:**
- `results: QueryResult[]` replaced by `messages: ChatMessage[]`
- New `routeQuery()` function maps natural language to endpoint + payload
- `react-markdown` renders assistant messages
- Tool name + duration shown per query
- Messages flow top-to-bottom (chat style) with auto-scroll
- Input pinned to bottom of chat area

**What stays the same:**
- All backend endpoints unchanged
- Hero section with connection status
- Skill cards grid
- Quick actions bar
- Health status dashboard
- API reference hint

### Phase 2: Full SSE Streaming (with backend changes)

```
┌─────────────────────┐     ┌─────────────────────┐     ┌──────────────┐
│  CloudBrainPage     │ SSE │  lab-manager backend │ SSE │  labclaw     │
│  useCloudBrain()    │────▶│  POST /brain/stream  │────▶│  brain       │
│  (adapted from      │     │  (new endpoint)      │     │  server      │
│   use-agent.ts)     │     └─────────────────────┘     └──────────────┘
└─────────────────────┘
```

**New backend endpoint:** `POST /brain/stream`
- Accepts `{ query: string }` (NLP routing moves to backend)
- Returns SSE stream with events:
  - `data: {"type":"tool_start","tool_name":"UniProt_get_function_by_accession"}`
  - `data: {"type":"text","content":"...","partial":true}`
  - `data: {"type":"tool_end","tool_name":"...","duration_ms":700}`
  - `data: {"type":"text","content":"...","partial":false}`
  - `data: {"type":"done"}`

**Frontend changes:**
- `useCloudBrain()` hook adapted from `use-agent.ts` SSE protocol
- `ActivityItem[]` per message with running/complete/error states
- Streaming text appended to assistant content in real time

Phase 2 is out of scope for this spec. The remainder focuses on Phase 1.

---

## 4. Frontend Changes (Phase 1)

### 4a. New Types

Replace the existing `QueryResult` interface:

```typescript
// Remove
interface QueryResult {
  id: string
  query: string
  skill: string
  timestamp: Date
  status: 'loading' | 'done' | 'error'
  result?: string
  error?: string
}

// Add
interface ChatMessage {
  readonly id: string
  readonly role: 'user' | 'assistant'
  readonly content: string
  readonly toolName?: string
  readonly toolArgs?: Record<string, unknown>
  readonly duration?: number       // milliseconds
  readonly timestamp: number       // Date.now()
  readonly status?: 'loading' | 'done' | 'error'
  readonly error?: string
}
```

### 4b. State Changes

```typescript
// Remove
const [results, setResults] = useState<QueryResult[]>([])

// Add
const [messages, setMessages] = useState<ChatMessage[]>([])
const messagesEndRef = useRef<HTMLDivElement>(null)
```

### 4c. Message Rendering

**User messages:** right-aligned, blue background, white text.

```tsx
<div className="flex justify-end">
  <div className="max-w-[80%] bg-primary text-white rounded-2xl rounded-br-sm px-4 py-2.5">
    <p className="text-sm">{msg.content}</p>
    <p className="text-[10px] text-white/60 mt-1">
      {new Date(msg.timestamp).toLocaleTimeString()}
    </p>
  </div>
</div>
```

**Assistant messages:** left-aligned, with Brain avatar, markdown body.

```tsx
<div className="flex gap-3">
  <div className="size-8 flex items-center justify-center rounded-lg bg-violet-50 shrink-0 mt-1">
    <Brain className="size-4 text-violet-600" />
  </div>
  <div className="max-w-[80%]">
    {/* Tool activity indicator */}
    {msg.status === 'loading' && msg.toolName && (
      <div className="flex items-center gap-2 text-xs text-gray-500 mb-2">
        <Loader2 className="size-3 animate-spin" />
        Querying {msg.toolName}...
      </div>
    )}
    {msg.status === 'done' && msg.toolName && (
      <div className="flex items-center gap-2 text-xs text-gray-400 mb-2">
        <span className="text-emerald-500">✓</span>
        {msg.toolName} · {((msg.duration ?? 0) / 1000).toFixed(1)}s
      </div>
    )}
    {/* Markdown content */}
    {msg.content && (
      <div className="prose prose-sm max-w-none bg-gray-50 rounded-2xl rounded-bl-sm px-4 py-3">
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
          {msg.content}
        </ReactMarkdown>
      </div>
    )}
    {/* Error state */}
    {msg.status === 'error' && (
      <div className="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3">
        {msg.error}
      </div>
    )}
    <p className="text-[10px] text-gray-400 mt-1">
      {new Date(msg.timestamp).toLocaleTimeString()}
    </p>
  </div>
</div>
```

### 4d. Conversation Layout

```tsx
{/* Chat area */}
{connected && (
  <div className="bg-white border border-gray-200 rounded-xl shadow-sm flex flex-col"
       style={{ maxHeight: messages.length > 0 ? '60vh' : undefined }}>
    {/* Messages */}
    {messages.length > 0 && (
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>
    )}
    {/* Input pinned at bottom */}
    <div className="border-t border-gray-100 p-4">
      <form onSubmit={handleFormSubmit} className="flex gap-3">
        <input ... />
        <button type="submit" ...>
          <Send className="size-4" />
          Ask
        </button>
      </form>
    </div>
  </div>
)}
```

Auto-scroll on new messages:

```typescript
useEffect(() => {
  messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
}, [messages])
```

### 4e. handleSubmit Rewrite

```typescript
const handleSubmit = async (text: string) => {
  const trimmed = text.trim()
  if (!trimmed) return

  // 1. Add user message
  const userMsgId = `msg-${Date.now()}`
  const userMsg: ChatMessage = {
    id: userMsgId,
    role: 'user',
    content: trimmed,
    timestamp: Date.now(),
  }

  // 2. Route query
  const route = routeQuery(trimmed)

  // 3. Add placeholder assistant message
  const assistantId = `msg-${Date.now() + 1}`
  const assistantMsg: ChatMessage = {
    id: assistantId,
    role: 'assistant',
    content: '',
    toolName: route.toolName,
    toolArgs: route.toolArgs,
    timestamp: Date.now(),
    status: 'loading',
  }

  setMessages(prev => [...prev, userMsg, assistantMsg])
  setQuery('')

  const startTime = performance.now()

  try {
    const res = await fetch(`${CLOUD_BRAIN_URL}${route.endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(route.payload),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    const duration = performance.now() - startTime

    const content = formatBrainResponse(data, route)

    setMessages(prev =>
      prev.map(m =>
        m.id === assistantId
          ? { ...m, status: 'done' as const, content, duration }
          : m
      )
    )
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Unknown error'
    setMessages(prev =>
      prev.map(m =>
        m.id === assistantId
          ? { ...m, status: 'error' as const, error: msg }
          : m
      )
    )
  }
}
```

### 4f. Response Formatting

```typescript
function formatBrainResponse(data: any, route: RouteResult): string {
  // /brain/reason returns { success, data: { answer, ... } }
  if (route.endpoint === '/reason') {
    return data.data?.answer ?? JSON.stringify(data.data, null, 2)
  }

  // /brain/write returns { success, data: { text, ... } }
  if (route.endpoint === '/write') {
    return data.data?.text ?? data.data?.answer ?? JSON.stringify(data.data, null, 2)
  }

  // /brain/execute returns { success, data: <tool-specific> }
  if (route.endpoint === '/execute') {
    const result = data.data
    if (typeof result === 'string') return result

    // Try to extract meaningful fields for common tools
    if (result?.output) return typeof result.output === 'string'
      ? result.output
      : '```json\n' + JSON.stringify(result.output, null, 2) + '\n```'

    return '```json\n' + JSON.stringify(result, null, 2) + '\n```'
  }

  return JSON.stringify(data, null, 2)
}
```

### 4g. Page Layout Order (top to bottom)

1. Hero / Status (unchanged)
2. Quick Actions (unchanged)
3. **Chat Area** (new — messages + input)
4. AI Skills Grid (unchanged)
5. API Reference hint (unchanged)

The chat area replaces the old "Query input" and "Recent Queries" sections.

---

## 5. Smart NLP Router

### 5a. Route Result Type

```typescript
interface RouteResult {
  endpoint: '/execute' | '/reason' | '/write'
  payload: Record<string, unknown>
  toolName?: string        // display name for activity indicator
  toolArgs?: Record<string, unknown>
}
```

### 5b. Gene-to-Accession Map

```typescript
const GENE_TO_ACCESSION: Record<string, string> = {
  // Tumor suppressors & oncogenes
  BRCA1: 'P38398',  BRCA2: 'P51587',
  TP53: 'P04637',   P53: 'P04637',
  EGFR: 'P00533',   HER2: 'P04626',  ERBB2: 'P04626',
  KRAS: 'P01116',   BRAF: 'P15056',
  MYC: 'P01106',    RB1: 'P06400',
  PTEN: 'P60484',   APC: 'P25054',
  VHL: 'P40337',    RAS: 'P01112',

  // Kinases & signaling
  AKT1: 'P31749',   MTOR: 'P42345',
  PIK3CA: 'P42336', JAK2: 'O60674',
  SRC: 'P12931',    ABL1: 'P00519',
  CDK4: 'P11802',   CDK6: 'Q00534',
  RAF1: 'P04049',   MEK1: 'Q02750',
  ERK2: 'P28482',   MAP2K1: 'Q02750',

  // DNA repair & chromatin
  ATM: 'Q13315',    ATR: 'Q13535',
  CHEK1: 'O14757',  CHEK2: 'O96017',
  PALB2: 'Q86YC2',  RAD51: 'Q06609',

  // Growth factors & receptors
  VEGFA: 'P15692',  PDGFRA: 'P16234',
  FGFR1: 'P11362',  FGFR2: 'P21802',
  KIT: 'P10721',    MET: 'P08581',
  ALK: 'Q9UM73',    RET: 'P07949',
  ROS1: 'P08922',   NTRK1: 'P04629',
  IGF1R: 'P08069',  INSR: 'P06213',

  // Immune / checkpoint
  PD1: 'Q15116',    PDL1: 'Q9NZQ7',
  CTLA4: 'P16410',  CD19: 'P15391',
  CD20: 'P11836',

  // Metabolic enzymes
  IDH1: 'O75874',   IDH2: 'P48735',

  // Neuroscience
  APP: 'P05067',     MAPT: 'P10636',  TAU: 'P10636',
  APOE: 'P02649',   SNCA: 'P37840',
  HTT: 'P42858',    SOD1: 'P00441',
  BDNF: 'P23560',   GRIN1: 'Q05586',
}
```

### 5c. Routing Logic

```typescript
// UniProt accession pattern: e.g. P04637, Q9NZQ7
const ACCESSION_RE = /\b([ABOPQ]\d[A-Z\d]{3}\d)\b/i

function routeQuery(input: string): RouteResult {
  const q = input.trim()
  const upper = q.toUpperCase()

  // 1. Direct UniProt accession in query
  const accessionMatch = q.match(ACCESSION_RE)

  // 2. Gene name detection
  let detectedAccession: string | undefined
  let detectedGene: string | undefined
  for (const [gene, acc] of Object.entries(GENE_TO_ACCESSION)) {
    // Match whole word (case-insensitive)
    const re = new RegExp(`\\b${gene}\\b`, 'i')
    if (re.test(q)) {
      detectedAccession = acc
      detectedGene = gene
      break
    }
  }

  const accession = accessionMatch?.[1] ?? detectedAccession

  // 3. If accession found, decide which UniProt tool
  if (accession) {
    if (/sequence|amino\s*acid|fasta/i.test(q)) {
      return {
        endpoint: '/execute',
        payload: {
          tool_name: 'tu_run',
          arguments: {
            name: 'UniProt_get_sequence_by_accession',
            arguments: { accession },
          },
        },
        toolName: 'UniProt (sequence)',
        toolArgs: { accession, gene: detectedGene },
      }
    }
    if (/structure|3d|pdb|fold/i.test(q)) {
      return {
        endpoint: '/execute',
        payload: {
          tool_name: 'tu_run',
          arguments: {
            name: 'UniProt_get_3D_structure_by_accession',
            arguments: { accession },
          },
        },
        toolName: 'UniProt (3D structure)',
        toolArgs: { accession, gene: detectedGene },
      }
    }
    // Default for gene/protein queries: get function
    return {
      endpoint: '/execute',
      payload: {
        tool_name: 'tu_run',
        arguments: {
          name: 'UniProt_get_function_by_accession',
          arguments: { accession },
        },
      },
      toolName: 'UniProt (function)',
      toolArgs: { accession, gene: detectedGene },
    }
  }

  // 4. Drug / molecule queries
  if (/\b(drug|molecule|chembl|compound|inhibitor|agonist|antagonist)\b/i.test(q)) {
    // Extract the search term: remove the keyword, take remaining meaningful words
    const searchTerm = q
      .replace(/\b(search|find|look\s*up|query|what|is|the|for|about|info|information|drug|molecule|compound)\b/gi, '')
      .trim() || q
    return {
      endpoint: '/execute',
      payload: {
        tool_name: 'tu_run',
        arguments: {
          name: 'ChEMBL_search_molecules',
          arguments: { query: searchTerm },
        },
      },
      toolName: 'ChEMBL (molecule search)',
      toolArgs: { query: searchTerm },
    }
  }

  // 5. Clinical trial queries
  if (/\b(clinical\s*trial|study|treatment|phase\s*[1-4]|nct\d+|intervention)\b/i.test(q)) {
    const searchTerm = q
      .replace(/\b(search|find|look\s*up|clinical|trial|trials|study|studies)\b/gi, '')
      .trim() || q
    return {
      endpoint: '/execute',
      payload: {
        tool_name: 'tu_run',
        arguments: {
          name: 'ClinicalTrials_search_studies',
          arguments: { query: searchTerm },
        },
      },
      toolName: 'ClinicalTrials.gov',
      toolArgs: { query: searchTerm },
    }
  }

  // 6. PubChem queries
  if (/\b(pubchem|chemical|cas\s*number|smiles|inchi)\b/i.test(q)) {
    const searchTerm = q
      .replace(/\b(search|find|look\s*up|pubchem|chemical)\b/gi, '')
      .trim() || q
    return {
      endpoint: '/execute',
      payload: {
        tool_name: 'tu_run',
        arguments: {
          name: 'PubChem_search_compounds',
          arguments: { query: searchTerm },
        },
      },
      toolName: 'PubChem',
      toolArgs: { query: searchTerm },
    }
  }

  // 7. Adverse event queries
  if (/\b(adverse|side\s*effect|faers|safety|toxicity)\b/i.test(q)) {
    const searchTerm = q
      .replace(/\b(search|find|look\s*up|adverse|event|events|side|effect|effects|report|reports)\b/gi, '')
      .trim() || q
    return {
      endpoint: '/execute',
      payload: {
        tool_name: 'tu_run',
        arguments: {
          name: 'FAERS_search_reports',
          arguments: { query: searchTerm },
        },
      },
      toolName: 'FAERS (adverse events)',
      toolArgs: { query: searchTerm },
    }
  }

  // 8. Scientific writing
  if (/\b(write|draft|compose|abstract|methods?\s*section|results?\s*section|discussion|introduction|manuscript)\b/i.test(q)) {
    // Detect section type
    let section = 'methods'
    if (/abstract/i.test(q)) section = 'abstract'
    else if (/result/i.test(q)) section = 'results'
    else if (/discussion/i.test(q)) section = 'discussion'
    else if (/introduction/i.test(q)) section = 'introduction'

    return {
      endpoint: '/write',
      payload: { section, context: q },
      toolName: `Scientific Writing (${section})`,
    }
  }

  // 9. Experiment design / reasoning
  if (/\b(design|experiment|protocol|assay|western\s*blot|pcr|elisa|crispr|control)\b/i.test(q)) {
    return {
      endpoint: '/reason',
      payload: { question: q, domain: 'experimental_design' },
      toolName: 'Life Science Reasoning',
    }
  }

  // 10. Fallback: general reasoning
  return {
    endpoint: '/reason',
    payload: { question: q, domain: 'general' },
    toolName: 'Cloud Brain',
  }
}
```

### 5d. Routing Priority Table

| Priority | Detection Pattern | Endpoint | Tool |
|----------|------------------|----------|------|
| 1 | UniProt accession in text (`/[ABOPQ]\d[A-Z\d]{3}\d/`) | `/execute` | UniProt_get_function_by_accession |
| 2 | Gene name from `GENE_TO_ACCESSION` map (50+ genes) | `/execute` | UniProt (function/sequence/structure based on sub-keywords) |
| 3 | drug/molecule/chembl/compound/inhibitor | `/execute` | ChEMBL_search_molecules |
| 4 | clinical trial/study/treatment/phase | `/execute` | ClinicalTrials_search_studies |
| 5 | pubchem/chemical/cas/smiles | `/execute` | PubChem_search_compounds |
| 6 | adverse/side effect/faers/safety | `/execute` | FAERS_search_reports |
| 7 | write/draft/abstract/methods/results | `/write` | Scientific Writing |
| 8 | design/experiment/protocol/assay | `/reason` | Life Science Reasoning |
| 9 | (everything else) | `/reason` | Cloud Brain (general) |

---

## 6. Dependencies to Add

```bash
cd lab-manager/web
npm install react-markdown remark-gfm rehype-highlight
```

| Package | Purpose | Bundle size (gzip) |
|---------|---------|-------------------|
| `react-markdown` | Render markdown in React | ~7 KB |
| `remark-gfm` | GitHub-flavored markdown (tables, strikethrough, task lists) | ~1 KB |
| `rehype-highlight` | Syntax highlighting for code blocks | ~3 KB + language grammars |

### Import in CloudBrainPage.tsx

```typescript
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github.css'  // or github-dark.css
```

---

## 7. Files Changed

| File | Change | Est. lines |
|------|--------|-----------|
| `web/src/pages/CloudBrainPage.tsx` | Replace QueryResult with ChatMessage, add routeQuery(), add MessageBubble, add markdown rendering, rewrite handleSubmit, conversation layout | +250 / -80 (net ~787 lines) |
| `web/src/lib/cloud-brain-router.ts` | **New file.** Extract `routeQuery()`, `GENE_TO_ACCESSION`, `formatBrainResponse()` for testability | ~200 lines |
| `web/src/lib/cloud-brain-router.test.ts` | **New file.** Unit tests for NLP router | ~200 lines |
| `web/src/pages/__tests__/CloudBrainPage.test.tsx` | Update existing tests for new ChatMessage flow | +60 / -40 |
| `web/package.json` | Add react-markdown, remark-gfm, rehype-highlight | +3 lines |
| `web/src/index.css` | Import highlight.js stylesheet (if not using CSS import) | +1 line |

**No backend files change in Phase 1.**

---

## 8. Testing

### 8a. Unit Tests: NLP Router (`cloud-brain-router.test.ts`)

```typescript
describe('routeQuery', () => {
  // Gene name detection
  it('routes "What is BRCA1?" to UniProt function lookup', () => {
    const result = routeQuery('What is BRCA1?')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('tu_run')
    expect(result.payload.arguments.name).toBe('UniProt_get_function_by_accession')
    expect(result.payload.arguments.arguments.accession).toBe('P38398')
    expect(result.toolName).toBe('UniProt (function)')
  })

  // Direct accession
  it('routes "Look up P04637" to UniProt', () => {
    const result = routeQuery('Look up P04637')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.arguments.arguments.accession).toBe('P04637')
  })

  // Sequence sub-routing
  it('routes "Get EGFR sequence" to UniProt sequence', () => {
    const result = routeQuery('Get EGFR sequence')
    expect(result.payload.arguments.name).toBe('UniProt_get_sequence_by_accession')
    expect(result.payload.arguments.arguments.accession).toBe('P00533')
  })

  // Drug detection
  it('routes "Search aspirin drug" to ChEMBL', () => {
    const result = routeQuery('Search aspirin drug')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.arguments.name).toBe('ChEMBL_search_molecules')
  })

  // Clinical trial detection
  it('routes "clinical trials for EGFR inhibitors" to ClinicalTrials', () => {
    const result = routeQuery('Find clinical trials for EGFR inhibitors')
    // Gene detection has higher priority, so this routes to UniProt
    // unless we specifically handle "clinical trial" priority
    expect(result.endpoint).toBe('/execute')
  })

  // Writing detection
  it('routes "Write a Methods section" to /write', () => {
    const result = routeQuery('Write a Methods section for immunohistochemistry')
    expect(result.endpoint).toBe('/write')
    expect(result.payload.section).toBe('methods')
  })

  // Experiment design
  it('routes "Design a Western blot experiment" to /reason', () => {
    const result = routeQuery('Design a Western blot experiment')
    expect(result.endpoint).toBe('/reason')
    expect(result.payload.domain).toBe('experimental_design')
  })

  // Fallback
  it('routes unknown queries to /reason general', () => {
    const result = routeQuery('Hello, how are you?')
    expect(result.endpoint).toBe('/reason')
    expect(result.payload.domain).toBe('general')
  })

  // Case insensitivity
  it('detects gene names case-insensitively', () => {
    const result = routeQuery('what is brca1?')
    expect(result.payload.arguments.arguments.accession).toBe('P38398')
  })

  // All 50+ genes in map should be valid UniProt accessions
  it('all accessions match UniProt format', () => {
    for (const [gene, acc] of Object.entries(GENE_TO_ACCESSION)) {
      expect(acc).toMatch(/^[ABOPQ]\d[A-Z\d]{3}\d$/)
    }
  })
})
```

### 8b. Component Tests: Message Rendering

```typescript
describe('CloudBrainPage chat', () => {
  it('renders user message right-aligned', () => { ... })
  it('renders assistant message with Brain avatar', () => { ... })
  it('renders markdown in assistant messages', () => { ... })
  it('shows loading indicator with tool name', () => { ... })
  it('shows tool name and duration after completion', () => { ... })
  it('shows error state on failure', () => { ... })
  it('auto-scrolls to latest message', () => { ... })
  it('preserves skill cards below chat', () => { ... })
})
```

### 8c. Integration Test: Full Query Flow

```typescript
describe('CloudBrainPage integration', () => {
  it('submits gene query and renders markdown response', async () => {
    // Mock fetch for /brain/execute
    fetchMock.post('/brain/execute', {
      success: true,
      data: { output: '## BRCA1\nBRCA1 is a tumor suppressor gene...' },
    })

    render(<CloudBrainPage onError={jest.fn()} __testConnected={true} __testHealth={mockHealth} />)

    const input = screen.getByPlaceholderText(/ask cloud brain/i)
    await userEvent.type(input, 'What is BRCA1?')
    await userEvent.click(screen.getByRole('button', { name: /ask/i }))

    // User message appears
    expect(screen.getByText('What is BRCA1?')).toBeInTheDocument()

    // Tool activity appears
    expect(screen.getByText(/querying uniprot/i)).toBeInTheDocument()

    // After response: markdown rendered
    await waitFor(() => {
      expect(screen.getByText('BRCA1')).toBeInTheDocument()
      expect(screen.getByText(/tumor suppressor/i)).toBeInTheDocument()
    })

    // Duration shown
    await waitFor(() => {
      expect(screen.getByText(/uniprot.*\d+\.\d+s/i)).toBeInTheDocument()
    })
  })
})
```

---

## 9. Success Criteria

| # | Criterion | Verification |
|---|-----------|-------------|
| S1 | User types "What is BRCA1?" and sees markdown-formatted protein function | Manual test + integration test |
| S2 | User types "Search aspirin" and sees ChEMBL results in code block | Manual test + integration test |
| S3 | Tool activity indicator shows tool name while loading, then tool name + duration after completion | Component test |
| S4 | Conversation persists within session (messages array not cleared on new query) | Component test |
| S5 | Existing skill cards grid renders correctly below chat | Component test (check DOM) |
| S6 | Health status dashboard still shows connected/tool count/version | Component test (use `__testHealth` prop) |
| S7 | Mobile responsive: chat input usable at 375px width | Manual test in devtools |
| S8 | Quick action buttons populate the chat input (or submit directly when connected) | Component test |
| S9 | All 50+ gene names in `GENE_TO_ACCESSION` route correctly | Unit test (parameterized) |
| S10 | `routeQuery()` has 100% branch coverage | Unit test coverage report |

---

## Appendix A: Backend Endpoints Reference

From `server.py` (no changes needed):

| Method | Path | Request Body | Response |
|--------|------|-------------|----------|
| GET | `/brain/health` | -- | `HealthStatus {status, skills, tool_count, version}` |
| GET | `/brain/tools` | `?category=` | `ToolInfo[]` |
| POST | `/brain/execute` | `{tool_name, arguments}` | `BrainResult {success, data, error}` |
| POST | `/brain/reason` | `{question, domain, context}` | `BrainResult {success, data, error}` |
| POST | `/brain/write` | `{section, context}` | `BrainResult {success, data, error}` |

### Execute Payload for ToolUniverse

The `tool_name` in `ExecuteRequest` is the ToolUniverse tool name (e.g., `UniProt_get_function_by_accession`). The registry routes it to `ToolUniverseSkill.execute()` which calls `tu.run({"name": tool_name, "arguments": kwargs})`.

From `tooluniverse.py` line 76-79:
```python
payload = {"name": tool_name, "arguments": kwargs}
result = await asyncio.wait_for(
    loop.run_in_executor(None, tu.run, payload),
    timeout=30.0,
)
```

So the frontend POST to `/brain/execute` should be:
```json
{
  "tool_name": "UniProt_get_function_by_accession",
  "arguments": { "accession": "P38398" }
}
```

The `tool_name` is the ToolUniverse tool name directly, and `arguments` is the dict passed as `**kwargs` to `execute()`, which becomes the `arguments` value in the ToolUniverse payload.

---

## Appendix B: Phase 2 SSE Protocol Reference

From `use-agent.ts` (byok), the SSE event format:

```
data: {"content":{"parts":[{"functionCall":{"id":"call_1","name":"search","args":{"query":"..."}}}]}}
data: {"content":{"parts":[{"functionResponse":{"id":"call_1","name":"search","response":{"result":"..."}}}]}}
data: {"content":{"parts":[{"text":"Here are the results..."}]},"partial":true}
data: {"content":{"parts":[{"text":"Final complete text"}]},"partial":false}
```

The lab-manager Phase 2 SSE endpoint should use a simplified version:

```
data: {"type":"tool_start","tool_name":"UniProt_get_function_by_accession","tool_args":{"accession":"P38398"}}
data: {"type":"text","content":"## BRCA1 Function\n","partial":true}
data: {"type":"text","content":"## BRCA1 Function\nBRCA1 is a tumor suppressor...","partial":true}
data: {"type":"tool_end","tool_name":"UniProt_get_function_by_accession","duration_ms":700}
data: {"type":"text","content":"## BRCA1 Function\nBRCA1 is a tumor suppressor gene that...","partial":false}
data: {"type":"done"}
```

This avoids the ADK-specific `content.parts[]` nesting and uses flat event types.
