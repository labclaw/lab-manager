import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { inventory as invApi } from '@/lib/api'
import { SkeletonTable } from '@/components/ui/SkeletonTable'
import { EmptyState } from '@/components/ui/EmptyState'

interface InventoryPageProps {
  readonly onError: (msg: string) => void
}

export function InventoryPage({ onError }: InventoryPageProps) {
  const [page, setPage] = useState(1)
  const pageSize = 15

  const { data: res, isLoading, error } = useQuery({
    queryKey: ['inventory', page],
    queryFn: () => invApi.list(page, pageSize),
  })

  useEffect(() => {
    if (error) {
      onError(error instanceof Error ? error.message : 'Failed to load inventory')
    }
  }, [error, onError])

  const items = res?.items ?? []
  const total = res?.total ?? 0
  const totalPages = res?.pages ?? Math.ceil(total / pageSize)

  const stockBadge = (status?: string, quantity?: number) => {
    if (status === 'low_stock' || (quantity != null && quantity <= 3)) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 mt-1 rounded-full bg-tertiary-fixed text-on-tertiary-fixed-variant text-[10px] font-bold w-fit uppercase">
          Low Stock
        </span>
      )
    }
    return (
      <span className="inline-flex items-center px-2 py-0.5 mt-1 rounded-full bg-secondary-container text-on-surface text-[10px] font-bold w-fit uppercase">
        In Stock
      </span>
    )
  }

  const itemIcon = (status?: string) => {
    if (status === 'low_stock' || status === 'expired') {
      return (
        <div className="w-10 h-10 rounded-lg bg-error-container flex items-center justify-center">
          <span className="material-symbols-outlined text-error" style={{ fontVariationSettings: "'FILL' 1" }}>biotech</span>
        </div>
      )
    }
    return (
      <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
        <span className="material-symbols-outlined text-primary">experiment</span>
      </div>
    )
  }

  const startItem = (page - 1) * pageSize + 1
  const endItem = Math.min(page * pageSize, total)

  // Generate page numbers for pagination
  const pageNumbers: (number | 'ellipsis')[] = []
  if (totalPages <= 5) {
    for (let i = 1; i <= totalPages; i++) pageNumbers.push(i)
  } else {
    pageNumbers.push(1)
    if (page > 3) pageNumbers.push('ellipsis')
    for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) {
      pageNumbers.push(i)
    }
    if (page < totalPages - 2) pageNumbers.push('ellipsis')
    pageNumbers.push(totalPages)
  }

  if (isLoading) {
    return (
      <div className="flex flex-col gap-8">
        <SkeletonTable rows={15} columns={8} />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-8">
      {/* Filters & Actions Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button disabled className="flex items-center gap-2 px-4 py-2 bg-[var(--card)] rounded-xl shadow-sm text-sm font-medium border border-outline opacity-50 cursor-not-allowed" title="Coming soon">
            <span className="material-symbols-outlined text-lg">filter_list</span>
            <span>Filters</span>
          </button>
          <button disabled className="flex items-center gap-2 px-4 py-2 bg-[var(--card)] rounded-xl shadow-sm text-sm font-medium border border-outline opacity-50 cursor-not-allowed" title="Coming soon">
            <span className="material-symbols-outlined text-lg">category</span>
            <span>Category</span>
          </button>
          <div className="h-6 w-px bg-[var(--border)] mx-2" />
          <span className="text-xs text-[var(--muted-foreground)] font-medium">
            {total.toLocaleString()} Items total
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button disabled className="bg-surface-container-high text-primary font-semibold px-6 py-2.5 rounded-xl text-sm flex items-center gap-2 opacity-50 cursor-not-allowed" title="Coming soon">
            <span className="material-symbols-outlined text-lg">add_circle</span>
            <span>New Item</span>
          </button>
          <button disabled className="bg-primary text-white font-semibold px-6 py-2.5 rounded-xl text-sm flex items-center gap-2 shadow-lg shadow-primary/20 opacity-50 cursor-not-allowed" title="Coming soon">
            <span className="material-symbols-outlined text-lg">local_shipping</span>
            <span>Bulk Order</span>
          </button>
        </div>
      </div>

      {/* Inventory Data Table */}
      <section className="bg-[var(--card)] rounded-[2rem] shadow-sm overflow-hidden flex flex-col flex-1 border border-outline">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-surface-container-high/50">
                <th className="px-8 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Item Name</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Lot #</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Vendor</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Location</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Stock</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline">
              {items.map((item) => (
                <tr key={item.id} className="hover:bg-surface-container-high/30 transition-colors group">
                  <td className="px-8 py-6">
                    <div className="flex items-center gap-4">
                      {itemIcon(item.status)}
                      <div>
                        <p className="font-bold text-on-surface">
                          {item.product_name ?? `Product #${item.product_id}`}
                        </p>
                        <p className="text-[11px] text-[var(--muted-foreground)]">
                          {item.lot_number ? `Lot ${item.lot_number}` : (item.unit ?? '')}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-6 text-sm font-mono text-[var(--muted-foreground)]">
                    {item.lot_number ?? '\u2014'}
                  </td>
                  <td className="px-6 py-6 text-sm font-medium">
                    {'\u2014'}
                  </td>
                  <td className="px-6 py-6">
                    {item.location_name ? (
                      <span className="inline-flex items-center px-2.5 py-1 rounded-lg bg-surface-container-high text-[var(--muted-foreground)] text-xs font-medium border border-outline">
                        <span className="material-symbols-outlined text-[14px] mr-1">meeting_room</span>
                        {item.location_name}
                      </span>
                    ) : (
                      <span className="text-[var(--muted-foreground)]">{'\u2014'}</span>
                    )}
                  </td>
                  <td className="px-6 py-6">
                    <div className="flex flex-col">
                      <span className="text-sm font-bold text-on-surface">
                        {item.quantity ?? 0} {item.unit ?? ''}
                      </span>
                      {stockBadge(item.status, item.quantity)}
                    </div>
                  </td>
                  <td className="px-6 py-6 text-right">
                    <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button className="p-2 hover:bg-primary/20 text-primary rounded-lg transition-colors" title="Order More">
                        <span className="material-symbols-outlined">shopping_cart_checkout</span>
                      </button>
                      <button className="p-2 hover:bg-surface-container-highest text-[var(--muted-foreground)] rounded-lg transition-colors" title="Edit Item">
                        <span className="material-symbols-outlined">edit</span>
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {items.length === 0 && (
            <EmptyState
              icon="inventory_2"
              title="Inventory is empty"
              description="Process documents through the review queue to populate inventory."
            />
          )}
        </div>

        {/* Pagination Footer */}
        {total > 0 && (
          <div className="mt-auto px-8 py-4 bg-surface-container-lowest/30 border-t border-outline flex items-center justify-between">
            <span className="text-xs text-[var(--muted-foreground)] font-medium">
              Showing {startItem}-{endItem} of {total.toLocaleString()} items
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-surface-container-highest transition-colors disabled:opacity-30"
              >
                <span className="material-symbols-outlined text-sm">chevron_left</span>
              </button>
              {pageNumbers.map((pn, idx) =>
                pn === 'ellipsis' ? (
                  <span key={`e${idx}`} className="text-slate-500/50 text-xs px-1">...</span>
                ) : (
                  <button
                    key={pn}
                    onClick={() => setPage(pn)}
                    className={`w-8 h-8 flex items-center justify-center rounded-lg text-xs font-bold transition-colors ${
                      pn === page
                        ? 'bg-primary text-white'
                        : 'hover:bg-surface-container-highest font-medium'
                    }`}
                  >
                    {pn}
                  </button>
                )
              )}
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-surface-container-highest transition-colors disabled:opacity-30"
              >
                <span className="material-symbols-outlined text-sm">chevron_right</span>
              </button>
            </div>
          </div>
        )}
      </section>

    </div>
  )
}
