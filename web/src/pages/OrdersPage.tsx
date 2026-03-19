import { useEffect, useState } from 'react'
import { orders as ordApi } from '@/lib/api'
import type { Order } from '@/lib/api'
import { Search, ChevronLeft, ChevronRight, RefreshCw, ShoppingCart, WifiOff, ClipboardCheck } from 'lucide-react'
import { EmptyState } from '@/components/ui/EmptyState'
import { SkeletonTable } from '@/components/ui/SkeletonTable'
import { Link } from 'react-router-dom'

const STATUS_FILTERS = [
  { value: '', label: 'All Status' },
  { value: 'pending', label: 'Pending' },
  { value: 'received', label: 'Received' },
  { value: 'cancelled', label: 'Cancelled' },
]

interface OrdersPageProps {
  onError?: (error: string) => void
}

export function OrdersPage({ onError }: OrdersPageProps) {
  const [orders, setOrders] = useState<Order[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const pageSize = 25

  const loadOrders = async () => {
    setLoading(true)
    setLoadError(false)
    try {
      const res = await ordApi.list(page, pageSize)
      setOrders(res.items ?? [])
      setTotal(res.total ?? 0)
    } catch (err) {
      console.error('Failed to load orders:', err)
      setLoadError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadOrders()
  }, [page])

  const filtered = orders.filter((o) => {
    if (statusFilter && o.status !== statusFilter) return false
    if (!search) return true
    const q = search.toLowerCase()
    return (
      o.po_number?.toLowerCase().includes(q) ||
      o.vendor_name?.toLowerCase().includes(q)
    )
  })

  const statusColor = (status?: string) => {
    switch (status) {
      case 'pending':
        return 'badge-warning'
      case 'received':
        return 'badge-accent'
      case 'cancelled':
        return 'badge-destructive'
      default:
        return 'badge-info'
    }
  }

  const formatCurrency = (amount?: number) => {
    if (amount == null) return '\u2014'
    return `$${amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  const totalPages = Math.ceil(total / pageSize)

  if (loadError && !loading) {
    return (
      <EmptyState
        icon={WifiOff}
        title="Could not load orders"
        description="Check your connection and try again."
        action={
          <button onClick={loadOrders} className="btn-primary flex items-center gap-2">
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        }
      />
    )
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted-foreground)]" />
          <input
            type="text"
            placeholder="Search PO numbers, vendors..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-[var(--popover)] border border-[var(--border)] rounded-lg pl-9 pr-3 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="bg-[var(--popover)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
        >
          {STATUS_FILTERS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>
        <button onClick={loadOrders} className="btn-ghost flex items-center gap-2">
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Table */}
      <div className="card !p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)]">
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                PO Number
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                Vendor
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                Order Date
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                Status
              </th>
              <th className="text-right px-4 py-3 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                Amount
              </th>
              <th className="text-right px-4 py-3 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                Items
              </th>
            </tr>
          </thead>
          {loading ? (
            <SkeletonTable columns={6} rows={5} />
          ) : filtered.length === 0 ? null : (
          <tbody>
            {filtered.map((order) => (
              <tr
                key={order.id}
                className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--muted)]/50 transition-colors"
              >
                <td className="px-4 py-3">
                  <span className="text-[var(--foreground)] font-medium">
                    {order.po_number ?? '\u2014'}
                  </span>
                </td>
                <td className="px-4 py-3 text-[var(--muted-foreground)]">
                  {order.vendor_name ?? '\u2014'}
                </td>
                <td className="px-4 py-3 text-[var(--muted-foreground)] tabular-nums">
                  {order.order_date
                    ? new Date(order.order_date).toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                      })
                    : '\u2014'}
                </td>
                <td className="px-4 py-3">
                  <span className={statusColor(order.status)}>
                    {order.status ?? 'unknown'}
                  </span>
                </td>
                <td className="px-4 py-3 text-right text-[var(--foreground)] font-medium tabular-nums">
                  {formatCurrency(order.total_amount)}
                </td>
                <td className="px-4 py-3 text-right text-[var(--muted-foreground)] tabular-nums">
                  {order.item_count ?? 0}
                </td>
              </tr>
            ))}
          </tbody>
          )}
        </table>

        {!loading && filtered.length === 0 && (
          <div className="py-12">
            <EmptyState
              icon={ShoppingCart}
              title={search ? "No matching orders" : "No orders yet"}
              description={search
                ? `No orders found matching "${search}"`
                : "Orders are created when documents are approved in the review queue."}
              action={
                search ? undefined : (
                  <Link to="/review" className="btn-primary flex items-center gap-2">
                    <ClipboardCheck className="w-4 h-4" />
                    Go to Review Queue
                  </Link>
                )
              }
            />
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-[var(--muted-foreground)]">
            {total} orders
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="btn-ghost p-2"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-sm text-[var(--foreground)]">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="btn-ghost p-2"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
