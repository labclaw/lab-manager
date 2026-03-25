import { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart3, FileText, Package, Store, CheckCircle, Clock,
  TrendingUp, Users, Beaker, Wrench, Box,
} from 'lucide-react'
import { analytics, documents as docApi, inventory as invApi } from '@/lib/api'
import type { DashboardStats, DocumentStats, Document, InventoryItem } from '@/lib/api'
import { formatEnum } from '@/lib/utils'

interface AnalyticsPageProps {
  readonly onError: (msg: string) => void
}

type TabValue = 'overview' | 'vendors' | 'documents' | 'inventory'

const TABS: { readonly value: TabValue; readonly label: string; readonly icon: typeof BarChart3 }[] = [
  { value: 'overview', label: 'Overview', icon: TrendingUp },
  { value: 'vendors', label: 'Vendors', icon: Store },
  { value: 'documents', label: 'Documents', icon: FileText },
  { value: 'inventory', label: 'Inventory', icon: Package },
]

// Vendor category mapping (from standalone analytics)
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

const DOC_TYPE_LABELS: Record<string, string> = {
  packing_list: 'Packing Lists',
  invoice: 'Invoices',
  shipping_label: 'Shipping Labels',
  certificate_of_analysis: 'Certificates of Analysis',
  other: 'Other',
  mta: 'Material Transfer Agreements',
  receipt: 'Receipts',
  null: 'Unclassified',
}

const CHART_COLORS = [
  'bg-primary', 'bg-emerald-500', 'bg-sky-500', 'bg-amber-500',
  'bg-rose-500', 'bg-teal-500', 'bg-violet-500', 'bg-orange-500',
]

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
// Stat Card (reused across tabs)
// ----------------------------------------------------------------
function StatCard({ label, value, sub, icon: Icon }: {
  label: string; value: string | number; sub: string; icon: typeof BarChart3
}) {
  return (
    <div className="bg-[var(--card)] border border-primary/10 p-5 rounded-xl flex flex-col gap-1 shadow-sm">
      <div className="flex items-center justify-between text-[var(--muted-foreground)] mb-2">
        <span className="text-[11px] font-bold uppercase tracking-wider">{label}</span>
        <Icon className="size-5 opacity-50" />
      </div>
      <div className="text-3xl font-bold text-[var(--foreground)] tracking-tight">{value}</div>
      <div className="text-[11px] text-[var(--muted-foreground)] font-medium">{sub}</div>
    </div>
  )
}

// ----------------------------------------------------------------
// Horizontal bar row
// ----------------------------------------------------------------
function BarRow({ label, count, max, index }: {
  label: string; count: number; max: number; index: number
}) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0
  const opacities = ['', '/80', '/60', '/40', '/20']
  const opacity = opacities[Math.min(index, opacities.length - 1)]
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-end">
        <span className="text-sm text-[var(--foreground)] font-semibold truncate mr-2">{label}</span>
        <span className="text-xs text-[var(--muted-foreground)] font-mono shrink-0">{count}</span>
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
// OVERVIEW TAB
// ================================================================
function OverviewTab({ stats, docs, docStats }: {
  stats: DashboardStats | undefined
  docs: Document[]
  docStats: DocumentStats | undefined
}) {
  const confidences = useMemo(
    () => docs.filter(d => d.extraction_confidence != null).map(d => d.extraction_confidence!),
    [docs],
  )
  const highConf = confidences.filter(c => c > 0.8).length
  const accuracy = confidences.length > 0 ? ((highConf / confidences.length) * 100).toFixed(1) : '0'

  const vendorSet = useMemo(() => new Set(docs.map(d => d.vendor_name).filter(Boolean)), [docs])

  let totalItems = 0
  for (const d of docs) {
    if (d.extracted_data?.items) totalItems += d.extracted_data.items.length
  }

  const pending = docStats?.by_status?.needs_review ?? stats?.documents_pending_review ?? 0

  // Top 5 vendors for quick view
  const vendorTop5 = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const d of docs) {
      const v = d.vendor_name ?? 'Unknown'
      counts[v] = (counts[v] ?? 0) + 1
    }
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 5)
    const max = sorted[0]?.[1] ?? 1
    return { items: sorted, max }
  }, [docs])

  // Top 4 doc types
  const docTypeTop4 = useMemo(() => {
    const typeMap = docStats?.by_type ?? {}
    const entries = Object.entries(typeMap).sort((a, b) => b[1] - a[1]).slice(0, 4)
    const max = entries[0]?.[1] ?? 1
    return { items: entries, max }
  }, [docStats])

  return (
    <div className="space-y-8">
      {/* Stats bar */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard label="Documents Processed" value={docStats?.total_documents ?? docs.length} sub="scanned & extracted" icon={FileText} />
        <StatCard label="Unique Vendors" value={vendorSet.size} sub="suppliers identified" icon={Store} />
        <StatCard label="Items Tracked" value={totalItems} sub="catalog items extracted" icon={Package} />
        <div className="bg-[var(--card)] border border-primary/10 p-5 rounded-xl flex flex-col gap-1 shadow-sm">
          <div className="flex items-center justify-between text-[var(--muted-foreground)] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider">AI Accuracy</span>
            <CheckCircle className="size-5 opacity-50" />
          </div>
          <div className="text-3xl font-bold text-primary tracking-tight">{accuracy}%</div>
          <div className="text-[11px] text-[var(--muted-foreground)] font-medium">confidence &gt; 0.8</div>
        </div>
        <div className="bg-[var(--card)] border border-primary/10 p-5 rounded-xl flex flex-col gap-1 shadow-sm">
          <div className="flex items-center justify-between text-[var(--muted-foreground)] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider">Pending Review</span>
            <Clock className="size-5 opacity-50" />
          </div>
          <div className="text-3xl font-bold text-amber-600 tracking-tight">{pending}</div>
          <div className="text-[11px] text-[var(--muted-foreground)] font-medium">awaiting human QA</div>
        </div>
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top vendors quick */}
        <div className="bg-[var(--card)] border border-primary/10 rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-[var(--foreground)] text-base font-bold flex items-center gap-2">
              <BarChart3 className="size-5 text-primary" />
              Top Vendors
            </h3>
            <span className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest">by documents</span>
          </div>
          <div className="space-y-4">
            {vendorTop5.items.map(([name, count], i) => (
              <BarRow key={name} label={name} count={count} max={vendorTop5.max} index={i} />
            ))}
            {vendorTop5.items.length === 0 && (
              <p className="text-sm text-[var(--muted-foreground)] py-4">No vendor data yet</p>
            )}
          </div>
        </div>

        {/* Doc types quick */}
        <div className="bg-[var(--card)] border border-primary/10 rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-[var(--foreground)] text-base font-bold flex items-center gap-2">
              <FileText className="size-5 text-primary" />
              Document Types
            </h3>
          </div>
          <div className="space-y-4">
            {docTypeTop4.items.map(([type, count], i) => (
              <BarRow key={type} label={DOC_TYPE_LABELS[type] ?? formatEnum(type)} count={count} max={docTypeTop4.max} index={i} />
            ))}
            {docTypeTop4.items.length === 0 && (
              <p className="text-sm text-[var(--muted-foreground)] py-4">No document type data yet</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ================================================================
// VENDORS TAB
// ================================================================
function VendorsTab({ docs }: { docs: Document[] }) {
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

  const filterButtons: { key: typeof filter; label: string; icon: typeof Beaker }[] = [
    { key: 'all', label: 'All', icon: Users },
    { key: 'reagents', label: 'Reagents', icon: Beaker },
    { key: 'equipment', label: 'Equipment', icon: Wrench },
    { key: 'supplies', label: 'Supplies', icon: Box },
  ]

  return (
    <div className="space-y-8">
      {/* Category stats */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Reagent Vendors" value={categoryCounts.reagents} sub="bio & chem suppliers" icon={Beaker} />
        <StatCard label="Equipment Vendors" value={categoryCounts.equipment} sub="instruments & devices" icon={Wrench} />
        <StatCard label="General Supplies" value={categoryCounts.supplies} sub="consumables & other" icon={Box} />
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
            <BarRow key={name} label={name} count={count} max={max} index={Math.min(i, 4)} />
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
            <span
              key={v.name}
              className="inline-block px-2.5 py-1 rounded-md bg-primary/5 text-primary text-[13px] font-medium"
              title={`${v.count} document${v.count > 1 ? 's' : ''}`}
            >
              {v.name} <span className="text-primary/50 ml-1">{v.count}</span>
            </span>
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
// DOCUMENTS TAB
// ================================================================
function DocumentsTab({ docs, docStats }: { docs: Document[]; docStats: DocumentStats | undefined }) {
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

  // Doc type breakdown (full)
  const typeEntries = useMemo(() => {
    const typeMap = docStats?.by_type ?? {}
    return Object.entries(typeMap).sort((a, b) => b[1] - a[1])
  }, [docStats])
  const typeTotal = typeEntries.reduce((s, e) => s + e[1], 0)

  // Recent 20 docs
  const recentDocs = useMemo(() => {
    return [...docs]
      .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''))
      .slice(0, 20)
  }, [docs])

  return (
    <div className="space-y-8">
      {/* Doc type breakdown + confidence side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Document type breakdown */}
        <div className="lg:col-span-2 bg-[var(--card)] border border-primary/10 rounded-xl p-6 shadow-sm">
          <div className="mb-6">
            <h3 className="text-[var(--foreground)] text-base font-bold flex items-center gap-2">
              <FileText className="size-5 text-primary" />
              Document Types
            </h3>
            <p className="text-xs text-[var(--muted-foreground)] mt-0.5">Breakdown of all processed documents</p>
          </div>
          <div className="space-y-3">
            {typeEntries.map(([type, count], i) => {
              const pct = typeTotal > 0 ? ((count / typeTotal) * 100).toFixed(0) : '0'
              return (
                <div key={type} className="flex items-center gap-3">
                  <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${CHART_COLORS[i % CHART_COLORS.length]}`} />
                  <span className="text-sm text-[var(--foreground)] font-medium flex-1 truncate">
                    {DOC_TYPE_LABELS[type] ?? formatEnum(type)}
                  </span>
                  <span className="text-sm font-semibold text-[var(--foreground)]">{count}</span>
                  <span className="text-xs text-[var(--muted-foreground)] w-10 text-right">{pct}%</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* AI confidence summary */}
        <div className="bg-[var(--card)] border border-primary/10 rounded-xl p-6 shadow-sm">
          <div className="mb-6">
            <h3 className="text-[var(--foreground)] text-base font-bold">AI Performance</h3>
            <p className="text-xs text-[var(--muted-foreground)] mt-0.5">Extraction confidence metrics</p>
          </div>
          <div className="space-y-4">
            <div className="flex justify-between items-center text-sm">
              <span className="text-[var(--muted-foreground)]">Mean confidence</span>
              <span className="font-semibold text-[var(--foreground)]">{meanConf}%</span>
            </div>
            <div className="flex justify-between items-center text-sm">
              <span className="text-[var(--muted-foreground)]">Docs with &gt; 90% conf</span>
              <span className="font-semibold text-emerald-600">{highConfCount} / {confidences.length}</span>
            </div>
            <div className="flex justify-between items-center text-sm">
              <span className="text-[var(--muted-foreground)]">Extraction model</span>
              <span className="font-mono text-xs text-[var(--muted-foreground)]">LLaMA 3.2 90B</span>
            </div>
            <div className="border-t border-primary/10 pt-4 mt-2">
              <h4 className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider mb-3">Confidence Distribution</h4>
              <div className="space-y-2">
                {histogram.map(bucket => (
                  <div key={bucket.label} className="flex items-center gap-2">
                    <span className="text-[10px] text-[var(--muted-foreground)] w-12 shrink-0">{bucket.label}</span>
                    <div className="flex-1 h-3 bg-[var(--background)] rounded-full overflow-hidden">
                      <div
                        className={`h-full ${bucket.color} rounded-full transition-all duration-500`}
                        style={{ width: `${histMax > 0 ? (bucket.count / histMax) * 100 : 0}%` }}
                      />
                    </div>
                    <span className="text-[10px] font-mono text-[var(--muted-foreground)] w-6 text-right">{bucket.count}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent documents table */}
      <div className="bg-[var(--card)] border border-primary/10 rounded-xl shadow-sm overflow-hidden">
        <div className="p-6 pb-3">
          <h3 className="text-[var(--foreground)] text-base font-bold">Recent Documents</h3>
          <p className="text-xs text-[var(--muted-foreground)] mt-0.5">Last 20 processed documents</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-t border-b border-primary/10 bg-[var(--background)]">
                <th className="text-left px-6 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Vendor</th>
                <th className="text-left px-4 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Type</th>
                <th className="text-center px-4 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Confidence</th>
                <th className="text-center px-4 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Status</th>
                <th className="text-right px-6 py-2.5 text-[11px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Date</th>
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
                const status = d.status ?? 'unknown'
                const statusClasses: Record<string, string> = {
                  approved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
                  needs_review: 'bg-amber-50 text-amber-700 border-amber-200',
                  rejected: 'bg-red-50 text-red-700 border-red-200',
                }
                const statusCls = statusClasses[status] ?? 'bg-gray-50 text-gray-600 border-gray-200'
                const date = d.created_at ? d.created_at.substring(0, 10) : '--'

                return (
                  <tr key={d.id} className="border-b border-primary/5 hover:bg-primary/[0.02] transition-colors">
                    <td className="px-6 py-3 text-sm font-medium text-[var(--foreground)]">{d.vendor_name ?? '--'}</td>
                    <td className="px-4 py-3 text-sm text-[var(--muted-foreground)]">{d.document_type ? formatEnum(d.document_type) : '--'}</td>
                    <td className={`px-4 py-3 text-sm text-center font-mono font-medium ${confColor}`}>{confDisplay}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full border ${statusCls}`}>
                        {formatEnum(status)}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-sm text-right text-[var(--muted-foreground)]">{date}</td>
                  </tr>
                )
              })}
              {recentDocs.length === 0 && (
                <tr><td colSpan={5} className="px-6 py-8 text-center text-[var(--muted-foreground)]">No documents found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ================================================================
// INVENTORY TAB
// ================================================================
function InventoryTab({ stats, lowStock, expiring }: {
  stats: DashboardStats | undefined
  lowStock: InventoryItem[]
  expiring: InventoryItem[]
}) {
  return (
    <div className="space-y-8">
      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Items" value={stats?.total_inventory_items ?? 0} sub="inventory records" icon={Package} />
        <StatCard label="Active Orders" value={stats?.total_orders ?? 0} sub="orders in pipeline" icon={TrendingUp} />
        <div className="bg-[var(--card)] border border-primary/10 p-5 rounded-xl flex flex-col gap-1 shadow-sm">
          <div className="flex items-center justify-between text-[var(--muted-foreground)] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider">Low Stock</span>
            <Package className="size-5 opacity-50" />
          </div>
          <div className={`text-3xl font-bold tracking-tight ${lowStock.length > 0 ? 'text-amber-600' : 'text-[var(--foreground)]'}`}>
            {lowStock.length}
          </div>
          <div className="text-[11px] text-[var(--muted-foreground)] font-medium">items below threshold</div>
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
          <h3 className="text-[var(--foreground)] text-base font-bold">Low Stock Items</h3>
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
          <h3 className="text-[var(--foreground)] text-base font-bold">Expiring Items</h3>
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
        <h2 className="text-3xl font-bold text-[var(--foreground)] tracking-tight">Analytics</h2>
        <p className="text-[var(--muted-foreground)] mt-2 text-sm">
          Lab data insights across {stats?.total_documents ?? 0} documents, {stats?.total_vendors ?? 0} vendors, and {stats?.total_inventory_items ?? 0} inventory items.
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
        <OverviewTab stats={stats} docs={docs} docStats={docStats} />
      )}
      {activeTab === 'vendors' && (
        <VendorsTab docs={docs} />
      )}
      {activeTab === 'documents' && (
        <DocumentsTab docs={docs} docStats={docStats} />
      )}
      {activeTab === 'inventory' && (
        <InventoryTab stats={stats} lowStock={lowStock} expiring={expiring} />
      )}
    </div>
  )
}
