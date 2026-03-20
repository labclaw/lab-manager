import { useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  Upload, ShoppingCartPlus, Boxes, Users, FileText, CheckCircle,
  Clock, ShoppingBag, Store, AlertTriangle, Calendar, BarChart3, FolderOpen,
} from 'lucide-react'
import { analytics, inventory, vendors, documents } from '@/lib/api'
import type { Vendor, DashboardStats } from '@/lib/api'

interface DashboardPageProps {
  readonly onError: (msg: string) => void
}

// Full Tailwind class names for bar colors (must be complete strings for purge)
const VENDOR_BAR_CLASSES = [
  'h-full bg-primary rounded-full transition-all duration-500',
  'h-full bg-primary/80 rounded-full transition-all duration-500',
  'h-full bg-primary/60 rounded-full transition-all duration-500',
  'h-full bg-primary/40 rounded-full transition-all duration-500',
  'h-full bg-primary/20 rounded-full transition-all duration-500',
]

const DOC_BAR_CLASSES = [
  'h-full bg-accent-green rounded-full transition-all duration-500',
  'h-full bg-accent-green/80 rounded-full transition-all duration-500',
  'h-full bg-accent-green/60 rounded-full transition-all duration-500',
  'h-full bg-accent-green/40 rounded-full transition-all duration-500',
]

export function DashboardPage({ onError }: Readonly<DashboardPageProps>) {
  const navigate = useNavigate()

  const { data: stats, error: statsErr } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => analytics.dashboard() as Promise<DashboardStats>,
  })

  const { data: lowStockData, error: lowStockErr } = useQuery({
    queryKey: ['inventory-low-stock'],
    queryFn: () => inventory.lowStock(),
  })

  const { data: expiringData, error: expiringErr } = useQuery({
    queryKey: ['inventory-expiring'],
    queryFn: () => inventory.expiring(),
  })

  const { data: vendorData, error: vendorErr } = useQuery({
    queryKey: ['vendors-list'],
    queryFn: () => vendors.list(1, 100),
  })

  const { data: docData, error: docErr } = useQuery({
    queryKey: ['documents-list'],
    queryFn: () => documents.list(1, 200), // API limits page_size to 200
  })

  // Report errors
  useEffect(() => {
    const err = statsErr ?? lowStockErr ?? expiringErr ?? vendorErr ?? docErr
    if (err) {
      onError(err instanceof Error ? err.message : 'Failed to load dashboard data')
    }
  }, [statsErr, lowStockErr, expiringErr, vendorErr, docErr, onError])

  // Compute vendor order counts (top 5)
  const vendorChart = useMemo(() => {
    const list = vendorData?.items ?? []
    const sorted = [...list]
      .sort((a, b) => (b.order_count ?? 0) - (a.order_count ?? 0))
      .slice(0, 5)
    const max = sorted.length > 0 ? (sorted[0]?.order_count ?? 1) : 1
    const totalOrders = list.reduce((s: number, v: Vendor) => s + (v.order_count ?? 0), 0)
    return sorted.map((v) => ({
      name: v.name,
      count: v.order_count ?? 0,
      pct: totalOrders > 0 ? Math.round(((v.order_count ?? 0) / totalOrders) * 100) : 0,
      width: max > 0 ? Math.round(((v.order_count ?? 0) / max) * 100) : 0,
    }))
  }, [vendorData])

  // Compute document type distribution (top 4)
  const docChart = useMemo(() => {
    const docs = docData?.items ?? []
    const counts: Record<string, number> = {}
    for (const d of docs) {
      const t = d.document_type ?? 'unknown'
      counts[t] = (counts[t] ?? 0) + 1
    }
    const entries = Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4)
    const max = entries.length > 0 ? entries[0]![1] : 1
    return entries.map(([type, count]) => ({
      type,
      count,
      width: max > 0 ? Math.round((count / max) * 100) : 0,
    }))
  }, [docData])

  const totalDocs = stats?.total_documents ?? 0
  const approved = stats?.documents_approved ?? 0
  const needsReview = stats?.documents_pending_review ?? 0
  const ordersCreated = stats?.total_orders ?? 0
  const totalVendors = stats?.total_vendors ?? 0
  const approvalPct = totalDocs > 0 ? Math.round((approved / totalDocs) * 100) : 0

  const lowStockCount = lowStockData?.items?.length ?? 0
  const expiringCount = expiringData?.items?.length ?? 0

  return (
    <div className="space-y-8">
      {/* Quick Actions Row */}
      <div className="mb-8">
        <h3 className="text-[var(--muted-foreground)] text-[10px] font-bold uppercase tracking-widest mb-4">Quick Actions</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <button
            onClick={() => navigate('/upload')}
            className="flex items-center justify-center gap-3 p-4 bg-primary hover:bg-primary/90 text-white rounded-xl font-bold text-sm transition-all shadow-lg shadow-primary/20 group"
          >
            <Upload className="size-5 group-hover:scale-110 transition-transform" />
            <span>Upload Document</span>
          </button>
          <button
            onClick={() => navigate('/orders')}
            className="flex items-center justify-center gap-3 p-4 bg-[var(--card)] border border-primary/20 hover:border-primary/50 text-[var(--foreground)] rounded-xl font-bold text-sm transition-all group"
          >
            <ShoppingCartPlus className="size-5 text-primary group-hover:scale-110 transition-transform" />
            <span>New Order</span>
          </button>
          <button
            onClick={() => navigate('/inventory')}
            className="flex items-center justify-center gap-3 p-4 bg-[var(--card)] border border-primary/20 hover:border-primary/50 text-[var(--foreground)] rounded-xl font-bold text-sm transition-all group"
          >
            <Boxes className="size-5 text-primary group-hover:scale-110 transition-transform" />
            <span>Update Stock</span>
          </button>
          <button
            onClick={() => navigate('/settings')}
            className="flex items-center justify-center gap-3 p-4 bg-[var(--card)] border border-primary/20 hover:border-primary/50 text-[var(--foreground)] rounded-xl font-bold text-sm transition-all group"
          >
            <Users className="size-5 text-primary group-hover:scale-110 transition-transform" />
            <span>Manage Lab</span>
          </button>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        {/* Total Documents */}
        <div className="bg-[var(--card)] border border-primary/10 p-5 rounded-xl flex flex-col gap-1 shadow-sm">
          <div className="flex items-center justify-between text-[var(--muted-foreground)] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">Total Documents</span>
            <FileText className="size-5 opacity-50" />
          </div>
          <div className="text-3xl font-bold text-[var(--foreground)] tracking-tight">{totalDocs}</div>
          <div className="text-[11px] text-[var(--muted-foreground)] font-medium">Total lab docs processed</div>
        </div>

        {/* Approved - green left border */}
        <div className="bg-[var(--card)] border border-primary/10 p-5 rounded-xl flex flex-col gap-1 shadow-sm border-l-4 border-l-accent-green">
          <div className="flex items-center justify-between text-[var(--muted-foreground)] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">Approved</span>
            <CheckCircle className="size-5 text-accent-green" />
          </div>
          <div className="text-3xl font-bold text-accent-green tracking-tight">{approved}</div>
          <div className="text-[11px] text-[var(--muted-foreground)] font-medium">{approvalPct}% automation accuracy</div>
        </div>

        {/* Needs Review - amber left border */}
        <div className="bg-[var(--card)] border border-primary/10 p-5 rounded-xl flex flex-col gap-1 shadow-sm border-l-4 border-l-amber-400">
          <div className="flex items-center justify-between text-[var(--muted-foreground)] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">Needs Review</span>
            <Clock className="size-5 text-amber-400" />
          </div>
          <div className="text-3xl font-bold text-amber-400 tracking-tight">{needsReview}</div>
          <div className="text-[11px] text-[var(--muted-foreground)] font-medium">Awaiting lab verification</div>
        </div>

        {/* Orders Created */}
        <div className="bg-[var(--card)] border border-primary/10 p-5 rounded-xl flex flex-col gap-1 shadow-sm">
          <div className="flex items-center justify-between text-[var(--muted-foreground)] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">Orders Created</span>
            <ShoppingBag className="size-5 opacity-50" />
          </div>
          <div className="text-3xl font-bold text-[var(--foreground)] tracking-tight">{ordersCreated}</div>
          <div className="text-[11px] text-[var(--muted-foreground)] font-medium">
            {stats?.total_inventory_items ?? 0} line items reconciled
          </div>
        </div>

        {/* Vendors */}
        <div className="bg-[var(--card)] border border-primary/10 p-5 rounded-xl flex flex-col gap-1 shadow-sm">
          <div className="flex items-center justify-between text-[var(--muted-foreground)] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">Vendors</span>
            <Store className="size-5 opacity-50" />
          </div>
          <div className="text-3xl font-bold text-[var(--foreground)] tracking-tight">{totalVendors}</div>
          <div className="text-[11px] text-[var(--muted-foreground)] font-medium">Discovered from scan history</div>
        </div>
      </div>

      {/* Alert Banners */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        {/* Critical Inventory Level */}
        <div className="flex items-center gap-4 bg-amber-400/5 border border-amber-400/20 p-5 rounded-xl group hover:bg-amber-400/10 transition-colors">
          <div className="size-12 rounded-full bg-amber-400/10 flex items-center justify-center text-amber-400 shrink-0">
            <AlertTriangle className="size-6" />
          </div>
          <div className="flex-1">
            <p className="text-amber-50 text-sm font-bold">Critical Inventory Level</p>
            <p className="text-amber-400/70 text-xs mt-0.5">
              {lowStockCount} item{lowStockCount !== 1 ? 's are' : ' is'} below minimum stock thresholds.
            </p>
          </div>
          <button
            onClick={() => navigate('/inventory')}
            className="px-4 py-2 bg-amber-400 text-[var(--background)] rounded-lg text-xs font-bold uppercase tracking-wider hover:bg-amber-300 transition-colors shadow-lg shadow-amber-400/10"
          >
            Reorder Now
          </button>
        </div>

        {/* Expiring Reagents */}
        <div className="flex items-center gap-4 bg-red-500/5 border border-red-500/20 p-5 rounded-xl group hover:bg-red-500/10 transition-colors">
          <div className="size-12 rounded-full bg-red-500/10 flex items-center justify-center text-red-400 shrink-0">
            <Calendar className="size-6" />
          </div>
          <div className="flex-1">
            <p className="text-red-50 text-sm font-bold">Expiring Reagents</p>
            <p className="text-red-400/70 text-xs mt-0.5">
              {expiringCount} vital item{expiringCount !== 1 ? 's' : ''} will expire within 30 days.
            </p>
          </div>
          <button
            onClick={() => navigate('/inventory')}
            className="px-4 py-2 bg-red-500 text-white rounded-lg text-xs font-bold uppercase tracking-wider hover:bg-red-400 transition-colors shadow-lg shadow-red-500/10"
          >
            View List
          </button>
        </div>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Top Lab Vendors */}
        <div className="bg-[var(--card)] border border-primary/10 rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-8">
            <h3 className="text-[var(--foreground)] text-lg font-bold flex items-center gap-2">
              <BarChart3 className="size-5 text-primary" />
              Top Lab Vendors
            </h3>
            <span className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest bg-[var(--card)] px-2 py-1 rounded">
              Last 90 Days
            </span>
          </div>
          <div className="space-y-6">
            {vendorChart.length > 0 ? (
              vendorChart.map((v, i) => (
                <div key={v.name} className="space-y-2 group">
                  <div className="flex justify-between items-end">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-[var(--foreground)] font-semibold">{v.name}</span>
                      {i === 0 && (
                        <span className="hidden group-hover:block text-[10px] bg-primary/20 text-primary px-1.5 py-0.5 rounded font-bold">
                          Primary Vendor
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-[var(--muted-foreground)] font-mono">
                      {v.count} orders ({v.pct}%)
                    </span>
                  </div>
                  <div className="h-2.5 w-full bg-[var(--card)] rounded-full overflow-hidden">
                    <div
                      className={VENDOR_BAR_CLASSES[i] ?? VENDOR_BAR_CLASSES[4]}
                      style={{ width: `${v.width}%` }}
                    />
                  </div>
                </div>
              ))
            ) : (
              <div className="text-sm text-[var(--muted-foreground)] py-4">No vendor data yet</div>
            )}
          </div>
        </div>

        {/* Document Classification */}
        <div className="bg-[var(--card)] border border-primary/10 rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-8">
            <h3 className="text-[var(--foreground)] text-lg font-bold flex items-center gap-2">
              <FolderOpen className="size-5 text-primary" />
              Document Classification
            </h3>
            <button
              onClick={() => navigate('/documents')}
              className="text-[10px] font-bold text-primary uppercase tracking-widest hover:underline"
            >
              View All Files
            </button>
          </div>
          <div className="space-y-6">
            {docChart.length > 0 ? (
              docChart.map((d, i) => (
                <div key={d.type} className="space-y-2 group">
                  <div className="flex justify-between items-end">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-[var(--foreground)] font-mono">{d.type}</span>
                      {i === 0 && totalDocs > 0 && (
                        <span className="hidden group-hover:block text-[10px] bg-accent-green/20 text-accent-green px-1.5 py-0.5 rounded font-bold">
                          {Math.round((d.count / totalDocs) * 100)}% of docs
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-[var(--muted-foreground)] font-mono">{d.count} files</span>
                  </div>
                  <div className="h-2.5 w-full bg-[var(--card)] rounded-full overflow-hidden">
                    <div
                      className={DOC_BAR_CLASSES[i] ?? DOC_BAR_CLASSES[3]}
                      style={{ width: `${d.width}%` }}
                    />
                  </div>
                </div>
              ))
            ) : (
              <div className="text-sm text-[var(--muted-foreground)] py-4">No document data yet</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
