import { useState, useEffect } from 'react'
import {
  Brain, Dna, FlaskConical, Search, Microscope,
  Pill, Activity, Zap, ExternalLink, Send, Loader2,
  CheckCircle2, XCircle, ChevronDown, ChevronUp, PenLine,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface CloudBrainPageProps {
  readonly onError: (msg: string) => void
}

/* ---------- types ---------- */

interface SkillDef {
  readonly id: string
  readonly name: string
  readonly icon: React.ElementType
  readonly color: string
  readonly description: string
  readonly tools: number
  readonly source: string
  readonly sourceUrl: string
  readonly examples: readonly string[]
  readonly categories: readonly string[]
}

interface HealthStatus {
  status: string
  skills: Record<string, boolean>
  tool_count: number
  version: string
}

interface QueryResult {
  id: string
  query: string
  skill: string
  timestamp: Date
  status: 'loading' | 'done' | 'error'
  result?: string
  error?: string
}

/* ---------- skill definitions ---------- */

const SKILLS: readonly SkillDef[] = [
  {
    id: 'tooluniverse',
    name: 'ToolUniverse',
    icon: Dna,
    color: 'text-emerald-600',
    description:
      '2,000+ scientific tools across 58 research skills. Covers UniProt, ChEMBL, PubChem, OpenTargets, FAERS, ClinicalTrials, and 440+ more databases.',
    tools: 2124,
    source: 'mims-harvard/ToolUniverse',
    sourceUrl: 'https://github.com/mims-harvard/ToolUniverse',
    examples: [
      'Look up protein P04637 in UniProt',
      'Search PubChem for aspirin compound data',
      'Find clinical trials for EGFR inhibitors',
      'Get adverse event reports for metformin',
    ],
    categories: [
      'Genomics', 'Proteomics', 'Drug Discovery', 'Clinical Trials',
      'Pharmacology', 'Oncology', 'Immunology', 'Bioinformatics',
    ],
  },
  {
    id: 'kdense',
    name: 'K-Dense AI',
    icon: Brain,
    color: 'text-violet-600',
    description:
      '170+ AI skill recipes with access to 250+ scientific databases and 500k+ Python packages. Covers bioinformatics, cheminformatics, clinical research, and lab automation.',
    tools: 170,
    source: 'K-Dense-AI/k-dense-byok',
    sourceUrl: 'https://github.com/K-Dense-AI/k-dense-byok',
    examples: [
      'Analyze gene expression in single-cell RNA-seq data',
      'Run BLAST sequence alignment',
      'Predict protein-protein interactions',
      'Design CRISPR guide RNAs',
    ],
    categories: [
      'Bioinformatics', 'Cheminformatics', 'Materials Science',
      'Lab Automation', 'Data Analysis', 'Computational Biology',
    ],
  },
  {
    id: 'biomni',
    name: 'Biomni',
    icon: Microscope,
    color: 'text-blue-600',
    description:
      '150+ tools across 59 biomedical databases. Autonomous biomedical AI agent for multi-step reasoning across scientific domains.',
    tools: 150,
    source: 'snap-stanford/biomni',
    sourceUrl: 'https://github.com/snap-stanford/biomni',
    examples: [
      'What drugs target the BRCA1 gene?',
      'Find all known protein interactions for TP53',
      'Cross-reference drug targets with clinical outcomes',
    ],
    categories: [
      'Drug-Target Interactions', 'Disease Networks', 'Multi-omics',
      'Knowledge Graphs', 'Biomedical QA',
    ],
  },
  {
    id: 'lifesci',
    name: 'Life Science Reasoning',
    icon: FlaskConical,
    color: 'text-amber-600',
    description:
      'Domain-expert AI reasoning for biology and medicine. Provides scientifically rigorous analysis and experiment design with confidence levels.',
    tools: 2,
    source: 'LabClaw Built-in',
    sourceUrl: '',
    examples: [
      'Design a Western blot experiment to confirm CRISPR knockout',
      'What controls do I need for a drug dose-response assay?',
      'Explain the PI3K/AKT/mTOR signaling pathway',
    ],
    categories: [
      'Experiment Design', 'Domain Reasoning', 'Molecular Biology',
      'Neuroscience',
    ],
  },
  {
    id: 'lifesci-mcp',
    name: 'LifeSci MCP',
    icon: Search,
    color: 'text-cyan-600',
    description:
      '5 specialized MCP servers for literature and drug research. Direct access to PubMed, bioRxiv, ChEMBL, OpenTargets, and ClinicalTrials.gov.',
    tools: 5,
    source: 'Anthropic Claude Life Sciences',
    sourceUrl: '',
    examples: [
      'Search PubMed for recent CRISPR base editing papers',
      'Find ChEMBL bioactivity data for compound CHEMBL25',
      'Get OpenTargets evidence for EGFR in lung cancer',
    ],
    categories: [
      'Literature Search', 'Drug Research', 'Clinical Data',
      'Preprints',
    ],
  },
  {
    id: 'write',
    name: 'Scientific Writing',
    icon: PenLine,
    color: 'text-rose-600',
    description:
      'AI-powered scientific writing: generate Methods, Results, Discussion sections and format citations in APA or other styles.',
    tools: 2,
    source: 'LabClaw Built-in',
    sourceUrl: '',
    examples: [
      'Write a Methods section for immunohistochemistry',
      'Draft an abstract summarizing my RNA-seq results',
      'Format this citation in APA style',
    ],
    categories: ['Paper Writing', 'Citation Formatting'],
  },
] as const

const CLOUD_BRAIN_URL = '/brain'

/* ---------- quick actions ---------- */

const QUICK_ACTIONS = [
  { label: 'Search PubMed', icon: Search, query: 'Search PubMed for recent papers on...', skill: 'lifesci-mcp' },
  { label: 'Protein Lookup', icon: Dna, query: 'Look up protein in UniProt by accession...', skill: 'tooluniverse' },
  { label: 'Drug Info', icon: Pill, query: 'Find drug information and targets for...', skill: 'tooluniverse' },
  { label: 'Experiment Design', icon: FlaskConical, query: 'Design an experiment to test...', skill: 'lifesci' },
  { label: 'Write Section', icon: PenLine, query: 'Write a Methods section for...', skill: 'write' },
  { label: 'Gene Analysis', icon: Activity, query: 'Analyze gene expression for...', skill: 'kdense' },
] as const

/* ---------- skill card ---------- */

function SkillCard({
  skill,
  healthy,
  onTryExample,
}: {
  readonly skill: SkillDef
  readonly healthy: boolean | null
  readonly onTryExample: (query: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const Icon = skill.icon

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm hover:shadow-md transition-shadow">
      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={cn('size-10 flex items-center justify-center rounded-lg bg-gray-50', skill.color)}>
              <Icon className="size-5" />
            </div>
            <div>
              <h3 className="font-bold text-gray-900 text-sm">{skill.name}</h3>
              <p className="text-xs text-gray-500">{skill.tools.toLocaleString()} tools</p>
            </div>
          </div>
          {healthy !== null && (
            <div className={cn('flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full',
              healthy
                ? 'bg-emerald-50 text-emerald-600'
                : 'bg-gray-100 text-gray-400',
            )}>
              {healthy ? <CheckCircle2 className="size-3" /> : <XCircle className="size-3" />}
              {healthy ? 'Active' : 'Offline'}
            </div>
          )}
        </div>

        {/* Description */}
        <p className="text-xs text-gray-600 leading-relaxed mb-3">{skill.description}</p>

        {/* Categories */}
        <div className="flex flex-wrap gap-1.5 mb-3">
          {skill.categories.slice(0, expanded ? undefined : 4).map((cat) => (
            <span key={cat} className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
              {cat}
            </span>
          ))}
          {!expanded && skill.categories.length > 4 && (
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-400">
              +{skill.categories.length - 4} more
            </span>
          )}
        </div>

        {/* Source */}
        {skill.sourceUrl && (
          <a
            href={skill.sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline mb-3"
          >
            <ExternalLink className="size-3" />
            {skill.source}
          </a>
        )}
        {!skill.sourceUrl && skill.source && (
          <p className="text-[11px] text-gray-400 mb-3">{skill.source}</p>
        )}

        {/* Expand toggle */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs text-primary font-medium hover:underline"
        >
          {expanded ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
          {expanded ? 'Hide examples' : 'Try examples'}
        </button>
      </div>

      {/* Examples */}
      {expanded && (
        <div className="border-t border-gray-100 px-5 py-3 bg-gray-50/50 rounded-b-xl">
          <div className="space-y-2">
            {skill.examples.map((ex) => (
              <button
                key={ex}
                onClick={() => onTryExample(ex)}
                className="w-full text-left text-xs text-gray-700 hover:text-primary hover:bg-primary/5 px-3 py-2 rounded-lg transition-colors"
              >
                <Zap className="size-3 inline mr-1.5 text-amber-500" />
                {ex}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ---------- main page ---------- */

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function CloudBrainPage({ onError }: CloudBrainPageProps) {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [connected, setConnected] = useState<boolean | null>(null)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<QueryResult[]>([])

  // Check Cloud Brain health on mount
  useEffect(() => {
    let cancelled = false

    async function checkHealth() {
      try {
        const res = await fetch(`${CLOUD_BRAIN_URL}/health`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        if (!cancelled) {
          setHealth(data)
          setConnected(true)
        }
      } catch {
        if (!cancelled) {
          setConnected(false)
        }
      }
    }

    checkHealth()
    return () => { cancelled = true }
  }, [])

  const handleSubmit = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return

    const id = `q-${Date.now()}`
    const entry: QueryResult = {
      id,
      query: trimmed,
      skill: 'auto',
      timestamp: new Date(),
      status: 'loading',
    }
    setResults((prev) => [entry, ...prev])
    setQuery('')

    try {
      const res = await fetch(`${CLOUD_BRAIN_URL}/reason`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: trimmed, domain: 'general' }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()

      setResults((prev) =>
        prev.map((r) =>
          r.id === id
            ? {
                ...r,
                status: 'done' as const,
                result: data.data?.answer ?? JSON.stringify(data.data, null, 2),
              }
            : r,
        ),
      )
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      setResults((prev) =>
        prev.map((r) =>
          r.id === id ? { ...r, status: 'error' as const, error: msg } : r,
        ),
      )
    }
  }

  const handleTryExample = (example: string) => {
    if (connected) {
      handleSubmit(example)
    } else {
      setQuery(example)
    }
  }

  const totalTools = SKILLS.reduce((sum, s) => sum + s.tools, 0)

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Hero / Status */}
      <div className="bg-gradient-to-br from-violet-50 via-white to-cyan-50 border border-gray-200 rounded-xl p-6 shadow-sm">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="size-10 flex items-center justify-center bg-violet-100 rounded-lg">
                <Brain className="size-6 text-violet-600" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-900">Cloud Brain</h2>
                <p className="text-xs text-gray-500">
                  Unified scientific AI gateway
                </p>
              </div>
            </div>
            <p className="text-sm text-gray-600 max-w-lg mt-2">
              One API to access {totalTools.toLocaleString()}+ scientific tools. Search literature,
              look up proteins, analyze drugs, design experiments, and generate scientific text
              without installing any specialized software.
            </p>
          </div>

          {/* Connection status */}
          <div className={cn(
            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium',
            connected === true
              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              : connected === false
                ? 'bg-amber-50 text-amber-700 border border-amber-200'
                : 'bg-gray-50 text-gray-500 border border-gray-200',
          )}>
            {connected === null && <Loader2 className="size-4 animate-spin" />}
            {connected === true && <CheckCircle2 className="size-4" />}
            {connected === false && <XCircle className="size-4" />}
            {connected === null && 'Checking...'}
            {connected === true && `Connected (${health?.tool_count?.toLocaleString() ?? '?'} tools)`}
            {connected === false && 'Not Connected'}
          </div>
        </div>

        {/* Stats row */}
        {health && connected && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5">
            <div className="bg-white/70 border border-gray-200/50 rounded-lg px-4 py-3 text-center">
              <p className="text-lg font-bold text-gray-900">{health.tool_count.toLocaleString()}</p>
              <p className="text-[10px] text-gray-500 uppercase tracking-wide font-medium">Tools Available</p>
            </div>
            <div className="bg-white/70 border border-gray-200/50 rounded-lg px-4 py-3 text-center">
              <p className="text-lg font-bold text-gray-900">{Object.keys(health.skills).length}</p>
              <p className="text-[10px] text-gray-500 uppercase tracking-wide font-medium">Active Skills</p>
            </div>
            <div className="bg-white/70 border border-gray-200/50 rounded-lg px-4 py-3 text-center">
              <p className="text-lg font-bold text-emerald-600">
                {Object.values(health.skills).filter(Boolean).length}/{Object.keys(health.skills).length}
              </p>
              <p className="text-[10px] text-gray-500 uppercase tracking-wide font-medium">Skills Healthy</p>
            </div>
            <div className="bg-white/70 border border-gray-200/50 rounded-lg px-4 py-3 text-center">
              <p className="text-lg font-bold text-gray-900">v{health.version}</p>
              <p className="text-[10px] text-gray-500 uppercase tracking-wide font-medium">Version</p>
            </div>
          </div>
        )}

        {/* Offline notice */}
        {connected === false && (
          <div className="mt-4 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-800">
            <p className="font-medium">Cloud Brain is not running</p>
            <p className="text-xs text-amber-600 mt-1">
              Start it with <code className="bg-amber-100 px-1.5 py-0.5 rounded text-[11px] font-mono">labclaw brain --port 18802</code> to
              enable live tool execution. The skill catalog below shows what is available when connected.
            </p>
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div>
        <h3 className="text-sm font-bold text-gray-900 mb-3">Quick Actions</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {QUICK_ACTIONS.map((action) => {
            const Icon = action.icon
            return (
              <button
                key={action.label}
                onClick={() => handleTryExample(action.query)}
                className="flex flex-col items-center gap-2 p-3 bg-white border border-gray-200 rounded-xl hover:border-primary/30 hover:shadow-sm transition-all text-center group"
              >
                <div className="size-8 flex items-center justify-center rounded-lg bg-gray-50 group-hover:bg-primary/10 transition-colors">
                  <Icon className="size-4 text-gray-500 group-hover:text-primary transition-colors" />
                </div>
                <span className="text-[11px] font-medium text-gray-700 group-hover:text-primary leading-tight">{action.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Query input (only when connected) */}
      {connected && (
        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleSubmit(query)
            }}
            className="flex gap-3"
          >
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask Cloud Brain a scientific question..."
              className="flex-1 px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/30"
            />
            <button
              type="submit"
              disabled={!query.trim()}
              className="flex items-center gap-2 px-5 py-2.5 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Send className="size-4" />
              Ask
            </button>
          </form>
        </div>
      )}

      {/* Query Results */}
      {results.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-bold text-gray-900">Recent Queries</h3>
          {results.map((r) => (
            <div key={r.id} className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="flex items-start gap-3">
                <div className="size-8 flex items-center justify-center rounded-lg bg-violet-50 shrink-0 mt-0.5">
                  <Brain className="size-4 text-violet-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900">{r.query}</p>
                  <p className="text-[10px] text-gray-400 mt-0.5">
                    {r.timestamp.toLocaleTimeString()}
                  </p>
                  {r.status === 'loading' && (
                    <div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
                      <Loader2 className="size-3 animate-spin" />
                      Processing...
                    </div>
                  )}
                  {r.status === 'done' && r.result && (
                    <div className="mt-2 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap bg-gray-50 rounded-lg p-3">
                      {r.result}
                    </div>
                  )}
                  {r.status === 'error' && (
                    <div className="mt-2 text-sm text-red-600 bg-red-50 rounded-lg p-3">
                      {r.error}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* AI Skills Grid */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-gray-900">Available AI Skills</h3>
          <span className="text-xs text-gray-400">
            {SKILLS.length} skill providers / {totalTools.toLocaleString()}+ total tools
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {SKILLS.map((skill) => (
            <SkillCard
              key={skill.id}
              skill={skill}
              healthy={
                health?.skills[skill.id] !== undefined
                  ? health.skills[skill.id]
                  : null
              }
              onTryExample={handleTryExample}
            />
          ))}
        </div>
      </div>

      {/* API Reference hint */}
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-center">
        <p className="text-xs text-gray-500">
          Cloud Brain API:{' '}
          <code className="bg-white px-2 py-0.5 rounded border border-gray-200 text-[11px] font-mono">
            POST /brain/execute
          </code>{' '}
          <code className="bg-white px-2 py-0.5 rounded border border-gray-200 text-[11px] font-mono">
            POST /brain/reason
          </code>{' '}
          <code className="bg-white px-2 py-0.5 rounded border border-gray-200 text-[11px] font-mono">
            POST /brain/write
          </code>{' '}
          <code className="bg-white px-2 py-0.5 rounded border border-gray-200 text-[11px] font-mono">
            GET /brain/tools
          </code>
        </p>
      </div>
    </div>
  )
}
