import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { inventory as invApi } from '@/lib/api'

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
        <span className="inline-flex items-center px-2 py-0.5 mt-1 rounded-full bg-[var(--warning)]/15 text-[var(--warning)] text-[10px] font-bold w-fit uppercase">
          Low Stock
        </span>
      )
    }
    return (
      <span className="inline-flex items-center px-2 py-0.5 mt-1 rounded-full bg-[var(--accent)]/15 text-[var(--accent)] text-[10px] font-bold w-fit uppercase">
        In Stock
      </span>
    )
  }

  const itemIcon = (status?: string) => {
    if (status === 'low_stock' || status === 'expired') {
      return (
        <div className="w-10 h-10 rounded-lg bg-[var(--destructive)]/10 flex items-center justify-center">
          <span className="material-symbols-outlined text-[var(--destructive)]" style={{ fontVariationSettings: "'FILL' 1" }}>biotech</span>
        </div>
      )
    }
    return (
      <div className="w-10 h-10 rounded-lg bg-[var(--primary)]/15 flex items-center justify-center">
        <span className="material-symbols-outlined text-[var(--primary)]">experiment</span>
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
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-[var(--primary)]/30 border-t-[var(--primary)] rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-8">
      {/* Filters & Actions Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 px-4 py-2 bg-[var(--card)] rounded-xl shadow-sm hover:bg-[var(--muted)] transition-colors text-sm font-medium border border-[var(--border)]">
            <span className="material-symbols-outlined text-lg">filter_list</span>
            <span>Filters</span>
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-[var(--card)] rounded-xl shadow-sm hover:bg-[var(--muted)] transition-colors text-sm font-medium border border-[var(--border)]">
            <span className="material-symbols-outlined text-lg">category</span>
            <span>Category</span>
          </button>
          <div className="h-6 w-px bg-[var(--border)] mx-2" />
          <span className="text-xs text-[var(--muted-foreground)] font-medium">
            {total.toLocaleString()} Items total
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button className="bg-[var(--muted)] text-[var(--primary)] font-semibold px-6 py-2.5 rounded-xl text-sm flex items-center gap-2 hover:brightness-110 transition-colors">
            <span className="material-symbols-outlined text-lg">add_circle</span>
            <span>New Item</span>
          </button>
          <button className="bg-[var(--primary)] text-white font-semibold px-6 py-2.5 rounded-xl text-sm flex items-center gap-2 shadow-lg hover:brightness-110 transition-transform">
            <span className="material-symbols-outlined text-lg">local_shipping</span>
            <span>Bulk Order</span>
          </button>
        </div>
      </div>

      {/* Inventory Data Table */}
      <section className="bg-[var(--card)] rounded-2xl shadow-sm overflow-hidden flex flex-col flex-1 border border-[var(--border)]">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[var(--muted)]/50">
                <th className="px-8 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Item Name</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Catalog #</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Vendor</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Location</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Stock</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {items.map((item) => (
                <tr key={item.id} className="hover:bg-[var(--muted)]/30 transition-colors group">
                  <td className="px-8 py-6">
                    <div className="flex items-center gap-4">
                      {itemIcon(item.status)}
                      <div>
                        <p className="font-bold text-[var(--foreground)]">
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
                  <td className="px-6 py-6 text-sm font-medium text-[var(--foreground)]">
                    {'\u2014'}
                  </td>
                  <td className="px-6 py-6">
                    {item.location_name ? (
                      <span className="inline-flex items-center px-2.5 py-1 rounded-lg bg-[var(--muted)] text-[var(--muted-foreground)] text-xs font-medium border border-[var(--border)]">
                        <span className="material-symbols-outlined text-[14px] mr-1">meeting_room</span>
                        {item.location_name}
                      </span>
                    ) : (
                      <span className="text-[var(--muted-foreground)]">{'\u2014'}</span>
                    )}
                  </td>
                  <td className="px-6 py-6">
                    <div className="flex flex-col">
                      <span className="text-sm font-bold text-[var(--foreground)]">
                        {item.quantity ?? 0} {item.unit ?? ''}
                      </span>
                      {stockBadge(item.status, item.quantity)}
                    </div>
                  </td>
                  <td className="px-6 py-6 text-right">
                    <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button className="p-2 hover:bg-[var(--primary)]/20 text-[var(--primary)] rounded-lg transition-colors" title="Order More">
                        <span className="material-symbols-outlined">shopping_cart_checkout</span>
                      </button>
                      <button className="p-2 hover:bg-[var(--muted)] text-[var(--muted-foreground)] rounded-lg transition-colors" title="Edit Item">
                        <span className="material-symbols-outlined">edit</span>
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {items.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center space-y-4">
              <div className="w-12 h-12 rounded-2xl bg-[var(--muted)] flex items-center justify-center">
                <span className="material-symbols-outlined text-[var(--muted-foreground)]">inventory_2</span>
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-semibold text-[var(--foreground)]">Inventory is empty</h3>
                <p className="text-sm text-[var(--muted-foreground)] max-w-xs mx-auto">
                  Process documents through the review queue to populate inventory.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Pagination Footer */}
        {total > 0 && (
          <div className="mt-auto px-8 py-4 bg-[var(--muted)]/30 border-t border-[var(--border)] flex items-center justify-between">
            <span className="text-xs text-[var(--muted-foreground)] font-medium">
              Showing {startItem}-{endItem} of {total.toLocaleString()} items
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-[var(--muted)] transition-colors disabled:opacity-30"
              >
                <span className="material-symbols-outlined text-sm">chevron_left</span>
              </button>
              {pageNumbers.map((pn, idx) =>
                pn === 'ellipsis' ? (
                  <span key={`e${idx}`} className="text-[var(--muted-foreground)]/50 text-xs px-1">...</span>
                ) : (
                  <button
                    key={pn}
                    onClick={() => setPage(pn)}
                    className={`w-8 h-8 flex items-center justify-center rounded-lg text-xs font-bold transition-colors ${
                      pn === page
                        ? 'bg-[var(--primary)] text-white'
                        : 'hover:bg-[var(--muted)] font-medium'
                    }`}
                  >
                    {pn}
                  </button>
                )
              )}
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-[var(--muted)] transition-colors disabled:opacity-30"
              >
                <span className="material-symbols-outlined text-sm">chevron_right</span>
              </button>
            </div>
          </div>
        )}
      </section>

      {/* Bottom Stats Bento Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="p-6 bg-[var(--card)] rounded-3xl border border-[var(--border)] shadow-sm flex flex-col justify-between">
          <div>
            <span className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest">Storage Status</span>
            <h3 className="text-2xl font-bold mt-1">94%</h3>
          </div>
          <div className="mt-4 w-full bg-[var(--muted)] h-1.5 rounded-full overflow-hidden">
            <div className="bg-[var(--primary)] h-full" style={{ width: '94%' }} />
          </div>
          <p className="text-[11px] text-[var(--muted-foreground)] mt-3 flex items-center gap-1">
            <span className="material-symbols-outlined text-[14px] text-[var(--warning)]">warning</span>
            Freezer #4 nearing capacity
          </p>
        </div>
        <div className="p-6 bg-[var(--card)] rounded-3xl border border-[var(--border)] shadow-sm">
          <span className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest">Monthly Spend</span>
          <h3 className="text-2xl font-bold mt-1 text-[var(--foreground)]">$4,120</h3>
          <div className="mt-4 flex items-center text-[var(--primary)] gap-1">
            <span className="material-symbols-outlined text-sm">trending_up</span>
            <span className="text-xs font-bold">+12% vs last month</span>
          </div>
        </div>
        <div className="p-6 bg-[var(--card)] rounded-3xl border border-[var(--border)] shadow-sm">
          <span className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest">Active Orders</span>
          <h3 className="text-2xl font-bold mt-1 text-[var(--foreground)]">12</h3>
          <div className="mt-4 flex -space-x-2">
            <div className="w-7 h-7 rounded-full bg-[var(--primary)] border-2 border-[var(--card)] flex items-center justify-center text-[10px] text-white font-bold">V</div>
            <div className="w-7 h-7 rounded-full bg-[var(--muted)] border-2 border-[var(--card)] flex items-center justify-center text-[10px] text-[var(--foreground)] font-bold">S</div>
            <div className="w-7 h-7 rounded-full bg-[var(--muted)] border-2 border-[var(--card)] flex items-center justify-center text-[10px] text-[var(--muted-foreground)] font-bold">+9</div>
          </div>
        </div>
        <div className="p-6 bg-[var(--card)] rounded-3xl border border-[var(--border)] shadow-sm">
          <span className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest">Audit Due</span>
          <h3 className="text-2xl font-bold mt-1 text-[var(--foreground)]">14 Days</h3>
          <button className="mt-4 text-xs font-bold text-[var(--primary)] flex items-center gap-1 hover:underline">
            Schedule Review <span className="material-symbols-outlined text-sm">arrow_forward</span>
          </button>
        </div>
      </div>
    </div>
  )
}
