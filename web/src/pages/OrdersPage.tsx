import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { orders as ordApi } from '@/lib/api'

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
  { key: 'ordered', label: 'Ordered', icon: 'check' },
  { key: 'shipped', label: 'Shipped', icon: 'local_shipping' },
  { key: 'out_for_delivery', label: 'Out for Delivery', icon: 'home_work' },
  { key: 'received', label: 'Received', icon: 'inventory' },
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
  const total = res?.total ?? 0

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
        <div className="w-8 h-8 border-2 border-[var(--primary)]/30 border-t-[var(--primary)] rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center text-xs text-[var(--muted-foreground)] font-medium uppercase tracking-wider mb-2">
          <span>Procurement</span>
          <span className="material-symbols-outlined text-[10px] mx-2">chevron_right</span>
          <span className="text-[var(--primary)] font-bold">Supply Chains</span>
        </div>
        <div className="flex justify-between items-end">
          <div>
            <h2 className="text-4xl font-extrabold text-[var(--foreground)] tracking-tight">Orders</h2>
            <p className="text-[var(--muted-foreground)] mt-2 text-sm">
              Tracking {total} active shipments and pending procurement requisitions.
            </p>
          </div>
          <button className="bg-[var(--primary)] text-white px-6 py-3 rounded-xl font-bold flex items-center shadow-lg hover:brightness-110 transition-transform">
            <span className="material-symbols-outlined mr-2">add_shopping_cart</span>
            New Requisition
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center space-x-8 border-b border-[var(--border)]">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => { setActiveTab(tab.value); setPage(1) }}
            className={`pb-4 border-b-2 text-sm tracking-wide transition-all ${
              activeTab === tab.value
                ? 'text-[var(--primary)] font-bold border-[var(--primary)]'
                : 'text-[var(--muted-foreground)] font-medium border-transparent hover:text-[var(--foreground)]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Bento Grid */}
      {orders.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center space-y-4">
          <div className="w-12 h-12 rounded-2xl bg-[var(--muted)] flex items-center justify-center">
            <span className="material-symbols-outlined text-[var(--muted-foreground)]">shopping_cart</span>
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-semibold text-[var(--foreground)]">No orders found</h3>
            <p className="text-sm text-[var(--muted-foreground)] max-w-xs mx-auto">
              {activeTab === 'active' ? 'No active orders right now.' : activeTab === 'past' ? 'No past orders yet.' : 'No drafts saved.'}
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Featured Card (full width) */}
          {featured && (
            <div className="lg:col-span-12 bg-[var(--card)] border border-[var(--border)] rounded-xl p-8 shadow-sm hover:shadow-md transition-shadow relative overflow-hidden">
              <div className="absolute top-0 left-0 w-1.5 h-full bg-[var(--primary)]" />
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-8">
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <h3 className="text-lg font-bold text-[var(--foreground)]">
                      Order #{featured.po_number ?? featured.id}
                    </h3>
                    <span className="badge badge-primary text-[10px] uppercase tracking-widest">
                      {featured.status ?? 'unknown'}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-[var(--muted-foreground)] flex items-center">
                    <span className="material-symbols-outlined text-sm mr-1">science</span>
                    {featured.vendor_name ?? 'Unknown'} {featured.order_date ? `\u00B7 ${formatDate(featured.order_date)}` : ''}
                  </p>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-[var(--primary)] text-sm font-semibold hover:underline cursor-pointer">View Invoice</span>
                  <button className="bg-[var(--muted)] text-[var(--primary)] px-5 py-2.5 rounded-xl font-bold text-sm hover:brightness-110 transition-colors">
                    Track Package
                  </button>
                </div>
              </div>

              {/* Progress Tracker */}
              <div className="relative pt-4 pb-2 px-2">
                <div className="absolute top-8 left-0 w-full h-1 bg-[var(--muted)] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[var(--primary)]"
                    style={{ width: `${(getProgressIndex(featured.status) / (PROGRESS_STEPS.length - 1)) * 100}%` }}
                  />
                </div>
                <div className="grid grid-cols-4 relative">
                  {PROGRESS_STEPS.map((step, i) => {
                    const active = i < getProgressIndex(featured.status)
                    const current = i === getProgressIndex(featured.status)
                    return (
                      <div key={step.key} className="flex flex-col items-center">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center z-10 shadow-md ${
                          active || current
                            ? 'bg-[var(--primary)] text-white'
                            : 'bg-[var(--muted)] text-[var(--muted-foreground)] border border-[var(--border)]'
                        }`}>
                          <span className="material-symbols-outlined text-sm"
                            style={active ? { fontVariationSettings: "'FILL' 1" } : undefined}
                          >
                            {active ? 'check' : step.icon}
                          </span>
                        </div>
                        <span className={`text-[10px] font-bold mt-3 uppercase tracking-tighter ${
                          active || current ? 'text-[var(--foreground)]' : 'text-[var(--muted-foreground)] opacity-50'
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
                className={`lg:col-span-6 bg-[var(--card)] border rounded-xl p-6 shadow-sm flex flex-col justify-between group hover:shadow-md transition-all ${
                  isPending ? 'border-dashed border-2 border-[var(--border)]' : 'border-[var(--border)]'
                }`}
              >
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <span className={`text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded mb-2 inline-block ${
                      isPending
                        ? 'text-[var(--muted-foreground)] bg-[var(--muted)]'
                        : 'text-[var(--primary)] bg-[var(--primary)]/10'
                    }`}>
                      {isPending ? 'Pending Approval' : 'Processing'}
                    </span>
                    <h3 className="text-lg font-bold text-[var(--foreground)]">
                      Order #{order.po_number ?? order.id}
                    </h3>
                    <p className="text-sm font-medium text-[var(--muted-foreground)]">
                      {order.vendor_name ?? 'Unknown'} {order.order_date ? `\u00B7 ${formatDate(order.order_date)}` : ''}
                    </p>
                  </div>
                  <div className="h-12 w-12 rounded-xl bg-[var(--muted)] flex items-center justify-center group-hover:scale-110 transition-transform">
                    <span className={`material-symbols-outlined ${isPending ? 'text-[var(--muted-foreground)]' : 'text-[var(--primary)]'}`}>
                      {isPending ? 'pending_actions' : 'conveyor_belt'}
                    </span>
                  </div>
                </div>
                <div className="space-y-4">
                  {isPending ? (
                    <div className="p-3 bg-[var(--muted)] rounded-lg text-[11px] text-[var(--muted-foreground)] italic">
                      Awaiting sign-off from Lab Manager head (Principal Investigator)
                    </div>
                  ) : (
                    <div className="flex justify-between items-end">
                      <div className="w-2/3 h-1.5 bg-[var(--muted)] rounded-full overflow-hidden">
                        <div className="h-full bg-[var(--primary)] w-[25%]" />
                      </div>
                      <span className="text-[10px] font-bold text-[var(--muted-foreground)]">25% Progress</span>
                    </div>
                  )}
                  <div className="flex gap-4 pt-2 border-t border-[var(--border)]">
                    <button className={`flex-1 py-2 rounded-lg font-bold text-xs ${
                      isPending
                        ? 'bg-[var(--primary)] text-white shadow-sm'
                        : 'bg-[var(--muted)] text-[var(--primary)]'
                    }`}>
                      {isPending ? 'View Details' : 'Track'}
                    </button>
                    <button className="flex-1 text-[var(--muted-foreground)] py-2 font-bold text-xs hover:text-[var(--foreground)] transition-colors">
                      Invoice
                    </button>
                  </div>
                </div>
              </div>
            )
          })}

          {/* Bottom Stats */}
          <div className="lg:col-span-12 grid grid-cols-1 md:grid-cols-3 gap-6 mt-4">
            <div className="bg-[var(--primary)] p-6 rounded-xl text-white flex flex-col justify-between shadow-lg">
              <div>
                <h4 className="text-xs font-bold uppercase tracking-widest opacity-80 mb-1">Total Monthly Spend</h4>
                <p className="text-2xl font-extrabold">
                  {formatCurrency(allOrders.reduce((sum, o) => sum + (o.total_amount ?? 0), 0))}
                </p>
              </div>
              <div className="mt-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-xs">trending_up</span>
                <span className="text-[10px] font-bold">+12% from last month</span>
              </div>
            </div>
            <div className="bg-[var(--card)] border border-[var(--border)] p-6 rounded-xl flex flex-col justify-between">
              <div>
                <h4 className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-1">Delivery Success</h4>
                <p className="text-2xl font-extrabold text-[var(--foreground)]">98.4%</p>
              </div>
              <div className="h-1 w-full bg-[var(--border)] mt-4 rounded-full overflow-hidden">
                <div className="h-full bg-[var(--primary)] w-[98%]" />
              </div>
            </div>
            <div className="bg-[var(--muted)] border border-[var(--border)] p-6 rounded-xl flex flex-col justify-between">
              <div>
                <h4 className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-1">Items in Transit</h4>
                <p className="text-2xl font-extrabold text-[var(--foreground)]">
                  {allOrders.filter((o) => o.status === 'shipped').reduce((sum, o) => sum + (o.item_count ?? 0), 0)}
                </p>
              </div>
              <div className="flex -space-x-2 mt-4 overflow-hidden">
                <div className="h-6 w-6 rounded-full border-2 border-[var(--card)] bg-[var(--muted-foreground)]/30" />
                <div className="h-6 w-6 rounded-full border-2 border-[var(--card)] bg-[var(--muted-foreground)]/20" />
                <div className="h-6 w-6 rounded-full border-2 border-[var(--card)] bg-[var(--primary)] flex items-center justify-center text-[8px] font-bold text-white">+39</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
