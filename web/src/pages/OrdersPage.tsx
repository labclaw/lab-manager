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
  ClipboardCheck,
  Package,
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

export function OrdersPage({ onError }: OrdersPageProps) {
  const [page, setPage] = useState(1)
  const [activeTab, setActiveTab] = useState<TabValue>('active')
  const pageSize = 20

  const { data: res, isLoading, error } = useQuery({
    queryKey: ['orders', page, activeTab],
    queryFn: () => ordApi.list(page, pageSize),
  })

  useEffect(() => {
    if (error) {
      onError(error instanceof Error ? error.message : 'Failed to load orders')
    }
  }, [error, onError])

  const allOrders = res?.items ?? []

  const activeCount = allOrders.filter((o) => o.status !== 'received' && o.status !== 'cancelled').length

  // Filter by tab
  const orders = allOrders.filter((o) => {
    if (activeTab === 'active') return o.status !== 'received' && o.status !== 'cancelled'
    if (activeTab === 'past') return o.status === 'received' || o.status === 'cancelled'
    return false // drafts: none from API currently
  })

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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <div className="flex justify-between items-end">
          <div>
            <h2 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight">Orders</h2>
            <p className="text-gray-500 dark:text-gray-400 mt-2 text-sm">
              {allOrders.length > 0
                ? `${activeCount} active, ${allOrders.length - activeCount} completed across ${allOrders.length} total orders.`
                : 'No orders yet. Orders are created when documents are processed.'}
            </p>
          </div>
          <button disabled className="bg-gradient-to-br from-primary to-primary-container text-white px-6 py-3 rounded-xl font-bold flex items-center shadow-lg opacity-50 cursor-not-allowed" title="Coming soon">
            <ShoppingCart className="mr-2" />
            New Requisition
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center space-x-8 border-b border-outline">
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
            <ShoppingCart className="text-on-surface-variant" />
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
            <div className="lg:col-span-12 bg-surface-container-lowest border border-outline rounded-xl p-8 shadow-sm hover:shadow-md transition-shadow relative overflow-hidden">
              <div className="absolute top-0 left-0 w-1.5 h-full bg-primary" />
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-8">
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <h3 className="text-lg font-bold text-on-surface">
                      Order #{featured.po_number ?? featured.id}
                    </h3>
                    <span className="bg-secondary-container text-on-secondary-container px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest">
                      {featured.status ? formatEnum(featured.status) : 'Unknown'}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-on-surface-variant flex items-center">
                    <FlaskConical className="size-4 mr-1" />
                    {featured.vendor_name ?? 'Unknown'} {featured.order_date ? `\u00B7 ${formatDate(featured.order_date)}` : ''}
                  </p>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-primary text-sm font-semibold hover:underline cursor-pointer">View Invoice</span>
                  <button className="bg-surface-container-high text-primary px-5 py-2.5 rounded-xl font-bold text-sm hover:bg-surface-container-highest transition-colors">
                    Track Package
                  </button>
                </div>
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
                    <span className={`text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded mb-2 inline-block ${
                      isPending
                        ? 'text-on-surface-variant bg-surface-container-high'
                        : 'text-primary bg-primary/10'
                    }`}>
                      {isPending ? 'Pending Approval' : 'Processing'}
                    </span>
                    <h3 className="text-lg font-bold text-on-surface">
                      Order #{order.po_number ?? order.id}
                    </h3>
                    <p className="text-sm font-medium text-on-surface-variant">
                      {order.vendor_name ?? 'Unknown'} {order.order_date ? `\u00B7 ${formatDate(order.order_date)}` : ''}
                    </p>
                  </div>
                  <div className="h-12 w-12 rounded-xl bg-surface-container flex items-center justify-center group-hover:scale-110 transition-transform">
                    {isPending ? (
                      <ClipboardCheck className={`size-6 ${isPending ? 'text-on-surface-variant' : 'text-primary'}`} />
                    ) : (
                      <Package className={`size-6 ${isPending ? 'text-on-surface-variant' : 'text-primary'}`} />
                    )}
                  </div>
                </div>
                <div className="space-y-4">
                  {isPending ? (
                    <div className="p-3 bg-surface-container-low rounded-lg text-[11px] text-on-surface-variant italic">
                      Awaiting sign-off from lab administrator
                    </div>
                  ) : (
                    <div className="flex justify-between items-end">
                      <div className="w-2/3 h-1.5 bg-surface-container rounded-full overflow-hidden">
                        <div className="h-full bg-primary w-[25%]" />
                      </div>
                      <span className="text-[10px] font-bold text-on-surface-variant">25% Progress</span>
                    </div>
                  )}
                  <div className="flex gap-4 pt-2 border-t border-outline">
                    <button className={`flex-1 py-2 rounded-lg font-bold text-xs ${
                      isPending
                        ? 'bg-primary text-white shadow-sm'
                        : 'bg-surface-container-high text-primary'
                    }`}>
                      {isPending ? 'View Details' : 'Track'}
                    </button>
                    <button className="flex-1 text-on-surface-variant py-2 font-bold text-xs hover:text-on-surface transition-colors">
                      Invoice
                    </button>
                  </div>
                </div>
              </div>
            )
          })}

          {/* Bottom Stats */}
          <div className="lg:col-span-12 grid grid-cols-1 md:grid-cols-2 gap-6 mt-4">
            <div className="bg-primary p-6 rounded-xl text-white flex flex-col justify-between shadow-lg">
              <div>
                <h4 className="text-xs font-bold uppercase tracking-widest opacity-80 mb-1">Total Monthly Spend</h4>
                <p className="text-2xl font-extrabold">
                  {formatCurrency(allOrders.reduce((sum, o) => sum + (o.total_amount ?? 0), 0))}
                </p>
              </div>
            </div>
            <div className="bg-surface-container-high border border-outline p-6 rounded-xl flex flex-col justify-between">
              <div>
                <h4 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-1">Items in Transit</h4>
                <p className="text-2xl font-extrabold text-on-surface">
                  {allOrders.filter((o) => o.status === 'shipped').reduce((sum, o) => sum + (o.item_count ?? 0), 0)}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
