import { useState, useEffect } from 'react'
import {
  Brain, Dna, FlaskConical, Search, Microscope,
  Zap, ExternalLink, Loader2,
  ChevronDown, ChevronUp, PenLine, X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { CloudBrainChat } from '@/components/chat/CloudBrainChat'

interface CloudBrainPageProps {
  readonly onError: (msg: string) => void
  /** @internal test-only: bypass async health check */
  readonly __testConnected?: boolean | null
  /** @internal test-only: bypass async health check */
  readonly __testHealth?: HealthStatus | null
}

/* ---------- types ---------- */

interface SkillDef {
  readonly id: string
  readonly name: string
  readonly icon: React.ElementType
  readonly color: string
  readonly bg: string
  readonly tagBg: string
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

/* ---------- skill definitions ---------- */

const SKILLS: readonly SkillDef[] = [
  {
    id: 'tooluniverse',
    name: 'ToolUniverse',
    icon: Dna,
    color: 'text-emerald-600',
    bg: 'bg-emerald-50',
    tagBg: 'bg-emerald-50 text-emerald-700',
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
    bg: 'bg-violet-50',
    tagBg: 'bg-violet-50 text-violet-700',
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
    bg: 'bg-blue-50',
    tagBg: 'bg-blue-50 text-blue-700',
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
    bg: 'bg-amber-50',
    tagBg: 'bg-amber-50 text-amber-700',
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
    bg: 'bg-cyan-50',
    tagBg: 'bg-cyan-50 text-cyan-700',
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
    bg: 'bg-rose-50',
    tagBg: 'bg-rose-50 text-rose-700',
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

/* ---------- skill card ---------- */

function SkillCard({
  skill,
  healthy,
}: {
  readonly skill: SkillDef
  readonly healthy: boolean | null
}) {
  const [expanded, setExpanded] = useState(false)
  const Icon = skill.icon

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm hover:shadow-md transition-shadow">
      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={cn('size-10 flex items-center justify-center rounded-lg', skill.bg, skill.color)}>
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
                : 'bg-gray-100 text-gray-500',
            )}>
              <span className={cn('size-2 rounded-full', healthy ? 'bg-emerald-500' : 'bg-gray-400')} />
              {healthy ? 'Active' : 'Offline'}
            </div>
          )}
        </div>

        {/* Description */}
        <p className="text-xs text-gray-600 leading-relaxed mb-3">{skill.description}</p>

        {/* Categories */}
        <div className="flex flex-wrap gap-1.5 mb-3">
          {skill.categories.slice(0, expanded ? undefined : 4).map((cat) => (
            <span key={cat} className={cn('text-[10px] font-medium px-2 py-0.5 rounded-full', skill.tagBg)}>
              {cat}
            </span>
          ))}
          {!expanded && skill.categories.length > 4 && (
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-400">
              +{skill.categories.length - 4} more
            </span>
          )}
        </div>

        {/* Example preview */}
        <div className={cn('rounded-lg px-3 py-2 mb-3', skill.bg)}>
          <p className="text-[11px] text-gray-500 font-medium mb-1">Example</p>
          <p className="text-xs text-gray-700 italic">&ldquo;{skill.examples[0]}&rdquo;</p>
        </div>

        {/* Source + Expand row */}
        <div className="flex items-center justify-between">
          <div>
            {skill.sourceUrl ? (
              <a
                href={skill.sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline"
              >
                <ExternalLink className="size-3" />
                {skill.source}
              </a>
            ) : skill.source ? (
              <p className="text-[11px] text-gray-400">{skill.source}</p>
            ) : null}
          </div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-xs text-primary font-medium hover:underline"
          >
            {expanded ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
            {expanded ? 'Less' : 'More examples'}
          </button>
        </div>
      </div>

      {/* Expanded examples */}
      {expanded && (
        <div className="border-t border-gray-100 px-5 py-3 bg-gray-50/50 rounded-b-xl">
          <div className="space-y-1.5">
            {skill.examples.slice(1).map((ex) => (
              <p
                key={ex}
                className="w-full text-left text-xs text-gray-500 px-3 py-2 rounded-lg"
              >
                <Zap className="size-3 inline mr-1.5 text-amber-500" />
                {ex}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ---------- main page ---------- */

export function CloudBrainPage({ onError: _onError, __testConnected, __testHealth }: CloudBrainPageProps) {
  const [health, setHealth] = useState<HealthStatus | null>(__testHealth ?? null)
  const [connected, setConnected] = useState<boolean | null>(__testConnected ?? null)
  const [searchQuery, setSearchQuery] = useState('')

  // Filter skills based on search query
  const filteredSkills = searchQuery.trim()
    ? SKILLS.filter(skill =>
        skill.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        skill.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        skill.categories.some(cat => cat.toLowerCase().includes(searchQuery.toLowerCase())) ||
        skill.examples.some(ex => ex.toLowerCase().includes(searchQuery.toLowerCase())),
      )
    : SKILLS

  // Check Cloud Brain health on mount (skip if test props provided)
  useEffect(() => {
    if (__testConnected !== undefined) return
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
  }, [__testConnected])

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
            {connected === true && (
              <span className="size-2.5 rounded-full bg-emerald-500 animate-pulse" />
            )}
            {connected === false && (
              <span className="size-2.5 rounded-full bg-amber-500" />
            )}
            {connected === null && 'Checking...'}
            {connected === true && `Connected (${health?.tool_count?.toLocaleString() ?? '?'} tools)`}
            {connected === false && 'Setup Required'}
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
          <div className="mt-4 bg-white border border-gray-200 rounded-lg px-4 py-3 text-sm text-gray-700">
            <p className="font-semibold text-gray-900">Cloud Brain is offline</p>
            <p className="text-xs text-gray-500 mt-1">
              Start it with{' '}
              <code className="bg-gray-100 px-1.5 py-0.5 rounded text-[11px] font-mono text-gray-700">
                labclaw brain --port 18802
              </code>{' '}
              to enable live tool execution. Browse the skill catalog below to see all available capabilities.
            </p>
          </div>
        )}
      </div>

      {/* Chat Interface */}
      <CloudBrainChat connected={connected ?? false} />

      {/* AI Skills Grid */}
      <div>
        <div className="flex items-center justify-between mb-3 gap-4">
          <div className="flex items-center gap-3">
            <h3 className="text-sm font-bold text-gray-900">Available AI Skills</h3>
            <span className="text-xs text-gray-400">
              {filteredSkills.length === SKILLS.length
                ? `${SKILLS.length} skill providers / ${totalTools.toLocaleString()}+ total tools`
                : `${filteredSkills.length} of ${SKILLS.length} skills`}
            </span>
          </div>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-gray-400" />
            <input
              type="text"
              aria-label="Search AI skills"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search tools..."
              className="pl-8 pr-8 py-1.5 text-xs bg-white border border-gray-200 rounded-lg w-48 focus:outline-none focus:border-primary"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <X className="size-3" />
              </button>
            )}
          </div>
        </div>

        {/* Search empty state */}
        {filteredSkills.length === 0 && searchQuery && (
          <div className="text-center py-8 text-gray-500 bg-white border border-gray-200 rounded-xl">
            <Search className="size-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No skills found for "{searchQuery}"</p>
            <button
              onClick={() => setSearchQuery('')}
              className="text-primary text-sm mt-2 hover:underline"
            >
              Clear search
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredSkills.map((skill) => (
            <SkillCard
              key={skill.id}
              skill={skill}
              healthy={
                health?.skills[skill.id] !== undefined
                  ? health.skills[skill.id]
                  : null
              }
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
