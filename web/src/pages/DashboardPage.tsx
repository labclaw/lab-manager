import { useQuery } from '@tanstack/react-query'
import { analytics } from '@/lib/api'
import {
  FileText,
  CheckCircle2,
  AlertTriangle,
  ShoppingCart,
  Store,
  TrendingUp,
  Package,
} from 'lucide-react'

interface DocStats {
  total_documents: number
  documents_approved: number
  documents_pending_review: number
  total_products: number
  total_vendors: number
  total_orders: number
  total_inventory_items: number
  total_staff: number
  orders_by_status?: Record<string, number>
  inventory_by_status?: Record<string, number>
  recent_orders?: Array<{ id: number; po_number: string | null; vendor_name: string; status: string; order_date: string }>
  expiring_soon?: Array<{ id: number; product_name: string | null; lot_number: string | null; quantity_on_hand: number | null; expiry_date: string | null }>
  low_stock_count?: number
}

interface DashboardPageProps {
  onError?: (error: string) => void
}

export function DashboardPage({ onError }: DashboardPageProps) {
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => analytics.dashboard() as Promise<DocStats>,
  })

  if (error && onError) {
    onError(error instanceof Error ? error.message : 'Failed to load dashboard data')
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-[var(--primary)]/30 border-t-[var(--primary)] rounded-full animate-spin" />
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="text-center py-16 text-[var(--muted-foreground)]">
        Failed to load dashboard data.
      </div>
    )
  }

  const cards = [
    {
      icon: FileText,
      label: 'Total Documents',
      value: stats.total_documents,
      sub: 'scanned lab documents',
      color: 'text-[var(--primary)]',
      bg: 'bg-[var(--primary)]/10',
    },
    {
      icon: CheckCircle2,
      label: 'Approved',
      value: stats.documents_approved ?? 0,
      sub:
        stats.total_documents > 0
          ? `${(((stats.documents_approved ?? 0) / stats.total_documents) * 100).toFixed(0)}% auto-approved`
          : '0% auto-approved',
      color: 'text-[var(--accent)]',
      bg: 'bg-[var(--accent)]/10',
    },
    {
      icon: AlertTriangle,
      label: 'Needs Review',
      value: stats.documents_pending_review ?? 0,
      sub: 'awaiting scientist verification',
      color: 'text-[var(--warning)]',
      bg: 'bg-[var(--warning)]/10',
    },
    {
      icon: ShoppingCart,
      label: 'Orders',
      value: stats.total_orders,
      sub: `${stats.total_inventory_items ?? 0} line items`,
      color: 'text-[var(--info)]',
      bg: 'bg-[var(--info)]/10',
    },
    {
      icon: Store,
      label: 'Vendors',
      value: stats.total_vendors,
      sub: 'discovered from scans',
      color: 'text-[var(--foreground)]',
      bg: 'bg-[var(--muted)]',
    },
    {
      icon: TrendingUp,
      label: 'Products',
      value: stats.total_products,
      sub: `${stats.total_inventory_items ?? 0} inventory items`,
      color: 'text-[var(--foreground)]',
      bg: 'bg-[var(--muted)]',
    },
  ]

  const maxStatus = Math.max(
    ...Object.values(stats.orders_by_status ?? {}),
    1,
  )

  const maxInvStatus = Math.max(
    ...Object.values(stats.inventory_by_status ?? {}),
    1,
  )

  return (
    <div className="space-y-6">
      {/* Alert banner */}
      {(stats.documents_pending_review ?? 0) > 10 && (
        <div className="flex items-center gap-3 p-3 rounded-lg border border-[var(--warning)]/30 bg-[var(--warning)]/5">
          <AlertTriangle className="w-5 h-5 text-[var(--warning)] shrink-0" />
          <span className="text-sm text-[var(--warning)]">
            {stats.documents_pending_review} documents awaiting review
          </span>
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        {cards.map((c) => (
          <div key={c.label} className="card">
            <div className="flex items-center gap-3 mb-3">
              <div className={`p-2 rounded-lg ${c.bg}`}>
                <c.icon className={`w-4 h-4 ${c.color}`} />
              </div>
              <span className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider font-medium">
                {c.label}
              </span>
            </div>
            <div className={`text-2xl font-bold ${c.color}`}>{c.value}</div>
            <div className="text-xs text-[var(--muted-foreground)] mt-1">{c.sub}</div>
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Orders by Status */}
        <div className="card">
          <h3 className="text-sm font-semibold text-[var(--foreground)] mb-4">
            Orders by Status
          </h3>
          {Object.entries(stats.orders_by_status ?? {}).length > 0 ? (
            <div className="space-y-3">
              {Object.entries(stats.orders_by_status ?? {})
                .sort((a, b) => b[1] - a[1])
                .slice(0, 8)
                .map(([name, count]) => (
                  <div key={name} className="flex items-center gap-3 text-sm">
                    <div className="w-40 text-right text-[var(--muted-foreground)] truncate capitalize" title={name}>
                      {name.replace(/_/g, ' ')}
                    </div>
                    <div
                      className="h-5 bg-[var(--primary)] rounded"
                      style={{ width: `${(count / maxStatus) * 200}px`, minWidth: '4px' }}
                    />
                    <div className="text-[var(--foreground)] font-semibold w-8 tabular-nums">
                      {count}
                    </div>
                  </div>
                ))}
            </div>
          ) : (
            <div className="text-sm text-[var(--muted-foreground)] py-4">
              No order data yet
            </div>
          )}
        </div>

        {/* Inventory by Status */}
        <div className="card">
          <h3 className="text-sm font-semibold text-[var(--foreground)] mb-4">
            Inventory by Status
          </h3>
          {Object.entries(stats.inventory_by_status ?? {}).length > 0 ? (
            <div className="space-y-3">
              {Object.entries(stats.inventory_by_status ?? {})
                .sort((a, b) => b[1] - a[1])
                .slice(0, 8)
                .map(([name, count]) => (
                  <div key={name} className="flex items-center gap-3 text-sm">
                    <div className="w-40 text-right text-[var(--muted-foreground)] truncate capitalize" title={name}>
                      {name.replace(/_/g, ' ')}
                    </div>
                    <div
                      className="h-5 bg-[var(--accent)] rounded"
                      style={{ width: `${(count / maxInvStatus) * 200}px`, minWidth: '4px' }}
                    />
                    <div className="text-[var(--foreground)] font-semibold w-8 tabular-nums">
                      {count}
                    </div>
                  </div>
                ))}
            </div>
          ) : (
            <div className="text-sm text-[var(--muted-foreground)] py-4">
              No inventory data yet
            </div>
          )}
        </div>
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Orders */}
        <div className="card">
          <h3 className="text-sm font-semibold text-[var(--foreground)] mb-4">
            Recent Orders
          </h3>
          {stats.recent_orders && stats.recent_orders.length > 0 ? (
            <div className="space-y-2">
              {stats.recent_orders.slice(0, 5).map((o) => (
                <div key={o.id} className="flex items-center justify-between text-sm py-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[var(--foreground)] font-medium">
                      {o.vendor_name ?? 'Unknown'}
                    </span>
                    <span className="text-[var(--muted-foreground)]">
                      {o.po_number ? `#${o.po_number}` : `#${o.id}`}
                    </span>
                  </div>
                  <span className={`badge ${o.status === 'received' ? 'badge-accent' : o.status === 'pending' ? 'badge-warning' : 'badge-info'}`}>
                    {o.status ?? 'unknown'}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-[var(--muted-foreground)] py-4">
              No orders yet
            </div>
          )}
        </div>

        {/* Expiring Soon */}
        <div className="card">
          <h3 className="text-sm font-semibold text-[var(--foreground)] mb-4 flex items-center gap-2">
            <Package className="w-4 h-4" />
            Expiring Soon (30 days)
          </h3>
          {stats.expiring_soon && stats.expiring_soon.length > 0 ? (
            <div className="space-y-2">
              {stats.expiring_soon.slice(0, 5).map((item) => (
                <div key={item.id} className="flex items-center justify-between text-sm py-1">
                  <div>
                    <span className="text-[var(--foreground)]">{item.product_name ?? 'Unknown'}</span>
                    {item.lot_number && (
                      <span className="text-[var(--muted-foreground)] ml-2">Lot {item.lot_number}</span>
                    )}
                  </div>
                  <span className="text-[var(--warning)] tabular-nums">
                    {item.expiry_date ?? '?'}
                  </span>
                </div>
              ))}
              {stats.expiring_soon.length > 5 && (
                <div className="text-xs text-[var(--muted-foreground)] pt-1">
                  +{stats.expiring_soon.length - 5} more items
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm text-[var(--muted-foreground)] py-4">
              No items expiring soon
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
