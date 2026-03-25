import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart3, FileText, Package, Store, Clock,
  TrendingUp, AlertTriangle, Beaker, Wrench, Box, Brain,
  Activity, ShieldCheck, PieChart, Users, Search,
} from 'lucide-react'
import { analytics, documents as docApi, inventory as invApi } from '@/lib/api'
import type { DashboardStats, DocumentStats, Document, InventoryItem } from '@/lib/api'
import { formatEnum } from '@/lib/utils'

interface AnalyticsPageProps {
  readonly onError: (msg: string) => void
}

type TabValue = 'overview' | 'vendors' | 'documents' | 'inventory'

const TABS: { readonly value: TabValue; readonly label: string; readonly icon: typeof BarChart3 }[] = [
  { value: 'overview', label: 'Lab Intelligence', icon: Brain },
  { value: 'vendors', label: 'Vendors', icon: Store },
  { value: 'documents', label: 'Documents', icon: FileText },
  { value: 'inventory', label: 'Inventory', icon: Package },
]

// Vendor category mapping
const REAGENT_VENDORS = new Set([
  'Sigma-Aldrich', 'Millipore Sigma', 'EMD Millipore Corporation', 'MilliporeSigma Corporation',
  'SIGMA-ALDRICH', 'Sigma Aldrich', 'Sigma Aldrich, Inc.', 'Sigma-Aldrich, Inc.',
  'abcam', 'Bio-Rad Laboratories, Inc.', 'BIO-RAD', 'BioLegend Inc', 'Cell Signaling Technology',
  'Addgene', 'invitrogen\u2122 by life technologies\u2122', 'Invitrogen', 'invitrogen by life technologies',
  'life technologies', 'Life Technologies Corpora', 'Miltenyi Biotec', 'MedChemExpress LLC',
  'MedChem Express LLC', 'Boston BioProducts Inc.', 'Biohippo Inc.', 'G-Biosciences / Geno Technology, Inc.',
  'ABclonal Technology', 'Alta Biotech, LLC', 'Boster Biological Technology',
  'Jackson ImmunoResearch Laboratories, Inc.', 'GOLDBIO', 'Qiagen, LLC', 'Targetmol Chemicals Inc.',
  'GeminiBio', 'Cell Biologics, Inc', 'ALSTEM, Inc.', 'Takara Bio Inc.', 'PackGene',
  'ACROS ORGANICS', 'Alkali Scientific', 'Proteintech Group, Inc.', 'Santa Cruz Biotechnology, Inc',
  'Kyfora Bio', 'LAMDA BIOTECH', 'Pluriselect usa, Inc.', 'PluriSelect usa, Inc.',
  'RayBiotech Life', 'Enzo Life Sciences, Inc.', 'Creative Biolabs Inc.', 'Creative Biolabs',
  'Growcells, Inc.', 'ATCC', 'Viral Vector Facility VVF', 'Brain Research Laboratories',
  'THERMO FISHER SCIENTIFIC CHEMICALS INC.', 'Thermo Fisher Scientific Chemicals Inc.',
  'ThermoFisher SCIENTIFIC', 'FISHER SCIENTIFIC CO', 'FISHER SCIENTIFIC', 'FISHER SCIENTIFIC CO.',
  'Fisher Scientific Company', 'Fisher Scientific Technology Inc.',
])

const EQUIPMENT_VENDORS = new Set([
  'THORLABS Inc.', 'Agilent Technologies', 'A-M Systems', 'Stoelting', 'Harvard Apparatus',
  'Nikon Instruments Consignment', 'Nikon', 'PerkinElmer, Inc.', 'Eppendorf North America, Inc.',
  'Amuza Inc.', 'IMEC VZW', 'RealSense', 'DRUMMOND SCIENT', 'TED PELLA, INC.',
  'B&H Photo & Video', 'Iwai North America Inc.', 'DigiKey', 'DigiKey Electronics', 'Digikay', 'Newark',
])

const CONFIDENCE_BUCKETS = [
  { label: '0-50%', range: [0, 0.5] as const, color: 'bg-red-500' },
  { label: '50-60%', range: [0.5, 0.6] as const, color: 'bg-orange-500' },
  { label: '60-70%', range: [0.6, 0.7] as const, color: 'bg-amber-500' },
  { label: '70-80%', range: [0.7, 0.8] as const, color: 'bg-yellow-500' },
  { label: '80-85%', range: [0.8, 0.85] as const, color: 'bg-lime-500' },
  { label: '85-90%', range: [0.85, 0.9] as const, color: 'bg-green-500' },
  { label: '90-95%', range: [0.9, 0.95] as const, color: 'bg-emerald-500' },
  { label: '95-100%', range: [0.95, 1.01] as const, color: 'bg-teal-600' },
]

// ----------------------------------------------------------------
// Insight banner — bold headline + supporting text
// ----------------------------------------------------------------
function Insight({ text, variant = 'info' }: { text: string; variant?: 'info' | 'warn' | 'good' | 'bad' }) {
  const colors = {
    info: 'bg-primary/5 border-primary/20 text-primary',
    warn: 'bg-amber-50 border-amber-200 text-amber-700',
    good: 'bg-emerald-50 border-emerald-200 text-emerald-700',
    bad: 'bg-red-50 border-red-200 text-red-700',
  }
  return (
    <div className={`text-sm font-semibold px-4 py-2.5 rounded-lg border ${colors[variant]}`}>
      {text}
    </div>
  )
}

// ----------------------------------------------------------------
// Horizontal bar row
// ----------------------------------------------------------------
function BarRow({ label, count, max, index, suffix }: {
  label: string; count: number; max: number; index: number; suffix?: string
}) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0
  const opacities = ['', '/80', '/60', '/40', '/20']
  const opacity = opacities[Math.min(index, opacities.length - 1)]
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-end">
        <span className="text-sm text-[var(--foreground)] font-semibold truncate mr-2">{label}</span>
        <span className="text-xs text-[var(--muted-foreground)] font-mono shrink-0">{count}{suffix ? ` ${suffix}` : ''}</span>
      </div>
      <div className="h-2 w-full bg-[var(--card)] rounded-full overflow-hidden border border-primary/5">
        <div
          className={`h-full bg-primary${opacity} rounded-full transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

// ================================================================
// OVERVIEW TAB — "Lab Intelligence"
// No duplicate stats cards. Unique insights only.
// ================================================================
function OverviewTab({ docs, docStats }: {
  docs: Document[]
  docStats: DocumentStats | undefined
}) {
  const [now] = useState(() => Date.now())
  const confidences = useMemo(
    () => docs.filter(d => d.extraction_confidence != null).map(d => d.extraction_confidence!),
    [docs],
  )
  const totalDocs = docStats?.total_documents ?? docs.length
  const highConf = confidences.filter(c => c > 0.8).length
  const accuracy = confidences.length > 0 ? ((highConf / confidences.length) * 100).toFixed(1) : '0'
  const meanConf = confidences.length > 0
    ? (confidences.reduce((a, b) => a + b, 0) / confidences.length * 100).toFixed(1)
    : '0'

  // Processing status breakdown
  const statusMap = docStats?.by_status ?? {}
  const approvedCount = statusMap['approved'] ?? 0
  const reviewCount = statusMap['needs_review'] ?? 0
  const rejectedCount = statusMap['rejected'] ?? 0
  const statusTotal = approvedCount + reviewCount + rejectedCount
  const approvedPct = statusTotal > 0 ? Math.round((approvedCount / statusTotal) * 100) : 0
  const reviewPct = statusTotal > 0 ? Math.round((reviewCount / statusTotal) * 100) : 0
  const rejectedPct = statusTotal > 0 ? Math.round((rejectedCount / statusTotal) * 100) : 0

  // Avg confidence by vendor (find lowest)
  const vendorConfidence = useMemo(() => {
    const map: Record<string, { sum: number; count: number }> = {}
    for (const d of docs) {
      const v = d.vendor_name
      const c = d.extraction_confidence
      if (v && c != null) {
        if (!map[v]) map[v] = { sum: 0, count: 0 }
        map[v].sum += c
        map[v].count += 1
      }
    }
    return Object.entries(map)
      .map(([name, { sum, count }]) => ({ name, avg: sum / count, count }))
      .filter(v => v.count >= 2) // need at least 2 docs for meaningful average
      .sort((a, b) => a.avg - b.avg) // lowest first
  }, [docs])

  const worstVendor = vendorConfidence[0]
  const bestVendor = vendorConfidence.length > 0 ? vendorConfidence[vendorConfidence.length - 1] : undefined

  // Oldest pending review
  const oldestPending = useMemo(() => {
    const pending = docs
      .filter(d => d.status === 'needs_review' && d.created_at)
      .sort((a, b) => (a.created_at ?? '').localeCompare(b.created_at ?? ''))
    return pending[0]
  }, [docs])

  const oldestDaysAgo = useMemo(() => {
    if (!oldestPending?.created_at) return 0
    return Math.floor((now - new Date(oldestPending.created_at).getTime()) / (1000 * 60 * 60 * 24))
  }, [oldestPending, now])

  // Confidence sparkline — mini histogram for inline display
  const sparkline = useMemo(() => {
    return CONFIDENCE_BUCKETS.map(bucket => ({
      ...bucket,
      count: confidences.filter(c => c >= bucket.range[0] && c < bucket.range[1]).length,
    }))
  }, [confidences])
  const sparkMax = Math.max(...sparkline.map(b => b.count), 1)

  return (
    <div className="space-y-6">
      {/* Headline insights */}
      <div className="space-y-2">
        <Insight
          text={`${accuracy}% of ${totalDocs} documents extracted with >80% confidence — ${
            parseFloat(accuracy) >= 90 ? 'your pipeline is reliable' : 'review low-confidence documents below'
          }`}
          variant={parseFloat(accuracy) >= 90 ? 'good' : 'warn'}
        />
        {reviewCount > 0 && (
          <Insight
            text={`${reviewCount} document${reviewCount > 1 ? 's' : ''} pending review${
              oldestDaysAgo > 0 ? ` — oldest is from ${oldestDaysAgo} day${oldestDaysAgo > 1 ? 's' : ''} ago` : ''
            }`}
            variant={oldestDaysAgo > 7 ? 'bad' : 'warn'}
          />
        )}
        {worstVendor && (
          <Insight
            text={`${worstVendor.name} has the lowest AI accuracy (${(worstVendor.avg * 100).toFixed(0)}%) across ${worstVendor.count} docs — consider manual review`}
            variant={worstVendor.avg < 0.8 ? 'bad' : 'warn'}
          />
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* AI Performance card */}
        <div className="bg-[var(--card)] border border-primary/10 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <ShieldCheck className="size-5 text-primary" />
            <h3 className="text-[var(--foreground)] text-base font-bold">AI Performance</h3>
          </div>
          <div className="space-y-4">
            <div>
              <div className="text-4xl font-bold text-primary tracking-tight">{accuracy}%</div>
              <div className="text-xs text-[var(--muted-foreground)] mt-1">accuracy across {totalDocs} documents (confidence &gt; 0.8)</div>
            </div>
            <div className="flex justify-between items-center text-sm border-t border-primary/10 pt-3">
              <span className="text-[var(--muted-foreground)]">Mean confidence</span>
              <span className="font-semibold text-[var(--foreground)]">{meanConf}%</span>
            </div>
            {bestVendor && (
              <div className="flex justify-between items-center text-sm">
                <span className="text-[var(--muted-foreground)]">Best vendor accuracy</span>
                <span className="font-semibold text-emerald-600">{bestVendor.name} ({(bestVendor.avg * 100).toFixed(0)}%)</span>
              </div>
            )}
            {/* Mini sparkline */}
            <div className="border-t border-primary/10 pt-3">
              <h4 className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider mb-2">Confidence Distribution</h4>
              <div className="flex items-end gap-1 h-12">
                {sparkline.map(bucket => (
                  <div key={bucket.label} className="flex-1 flex flex-col items-center gap-0.5">
                    <div
                      className={`w-full ${bucket.color} rounded-t transition-all duration-500`}
                      style={{ height: `${sparkMax > 0 ? (bucket.count / sparkMax) * 100 : 0}%`, minHeight: bucket.count > 0 ? '2px' : '0' }}
                    />
                  </div>
                ))}
              </div>
              <div className="flex gap-1 mt-0.5">
                {sparkline.map(bucket => (
                  <div key={bucket.label} className="flex-1 text-center text-[8px] text-[var(--muted-foreground)]">
                    {bucket.count > 0 ? bucket.count : ''}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Processing Status — pie-like breakdown */}
        <div className="bg-[var(--card)] border border-primary/10 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <PieChart className="size-5 text-primary" />
            <h3 className="text-[var(--foreground)] text-base font-bold">Processing Status</h3>
          </div>
          {statusTotal > 0 ? (
            <div className="space-y-5">
              {/* Visual bar */}
              <div className="h-4 w-full rounded-full overflow-hidden flex">
                {approvedPct > 0 && (
                  <div className="h-full bg-emerald-500 transition-all duration-500" style={{ width: `${approvedPct}%` }} />
                )}
                {reviewPct > 0 && (
                  <div className="h-full bg-amber-500 transition-all duration-500" style={{ width: `${reviewPct}%` }} />
                )}
                {rejectedPct > 0 && (
                  <div className="h-full bg-red-500 transition-all duration-500" style={{ width: `${rejectedPct}%` }} />
                )}
              </div>
              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                    <span className="text-[var(--foreground)] font-medium">Approved</span>
                  </div>
                  <span className="font-semibold text-[var(--foreground)]">{approvedCount} <span className="text-[var(--muted-foreground)] font-normal text-xs">({approvedPct}%)</span></span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                    <span className="text-[var(--foreground)] font-medium">Needs Review</span>
                  </div>
                  <span className="font-semibold text-[var(--foreground)]">{reviewCount} <span className="text-[var(--muted-foreground)] font-normal text-xs">({reviewPct}%)</span></span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
                    <span className="text-[var(--foreground)] font-medium">Rejected</span>
                  </div>
                  <span className="font-semibold text-[var(--foreground)]">{rejectedCount} <span className="text-[var(--muted-foreground)] font-normal text-xs">({rejectedPct}%)</span></span>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-[var(--muted-foreground)] py-4">No status data yet</p>
          )}
        </div>

        {/* Extraction Quality — confidence by vendor */}
        <div className="bg-[var(--card)] border border-primary/10 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="size-5 text-primary" />
            <h3 className="text-[var(--foreground)] text-base font-bold">Extraction Quality</h3>
          </div>
          <p className="text-xs text-[var(--muted-foreground)] mb-4">Avg confidence by vendor (lowest first — needs attention)</p>
          <div className="space-y-3">
            {vendorConfidence.slice(0, 8).map((v, i) => {
              const pct = (v.avg * 100).toFixed(0)
              const color = v.avg >= 0.9 ? 'text-emerald-600' : v.avg >= 0.8 ? 'text-amber-600' : 'text-red-500'
              return (
                <div key={v.name} className="flex items-center justify-between text-sm">
                  <span className="text-[var(--foreground)] truncate mr-2 font-medium">{i + 1}. {v.name}</span>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`font-mono font-semibold ${color}`}>{pct}%</span>
                    <span className="text-[10px] text-[var(--muted-foreground)]">({v.count} docs)</span>
                  </div>
                </div>
              )
            })}
            {vendorConfidence.length === 0 && (
              <p className="text-sm text-[var(--muted-foreground)] py-4">Need at least 2 docs per vendor for analysis</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ================================================================
// VENDORS TAB — enhanced with diversity insight
// ================================================================
function VendorsTab({ docs, navigate }: { docs: Document[]; navigate: ReturnType<typeof useNavigate> }) {
  const [filter, setFilter] = useState<'all' | 'reagents' | 'equipment' | 'supplies'>('all')

  const vendorData = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const d of docs) {
      const v = d.vendor_name
      if (v) counts[v] = (counts[v] ?? 0) + 1
    }
    const all = Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([name, count]) => {
        let category: 'reagents' | 'equipment' | 'supplies' = 'supplies'
        if (REAGENT_VENDORS.has(name)) category = 'reagents'
        else if (EQUIPMENT_VENDORS.has(name)) category = 'equipment'
        return { name, count, category }
      })
    return all
  }, [docs])

  const top20 = useMemo(() => vendorData.slice(0, 20), [vendorData])
  const max = top20[0]?.count ?? 1

  const filteredVendors = useMemo(
    () => filter === 'all' ? vendorData : vendorData.filter(v => v.category === filter),
    [vendorData, filter],
  )

  const categoryCounts = useMemo(() => ({
    reagents: vendorData.filter(v => v.category === 'reagents').length,
    equipment: vendorData.filter(v => v.category === 'equipment').length,
    supplies: vendorData.filter(v => v.category === 'supplies').length,
  }), [vendorData])

  // Vendor diversity analysis
  const diversity = useMemo(() => {
    const totalDocs = vendorData.reduce((s, v) => s + v.count, 0)
    const top3Docs = vendorData.slice(0, 3).reduce((s, v) => s + v.count, 0)
    const top3Pct = totalDocs > 0 ? Math.round((top3Docs / totalDocs) * 100) : 0
    const top3Names = vendorData.slice(0, 3).map(v => v.name)
    return { totalVendors: vendorData.length, totalDocs, top3Docs, top3Pct, top3Names }
  }, [vendorData])

  const filterButtons: { key: typeof filter; label: string; icon: typeof Beaker }[] = [
    { key: 'all', label: 'All', icon: Users },
    { key: 'reagents', label: 'Reagents', icon: Beaker },
    { key: 'equipment', label: 'Equipment', icon: Wrench },
    { key: 'supplies', label: 'Supplies', icon: Box },
  ]

  return (
    <div className="space-y-6">
      {/* Headline insights */}
      <div className="space-y-2">
        <Insight
          text={`Your top 3 vendors (${diversity.top3Names.join(', ')}) account for ${diversity.top3Pct}% of all documents — ${
            diversity.top3Pct > 50 ? 'high supplier concentration risk' : 'healthy vendor diversity'
          }`}
          variant={diversity.top3Pct > 50 ? 'warn' : 'good'}
        />
        <Insight
          text={`${diversity.totalVendors} unique vendors across ${diversity.totalDocs} documents — ${categoryCounts.reagents} reagent, ${categoryCounts.equipment} equipment, ${categoryCounts.supplies} general supply`}
          variant="info"
        />
      </div>

      {/* Vendor Diversity card */}
      <div className="bg-[var(--card)] border border-primary/10 rounded-xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="size-5 text-primary" />
          <h3 className="text-[var(--foreground)] text-base font-bold">Vendor Concentration</h3>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-4 bg-[var(--background)] rounded-lg">
            <div className="text-2xl font-bold text-[var(--foreground)]">{diversity.totalVendors}</div>
            <div className="text-[11px] text-[var(--muted-foreground)] font-medium mt-1">Total Vendors</div>
          </div>
          <div className="text-center p-4 bg-[var(--background)] rounded-lg">
            <div className={`text-2xl font-bold ${diversity.top3Pct > 50 ? 'text-amber-600' : 'text-emerald-600'}`}>{diversity.top3Pct}%</div>
            <div className="text-[11px] text-[var(--muted-foreground)] font-medium mt-1">Top 3 Concentration</div>
          </div>
          <div className="text-center p-4 bg-[var(--background)] rounded-lg">
            <div className="text-2xl font-bold text-[var(--foreground)]">{diversity.totalDocs}</div>
            <div className="text-[11px] text-[var(--muted-foreground)] font-medium mt-1">Total Documents</div>
          </div>
        </div>
      </div>

      {/* Top 20 */}
      <div className="bg-[var(--card)] border border-primary/10 rounded-xl p-6 shadow-sm">
        <div className="mb-6">
          <h3 className="text-[var(--foreground)] text-base font-bold flex items-center gap-2">
            <BarChart3 className="size-5 text-primary" />
            Top 20 Vendors by Document Count
          </h3>
          <p className="text-xs text-[var(--muted-foreground)] mt-1">Extracted from packing lists, invoices, and shipping labels</p>
        </div>
        <div className="space-y-3">
          {top20.map(({ name, count }, i) => (
            <BarRow key={name} label={name} count={count} max={max} index={Math.min(i, 4)} suffix="docs" />
          ))}
        </div>
      </div>

      {/* Vendor directory */}
      <div className="bg-[var(--card)] border border-primary/10 rounded-xl p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-[var(--foreground)] text-base font-bold">Vendor Directory</h3>
            <p className="text-xs text-[var(--muted-foreground)] mt-0.5">All {vendorData.length} suppliers identified across documents</p>
          </div>
          <div className="flex gap-2">
            {filterButtons.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`text-xs px-3 py-1 rounded-full font-medium transition-colors ${
                  filter === key
                    ? 'bg-primary/10 text-primary'
                    : 'bg-[var(--background)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {filteredVendors.map(v => (
            <button
              key={v.name}
              onClick={() => navigate(`/documents?vendor=${encodeURIComponent(v.name)}`)}
              className="inline-block px-2.5 py-1 rounded-md bg-primary/5 text-primary text-[13px] font-medium hover:bg-primary/10 hover:underline cursor-pointer transition-colors"
              title={`${v.count} document${v.count > 1 ? 's' : ''} — click to view`}
            >
              {v.name} <span className="text-primary/50 ml-1">{v.count}</span>
            </button>
          ))}
          {filteredVendors.length === 0 && (
            <p className="text-sm text-[var(--muted-foreground)] py-4">No vendors in this category</p>
          )}
        </div>
      </div>
    </div>
  )
}

// ================================================================
// DOCUMENTS TAB — confidence histogram + problem docs + extraction log
// No doc type pie (Dashboard has it)
// ================================================================
function DocumentsTab({ docs }: { docs: Document[] }) {
  const confidences = useMemo(
    () => docs.filter(d => d.extraction_confidence != null).map(d => d.extraction_confidence!),
    [docs],
  )

  // Confidence histogram
  const histogram = useMemo(() => {
    return CONFIDENCE_BUCKETS.map(bucket => ({
      ...bucket,
      count: confidences.filter(c => c >= bucket.range[0] && c < bucket.range[1]).length,
    }))
  }, [confidences])
  const histMax = Math.max(...histogram.map(b => b.count), 1)

  const meanConf = confidences.length > 0
    ? (confidences.reduce((a, b) => a + b, 0) / confidences.length * 100).toFixed(1)
    : '0'
  const highConfCount = confidences.filter(c => c >= 0.9).length
  const lowConfCount = confidences.filter(c => c < 0.8).length

  // Problem documents — lowest confidence
  const problemDocs = useMemo(() => {
    return [...docs]
      .filter(d => d.extraction_confidence != null && d.extraction_confidence < 0.8)
      .sort((a, b) => (a.extraction_confidence ?? 0) - (b.extraction_confidence ?? 0))
      .slice(0, 15)
  }, [docs])

  // Recent extraction log
  const recentDocs = useMemo(() => {
    return [...docs]
      .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''))
      .slice(0, 20)
  }, [docs])

  return (
    <div className="space-y-6">
      {/* Headline insights */}
      <div className="space-y-2">
        <Insight
          text={`${highConfCount} of ${confidences.length} documents have >90% confidence (mean: ${meanConf}%) — ${
            parseFloat(meanConf) >= 85 ? 'extraction quality is strong' : 'consider reprocessing low-confidence docs'
          }`}
          variant={parseFloat(meanConf) >= 85 ? 'good' : 'warn'}
        />
        {lowConfCount > 0 && (
          <Insight
            text={`${lowConfCount} document${lowConfCount > 1 ? 's' : ''} below 80% confidence — flagged for review below`}
            variant="bad"
          />
        )}
      </div>

      {/* Confidence histogram */}
      <div className="bg-[var(--card)] border border-primary/10 rounded-xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-6">
          <BarChart3 className="size-5 text-primary" />
          <h3 className="text-[var(--foreground)] text-base font-bold">Confidence Distribution</h3>
          <span className="text-xs text-[var(--muted-foreground)] ml-auto">{confidences.length} documents with confidence scores</span>
        </div>
        <div className="space-y-2.5">
          {histogram.map(bucket => (
            <div key={bucket.label} className="flex items-center gap-3">
              <span className="text-xs text-[var(--muted-foreground)] w-14 shrink-0 font-mono">{bucket.label}</span>
              <div className="flex-1 h-5 bg-[var(--background)] rounded-full overflow-hidden">
                <div
                  className={`h-full ${bucket.color} rounded-full transition-all duration-500`}
                  style={{ width: `${histMax > 0 ? (bucket.count / histMax) * 100 : 0}%` }}
                />
              </div>
              <span className="text-xs font-mono text-[var(--muted-foreground)] w-8 text-right font-semibold">{bucket.count}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Problem documents */}
        <div className="bg-[var(--card)] border border-primary/10 rounded-xl shadow-sm overflow-hidden">
          <div className="p-6 pb-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="size-5 text-amber-500" />
              <h3 className="text-[var(--foreground)] text-base font-bold">Problem Documents</h3>
            </div>
            <p className="text-xs text-[var(--muted-foreground)] mt-1">Documents with lowest confidence or extraction failures</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-t border-b border-primary/10 bg-[var(--background)]">
                  <th className="text-left px-6 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Vendor</th>
                  <th className="text-center px-4 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Conf</th>
                  <th className="text-center px-4 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody>
                {problemDocs.map(d => {
                  const conf = d.extraction_confidence
                  const confDisplay = conf != null ? (conf * 100).toFixed(0) + '%' : '--'
                  const confColor = conf != null && conf < 0.5 ? 'text-red-500' : 'text-amber-600'
                  const status = d.status ?? 'unknown'
                  const statusClasses: Record<string, string> = {
                    approved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
                    needs_review: 'bg-amber-50 text-amber-700 border-amber-200',
                    rejected: 'bg-red-50 text-red-700 border-red-200',
                  }
                  const statusCls = statusClasses[status] ?? 'bg-gray-50 text-gray-600 border-gray-200'
                  return (
                    <tr key={d.id} className="border-b border-primary/5 hover:bg-primary/[0.02] transition-colors">
                      <td className="px-6 py-2.5 text-sm font-medium text-[var(--foreground)]">{d.vendor_name ?? d.file_name ?? '--'}</td>
                      <td className={`px-4 py-2.5 text-sm text-center font-mono font-semibold ${confColor}`}>{confDisplay}</td>
                      <td className="px-4 py-2.5 text-center">
                        <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full border ${statusCls}`}>
                          {formatEnum(status)}
                        </span>
                      </td>
                    </tr>
                  )
                })}
                {problemDocs.length === 0 && (
                  <tr><td colSpan={3} className="px-6 py-8 text-center text-[var(--muted-foreground)]">No problem documents — all above 80% confidence</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent extraction log */}
        <div className="bg-[var(--card)] border border-primary/10 rounded-xl shadow-sm overflow-hidden">
          <div className="p-6 pb-3">
            <div className="flex items-center gap-2">
              <Search className="size-5 text-primary" />
              <h3 className="text-[var(--foreground)] text-base font-bold">Recent Extraction Log</h3>
            </div>
            <p className="text-xs text-[var(--muted-foreground)] mt-1">Last 20 processed documents with model info</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-t border-b border-primary/10 bg-[var(--background)]">
                  <th className="text-left px-6 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Vendor</th>
                  <th className="text-center px-4 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Model</th>
                  <th className="text-center px-4 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Conf</th>
                  <th className="text-right px-4 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Date</th>
                </tr>
              </thead>
              <tbody>
                {recentDocs.map(d => {
                  const conf = d.extraction_confidence
                  let confDisplay = '--'
                  let confColor = 'text-[var(--muted-foreground)]'
                  if (conf != null) {
                    confDisplay = (conf * 100).toFixed(0) + '%'
                    confColor = conf >= 0.9 ? 'text-emerald-600' : conf >= 0.8 ? 'text-amber-600' : 'text-red-500'
                  }
                  const date = d.created_at ? d.created_at.substring(0, 10) : '--'
                  const model = d.extraction_model ?? '--'
                  return (
                    <tr key={d.id} className="border-b border-primary/5 hover:bg-primary/[0.02] transition-colors">
                      <td className="px-6 py-2.5 text-sm font-medium text-[var(--foreground)] truncate max-w-[160px]">{d.vendor_name ?? d.file_name ?? '--'}</td>
                      <td className="px-4 py-2.5 text-[11px] text-center font-mono text-[var(--muted-foreground)]">{model}</td>
                      <td className={`px-4 py-2.5 text-sm text-center font-mono font-medium ${confColor}`}>{confDisplay}</td>
                      <td className="px-4 py-2.5 text-sm text-right text-[var(--muted-foreground)]">{date}</td>
                    </tr>
                  )
                })}
                {recentDocs.length === 0 && (
                  <tr><td colSpan={4} className="px-6 py-8 text-center text-[var(--muted-foreground)]">No documents found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

// ================================================================
// INVENTORY TAB — stock levels, low stock, expiring
// ================================================================
function InventoryTab({ stats, lowStock, expiring }: {
  stats: DashboardStats | undefined
  lowStock: InventoryItem[]
  expiring: InventoryItem[]
}) {
  const [now] = useState(() => Date.now())
  // Find soonest expiry
  const soonestExpiry = useMemo(() => {
    if (expiring.length === 0) return null
    const sorted = [...expiring]
      .filter(i => i.expiry_date)
      .sort((a, b) => (a.expiry_date ?? '').localeCompare(b.expiry_date ?? ''))
    return sorted[0] ?? null
  }, [expiring])

  const soonestDays = useMemo(() => {
    if (!soonestExpiry?.expiry_date) return null
    return Math.max(0, Math.floor((new Date(soonestExpiry.expiry_date).getTime() - now) / (1000 * 60 * 60 * 24)))
  }, [soonestExpiry, now])

  return (
    <div className="space-y-6">
      {/* Headline insights */}
      <div className="space-y-2">
        {lowStock.length > 0 ? (
          <Insight
            text={`${lowStock.length} inventory item${lowStock.length > 1 ? 's' : ''} below reorder threshold — check low stock table below`}
            variant="warn"
          />
        ) : (
          <Insight text="All inventory items are above minimum stock levels" variant="good" />
        )}
        {expiring.length > 0 ? (
          <Insight
            text={`${expiring.length} item${expiring.length > 1 ? 's' : ''} expiring within 30 days${
              soonestExpiry ? ` — soonest: ${soonestExpiry.product_name ?? 'unknown'} in ${soonestDays} days` : ''
            }`}
            variant={soonestDays != null && soonestDays <= 7 ? 'bad' : 'warn'}
          />
        ) : (
          <Insight text="No inventory items expiring in the next 30 days" variant="good" />
        )}
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[var(--card)] border border-primary/10 p-5 rounded-xl flex flex-col gap-1 shadow-sm">
          <div className="flex items-center justify-between text-[var(--muted-foreground)] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider">Total Items</span>
            <Package className="size-5 opacity-50" />
          </div>
          <div className="text-3xl font-bold text-[var(--foreground)] tracking-tight">{stats?.total_inventory_items ?? 0}</div>
          <div className="text-[11px] text-[var(--muted-foreground)] font-medium">inventory records</div>
        </div>
        <div className="bg-[var(--card)] border border-primary/10 p-5 rounded-xl flex flex-col gap-1 shadow-sm">
          <div className="flex items-center justify-between text-[var(--muted-foreground)] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider">Active Orders</span>
            <TrendingUp className="size-5 opacity-50" />
          </div>
          <div className="text-3xl font-bold text-[var(--foreground)] tracking-tight">{stats?.total_orders ?? 0}</div>
          <div className="text-[11px] text-[var(--muted-foreground)] font-medium">orders in pipeline</div>
        </div>
        <div className="bg-[var(--card)] border border-primary/10 p-5 rounded-xl flex flex-col gap-1 shadow-sm">
          <div className="flex items-center justify-between text-[var(--muted-foreground)] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider">Low Stock</span>
            <AlertTriangle className="size-5 opacity-50" />
          </div>
          <div className={`text-3xl font-bold tracking-tight ${lowStock.length > 0 ? 'text-amber-600' : 'text-[var(--foreground)]'}`}>
            {lowStock.length}
          </div>
          <div className="text-[11px] text-[var(--muted-foreground)] font-medium">below reorder threshold</div>
        </div>
        <div className="bg-[var(--card)] border border-primary/10 p-5 rounded-xl flex flex-col gap-1 shadow-sm">
          <div className="flex items-center justify-between text-[var(--muted-foreground)] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider">Expiring Soon</span>
            <Clock className="size-5 opacity-50" />
          </div>
          <div className={`text-3xl font-bold tracking-tight ${expiring.length > 0 ? 'text-red-500' : 'text-[var(--foreground)]'}`}>
            {expiring.length}
          </div>
          <div className="text-[11px] text-[var(--muted-foreground)] font-medium">within 30 days</div>
        </div>
      </div>

      {/* Low stock table */}
      <div className="bg-[var(--card)] border border-primary/10 rounded-xl shadow-sm overflow-hidden">
        <div className="p-6 pb-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="size-5 text-amber-500" />
            <h3 className="text-[var(--foreground)] text-base font-bold">Low Stock Items</h3>
          </div>
          <p className="text-xs text-[var(--muted-foreground)] mt-0.5">Items that need reordering</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-t border-b border-primary/10 bg-[var(--background)]">
                <th className="text-left px-6 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Product</th>
                <th className="text-left px-4 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Location</th>
                <th className="text-center px-4 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Quantity</th>
                <th className="text-left px-4 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Lot</th>
              </tr>
            </thead>
            <tbody>
              {lowStock.map(item => (
                <tr key={item.id} className="border-b border-primary/5 hover:bg-primary/[0.02] transition-colors">
                  <td className="px-6 py-3 text-sm font-medium text-[var(--foreground)]">{item.product_name ?? '--'}</td>
                  <td className="px-4 py-3 text-sm text-[var(--muted-foreground)]">{item.location_name ?? '--'}</td>
                  <td className="px-4 py-3 text-sm text-center font-mono text-amber-600 font-medium">
                    {item.quantity_on_hand ?? 0} {item.unit ?? ''}
                  </td>
                  <td className="px-4 py-3 text-sm text-[var(--muted-foreground)] font-mono">{item.lot_number ?? '--'}</td>
                </tr>
              ))}
              {lowStock.length === 0 && (
                <tr><td colSpan={4} className="px-6 py-8 text-center text-[var(--muted-foreground)]">No low stock items</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Expiring items table */}
      <div className="bg-[var(--card)] border border-primary/10 rounded-xl shadow-sm overflow-hidden">
        <div className="p-6 pb-3">
          <div className="flex items-center gap-2">
            <Clock className="size-5 text-red-500" />
            <h3 className="text-[var(--foreground)] text-base font-bold">Expiring Items</h3>
          </div>
          <p className="text-xs text-[var(--muted-foreground)] mt-0.5">Items expiring within 30 days</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-t border-b border-primary/10 bg-[var(--background)]">
                <th className="text-left px-6 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Product</th>
                <th className="text-left px-4 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Location</th>
                <th className="text-center px-4 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Expiry Date</th>
                <th className="text-center px-4 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Quantity</th>
              </tr>
            </thead>
            <tbody>
              {expiring.map(item => (
                <tr key={item.id} className="border-b border-primary/5 hover:bg-primary/[0.02] transition-colors">
                  <td className="px-6 py-3 text-sm font-medium text-[var(--foreground)]">{item.product_name ?? '--'}</td>
                  <td className="px-4 py-3 text-sm text-[var(--muted-foreground)]">{item.location_name ?? '--'}</td>
                  <td className="px-4 py-3 text-sm text-center font-mono text-red-500 font-medium">{item.expiry_date ?? '--'}</td>
                  <td className="px-4 py-3 text-sm text-center font-mono text-[var(--foreground)]">
                    {item.quantity_on_hand ?? 0} {item.unit ?? ''}
                  </td>
                </tr>
              ))}
              {expiring.length === 0 && (
                <tr><td colSpan={4} className="px-6 py-8 text-center text-[var(--muted-foreground)]">No items expiring soon</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ================================================================
// MAIN PAGE
// ================================================================
export function AnalyticsPage({ onError }: AnalyticsPageProps) {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<TabValue>('overview')

  // Fetch all data
  const { data: stats, error: statsErr } = useQuery({
    queryKey: ['analytics-dashboard'],
    queryFn: () => analytics.dashboard() as Promise<DashboardStats>,
  })

  const { data: docStats, error: docStatsErr } = useQuery({
    queryKey: ['analytics-doc-stats'],
    queryFn: () => analytics.documentStats(),
  })

  const { data: docsRes, error: docsErr } = useQuery({
    queryKey: ['analytics-docs'],
    queryFn: () => docApi.list(1, 200),
  })

  const { data: lowStockRes, error: lowStockErr } = useQuery({
    queryKey: ['analytics-low-stock'],
    queryFn: () => invApi.lowStock(),
  })

  const { data: expiringRes, error: expiringErr } = useQuery({
    queryKey: ['analytics-expiring'],
    queryFn: () => invApi.expiring(),
  })

  const docs = docsRes?.items ?? []
  const lowStock = lowStockRes?.items ?? []
  const expiring = expiringRes?.items ?? []

  useEffect(() => {
    const err = statsErr ?? docStatsErr ?? docsErr ?? lowStockErr ?? expiringErr
    if (err) {
      onError(err instanceof Error ? err.message : 'Failed to load analytics data')
    }
  }, [statsErr, docStatsErr, docsErr, lowStockErr, expiringErr, onError])

  const isLoading = !stats && !statsErr

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
          <p className="text-sm text-[var(--muted-foreground)]">Loading analytics...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-3xl font-bold text-[var(--foreground)] tracking-tight">Lab Intelligence</h2>
        <p className="text-[var(--muted-foreground)] mt-2 text-sm">
          Insights and analysis you cannot see on the Dashboard — AI performance, vendor risks, problem documents, inventory alerts.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-6 border-b border-primary/10">
        {TABS.map(tab => {
          const Icon = tab.icon
          return (
            <button
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              className={`flex items-center gap-2 pb-3 border-b-2 text-sm tracking-wide transition-all ${
                activeTab === tab.value
                  ? 'text-primary font-bold border-primary'
                  : 'text-[var(--muted-foreground)] font-medium border-transparent hover:text-[var(--foreground)]'
              }`}
            >
              <Icon className="size-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      {activeTab === 'overview' && (
        <OverviewTab docs={docs} docStats={docStats} />
      )}
      {activeTab === 'vendors' && (
        <VendorsTab docs={docs} navigate={navigate} />
      )}
      {activeTab === 'documents' && (
        <DocumentsTab docs={docs} />
      )}
      {activeTab === 'inventory' && (
        <InventoryTab stats={stats} lowStock={lowStock} expiring={expiring} />
      )}
    </div>
  )
}
