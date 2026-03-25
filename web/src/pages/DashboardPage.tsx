import { useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  Upload, ShoppingCart, Boxes, Users, FileText, CheckCircle,
  Clock, ShoppingBag, Store, AlertTriangle, Calendar, BarChart3, FolderOpen,
} from 'lucide-react'
import { analytics, inventory, vendors, documents } from '@/lib/api'
import type { Vendor, DashboardStats } from '@/lib/api'
import { formatEnum } from '@/lib/utils'

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
  'h-full bg-primary rounded-full transition-all duration-500',
  'h-full bg-accent-green rounded-full transition-all duration-500',
  'h-full bg-amber-500 rounded-full transition-all duration-500',
  'h-full bg-sky-500 rounded-full transition-all duration-500',
]

export function DashboardPage({ onError }: Readonly<DashboardPageProps>) {
  const navigate = useNavigate()

  const { data: stats, error: statsErr, isLoading: statsLoading } = useQuery({
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

  // Compute vendor counts (top 5) — prefer order counts, fall back to document counts
  const vendorChart = useMemo(() => {
    const list = vendorData?.items ?? []
    const docs = docData?.items ?? []
    const totalOrders = list.reduce((s: number, v: Vendor) => s + (v.order_count ?? 0), 0)
    const useDocCounts = totalOrders === 0

    // Count docs per vendor name
    const docCountByVendor: Record<string, number> = {}
    if (useDocCounts) {
      for (const d of docs) {
        const vn = d.vendor_name
        if (vn) docCountByVendor[vn] = (docCountByVendor[vn] ?? 0) + 1
      }
    }

    const sorted = [...list]
      .map((v) => ({
        ...v,
        effectiveCount: useDocCounts ? (docCountByVendor[v.name] ?? 0) : (v.order_count ?? 0),
      }))
      .sort((a, b) => b.effectiveCount - a.effectiveCount)
      .slice(0, 5)
    const max = sorted.length > 0 ? (sorted[0]?.effectiveCount ?? 1) : 1
    const totalEffective = sorted.reduce((s, v) => s + v.effectiveCount, 0)
    return {
      label: useDocCounts ? 'documents' : 'orders',
      items: sorted.map((v) => ({
        name: v.name,
        count: v.effectiveCount,
        pct: totalEffective > 0 ? Math.round((v.effectiveCount / totalEffective) * 100) : 0,
        width: max > 0 ? Math.round((v.effectiveCount / max) * 100) : 0,
      })),
    }
  }, [vendorData, docData])

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

  if (statsLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
          <p className="text-sm text-[var(--muted-foreground)]">Loading dashboard...</p>
        </div>
      </div>
    )
  }

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
            <ShoppingCart className="size-5 text-primary group-hover:scale-110 transition-transform" />
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

        {/* Approved */}
        <div className="bg-[var(--card)] border border-primary/10 p-5 rounded-xl flex flex-col gap-1 shadow-sm">
          <div className="flex items-center justify-between text-[var(--muted-foreground)] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">Approved</span>
            <CheckCircle className="size-5 opacity-50" />
          </div>
          <div className="text-3xl font-bold text-primary tracking-tight">{approved}</div>
          <div className="text-[11px] text-[var(--muted-foreground)] font-medium">{approvalPct}% automation accuracy</div>
        </div>

        {/* Needs Review */}
        <div className="bg-[var(--card)] border border-primary/10 p-5 rounded-xl flex flex-col gap-1 shadow-sm">
          <div className="flex items-center justify-between text-[var(--muted-foreground)] mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">Needs Review</span>
            <Clock className="size-5 opacity-50" />
          </div>
          <div className="text-3xl font-bold text-primary tracking-tight">{needsReview}</div>
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

      {/* Inline Alerts */}
      {(lowStockCount > 0 || expiringCount > 0) && (
        <div className="flex flex-wrap gap-3 mb-8">
          {lowStockCount > 0 && (
            <button
              onClick={() => navigate('/inventory')}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100 transition-colors"
            >
              <AlertTriangle className="size-3.5" />
              {lowStockCount} low stock item{lowStockCount !== 1 ? 's' : ''}
            </button>
          )}
          {expiringCount > 0 && (
            <button
              onClick={() => navigate('/inventory')}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium bg-orange-50 text-orange-700 border border-orange-200 hover:bg-orange-100 transition-colors"
            >
              <Calendar className="size-3.5" />
              {expiringCount} expiring item{expiringCount !== 1 ? 's' : ''}
            </button>
          )}
        </div>
      )}

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
            {vendorChart.items.length > 0 ? (
              vendorChart.items.map((v, i) => (
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
                      {v.count} {vendorChart.label} ({v.pct}%)
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
                      <span className="text-sm text-[var(--foreground)] font-semibold">{formatEnum(d.type)}</span>
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
