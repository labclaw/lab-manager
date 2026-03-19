import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { inventory as invApi } from '@/lib/api'
import type { InventoryItem } from '@/lib/api'
import { RefreshCw, Search, ChevronLeft, ChevronRight, PackageSearch } from 'lucide-react'
import { EmptyState } from '@/components/ui/EmptyState'

interface InventoryPageProps {
  onError?: (error: string) => void
}

export function InventoryPage({ onError }: InventoryPageProps) {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const pageSize = 20

  const { data: res, isLoading, error, refetch } = useQuery({
    queryKey: ['inventory', page, search],
    queryFn: () => invApi.list(page, pageSize),
  })

  useEffect(() => {
    if (error && onError) {
      onError(error instanceof Error ? error.message : 'Failed to load inventory')
    }
  }, [error, onError])

  const items = res?.items ?? []
  const total = res?.total ?? 0

  const statusColor = (status?: string) => {
    switch (status) {
      case 'active':
        return 'badge-accent'
      case 'low_stock':
        return 'badge-warning'
      case 'expired':
        return 'badge-destructive'
      case 'disposed':
        return 'badge-info'
      default:
        return 'badge-info'
    }
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted-foreground)]" />
          <input
            type="text"
            placeholder="Search products, lots, locations..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-[var(--popover)] border border-[var(--border)] rounded-lg pl-9 pr-3 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          />
        </div>
        <button onClick={() => refetch()} className="btn-ghost flex items-center gap-2">
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      <div className="card !p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)]">
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                Product
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                Location
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                Lot
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                Qty
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                Expiry
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr
                key={item.id}
                className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--muted)]/50 transition-colors"
              >
                <td className="px-4 py-3">
                  <span className="text-[var(--foreground)] font-medium">
                    {item.product_name ?? `Product #${item.product_id}`}
                  </span>
                </td>
                <td className="px-4 py-3 text-[var(--muted-foreground)]">
                  {item.location_name ?? '—'}
                </td>
                <td className="px-4 py-3 text-[var(--muted-foreground)] font-mono text-xs">
                  {item.lot_number ?? '—'}
                </td>
                <td className="px-4 py-3 text-[var(--foreground)] tabular-nums">
                  {item.quantity ?? 0} {item.unit ?? ''}
                </td>
                <td className="px-4 py-3 text-[var(--muted-foreground)] tabular-nums">
                  {item.expiry_date
                    ? new Date(item.expiry_date).toLocaleDateString()
                    : '—'}
                </td>
                <td className="px-4 py-3">
                  <span className={statusColor(item.status)}>
                    {item.status ?? 'unknown'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {items.length === 0 && (
          <div className="py-12">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center space-y-3">
                <div className="w-8 h-8 border-2 border-[var(--primary)]/30 border-t-[var(--primary)] rounded-full animate-spin" />
                <span className="text-sm text-[var(--muted-foreground)] font-medium">Fetching inventory...</span>
              </div>
            ) : (
              <EmptyState
                icon={PackageSearch}
                title={search ? "No matching items" : "No inventory items"}
                description={search ? `No items found matching "${search}"` : "Your laboratory inventory is currently empty."}
              />
            )}
          </div>
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-[var(--muted-foreground)]">
            {total} items
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
