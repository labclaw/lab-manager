import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { orders as ordApi } from '@/lib/api'
import { formatEnum } from '@/lib/utils'
import {
  Check,
  Truck,
  Building2,
  PackageCheck,
  ShoppingCart,
  FlaskConical,
  Package,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'

interface OrdersPageProps {
  readonly onError: (msg: string) => void
}

type TabValue = 'active' | 'past' | 'drafts'

const TABS: { readonly value: TabValue; readonly label: string }[] = [
  { value: 'active', label: 'Active Orders' },
  { value: 'past', label: 'Past Orders' },
  { value: 'drafts', label: 'Drafts' },
]

const STATUS_PROGRESS: Record<string, number> = {
  pending: 0,
  ordered: 1,
  shipped: 2,
  out_for_delivery: 3,
  received: 4,
}

const PROGRESS_STEPS = [
  { key: 'ordered', label: 'Ordered', icon: Check },
  { key: 'shipped', label: 'Shipped', icon: Truck },
  { key: 'out_for_delivery', label: 'Out for Delivery', icon: Building2 },
  { key: 'received', label: 'Received', icon: PackageCheck },
] as const

const STATUS_BADGE_STYLES: Record<string, string> = {
  pending: 'text-on-surface-variant bg-surface-container-high',
  ordered: 'text-primary bg-primary/10',
  shipped: 'text-blue-700 bg-blue-100',
  out_for_delivery: 'text-amber-700 bg-amber-100',
  received: 'text-green-700 bg-green-100',
  cancelled: 'text-red-700 bg-red-100',
}

export function OrdersPage({ onError }: OrdersPageProps) {
  const [page, setPage] = useState(1)
  const [activeTab, setActiveTab] = useState<TabValue>('active')
  const [expandedOrder, setExpandedOrder] = useState<number | null>(null)
  const pageSize = 20

  const { data: res, isLoading, error } = useQuery({
    queryKey: ['orders', page, activeTab],
    queryFn: () => ordApi.list(page, pageSize, activeTab),
  })

  useEffect(() => {
    if (error) {
      onError(error instanceof Error ? error.message : 'Failed to load orders')
    }
  }, [error, onError])

  const orders = res?.items ?? []

  const formatCurrency = (amount?: number) => {
    if (amount == null) return '\u2014'
    return `$${amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  const formatDate = (date?: string) => {
    if (!date) return ''
    return new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  // Pick featured order (first shipped/ordered) and secondary orders
  const featured = orders.find((o) => o.status === 'shipped' || o.status === 'ordered') ?? orders[0]
  const secondary = orders.filter((o) => o.id !== featured?.id).slice(0, 2)

  const getProgressIndex = (status?: string) => STATUS_PROGRESS[status ?? ''] ?? 0

  const getStatusBadgeStyle = (status?: string) =>
    STATUS_BADGE_STYLES[status ?? ''] ?? 'text-on-surface-variant bg-surface-container-high'

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6 md:space-y-8">
      {/* Header */}
      <div>
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4">
          <div>
            <h2 className="text-2xl md:text-3xl font-bold text-gray-900 tracking-tight">Orders</h2>
            <p className="text-gray-500 mt-1 md:mt-2 text-sm">
              {orders.length > 0
                ? `${orders.length} orders shown.`
                : 'No orders yet. Orders are created when documents are processed.'}
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center space-x-4 md:space-x-8 border-b border-outline overflow-x-auto">
        {TABS.map((tab) => (
          <button
            type="button"
            key={tab.value}
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); setActiveTab(tab.value); setPage(1) }}
            className={`pb-4 border-b-2 text-sm tracking-wide transition-all ${
              activeTab === tab.value
                ? 'text-primary font-bold border-primary'
                : 'text-on-surface-variant font-medium border-transparent hover:text-on-surface'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Bento Grid */}
      {orders.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center space-y-4">
          <div className="w-12 h-12 rounded-2xl bg-surface-container-high flex items-center justify-center">
            <ShoppingCart className="size-5 text-[var(--muted-foreground)]" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-semibold text-on-surface">No orders found</h3>
            <p className="text-sm text-on-surface-variant max-w-xs mx-auto">
              {activeTab === 'active' ? 'No active orders right now.' : activeTab === 'past' ? 'No past orders yet.' : 'No drafts saved.'}
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Featured Card (full width) */}
          {featured && (
            <div className="lg:col-span-12 bg-surface-container-lowest border border-outline rounded-xl p-4 md:p-8 shadow-sm hover:shadow-md transition-shadow relative overflow-hidden">
              <div className="absolute top-0 left-0 w-1.5 h-full bg-primary" />
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 md:gap-6 mb-6 md:mb-8">
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <h3 className="text-lg font-bold text-on-surface">
                      Order #{featured.po_number ?? featured.id}
                    </h3>
                    <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest ${getStatusBadgeStyle(featured.status)}`}>
                      {featured.status ? formatEnum(featured.status) : 'Unknown'}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-on-surface-variant flex items-center">
                    <FlaskConical className="size-4 mr-1" />
                    {featured.vendor_name ?? 'Unknown'} {featured.order_date ? `\u00B7 ${formatDate(featured.order_date)}` : ''}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setExpandedOrder(expandedOrder === featured.id ? null : featured.id)}
                  className="bg-surface-container-high text-on-surface px-5 py-2.5 rounded-xl font-bold text-sm hover:bg-surface-container transition-colors flex items-center gap-2"
                >
                  View Details
                  {expandedOrder === featured.id ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                </button>
              </div>

              {/* Progress Tracker */}
              <div className="relative pt-4 pb-2 px-2">
                <div className="absolute top-8 left-0 w-full h-1 bg-surface-container rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary"
                    style={{ width: `${(getProgressIndex(featured.status) / (PROGRESS_STEPS.length - 1)) * 100}%` }}
                  />
                </div>
                <div className="grid grid-cols-4 relative">
                  {PROGRESS_STEPS.map((step, i) => {
                    const active = i < getProgressIndex(featured.status)
                    const current = i === getProgressIndex(featured.status)
                    const StepIcon = active ? Check : step.icon
                    return (
                      <div key={step.key} className="flex flex-col items-center">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center z-10 shadow-md ${
                          active || current
                            ? 'bg-primary text-white'
                            : 'bg-surface-container text-[var(--muted-foreground)]/40 border border-outline'
                        }`}>
                          <StepIcon className="size-4" />
                        </div>
                        <span className={`text-[10px] font-bold mt-3 uppercase tracking-tighter ${
                          active || current ? 'text-on-surface' : 'text-on-surface-variant opacity-50'
                        }`}>
                          {step.label}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Expandable Details */}
              {expandedOrder === featured.id && (
                <div className="mt-6 pt-6 border-t border-outline grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="order-details">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">PO Number</p>
                    <p className="text-sm font-semibold text-on-surface">{featured.po_number ?? '\u2014'}</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Total Amount</p>
                    <p className="text-sm font-semibold text-on-surface">{formatCurrency(featured.total_amount)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Items</p>
                    <p className="text-sm font-semibold text-on-surface">{featured.item_count ?? '\u2014'}</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Vendor</p>
                    <p className="text-sm font-semibold text-on-surface">{featured.vendor_name ?? '\u2014'}</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Secondary Cards */}
          {secondary.map((order) => {
            const isPending = order.status === 'pending'
            return (
              <div
                key={order.id}
                className={`lg:col-span-6 bg-surface-container-lowest border rounded-xl p-6 shadow-sm flex flex-col justify-between group hover:shadow-md transition-all ${
                  isPending ? 'border-dashed border-2 border-outline' : 'border-outline'
                }`}
              >
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <span className={`text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded mb-2 inline-block ${getStatusBadgeStyle(order.status)}`}>
                      {order.status ? formatEnum(order.status) : 'Unknown'}
                    </span>
                    <h3 className="text-lg font-bold text-on-surface">
                      Order #{order.po_number ?? order.id}
                    </h3>
                    <p className="text-sm font-medium text-on-surface-variant">
                      {order.vendor_name ?? 'Unknown'} {order.order_date ? `\u00B7 ${formatDate(order.order_date)}` : ''}
                    </p>
                  </div>
                  <div className="h-12 w-12 rounded-xl bg-surface-container flex items-center justify-center group-hover:scale-110 transition-transform">
                    <Package className={`size-6 ${isPending ? 'text-on-surface-variant' : 'text-primary'}`} />
                  </div>
                </div>
                <div className="space-y-4">
                  {isPending && (
                    <div className="p-3 bg-surface-container-low rounded-lg text-[11px] text-on-surface-variant italic">
                      Awaiting sign-off from lab administrator
                    </div>
                  )}
                  <div className="flex justify-between items-center text-sm text-on-surface-variant">
                    <span>{formatCurrency(order.total_amount)}</span>
                    <span>{order.item_count != null ? `${order.item_count} items` : ''}</span>
                  </div>
                </div>
              </div>
            )
          })}

          {/* Bottom Stats */}
          <div className="lg:col-span-12 grid grid-cols-1 md:grid-cols-2 gap-6 mt-4">
            <div className="bg-primary p-6 rounded-xl text-white flex flex-col justify-between shadow-lg">
              <div>
                <h4 className="text-xs font-bold uppercase tracking-widest opacity-80 mb-1">Total Spend</h4>
                <p className="text-2xl font-extrabold">
                  {formatCurrency(orders.reduce((sum, o) => sum + (o.total_amount ?? 0), 0))}
                </p>
              </div>
            </div>
            <div className="bg-surface-container-high border border-outline p-6 rounded-xl flex flex-col justify-between">
              <div>
                <h4 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-1">Items in Transit</h4>
                <p className="text-2xl font-extrabold text-on-surface">
                  {orders.filter((o) => o.status === 'shipped').reduce((sum, o) => sum + (o.item_count ?? 0), 0)}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
