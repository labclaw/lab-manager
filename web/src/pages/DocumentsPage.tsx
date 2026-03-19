import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { documents as docApi } from '@/lib/api'
import type { Document } from '@/lib/api'
import { Search, ChevronLeft, ChevronRight, RefreshCw, FileText } from 'lucide-react'
import { EmptyState } from '@/components/ui/EmptyState'

interface DocumentsPageProps {
  onError?: (error: string) => void
}

export function DocumentsPage({ onError }: DocumentsPageProps) {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const pageSize = 20

  const { data: res, isLoading, error, refetch } = useQuery({
    queryKey: ['documents', page, search],
    queryFn: () => docApi.list(page, pageSize),
  })

  if (error && onError) {
    onError(error instanceof Error ? error.message : 'Failed to load documents')
  }

  const docs = res?.items ?? []
  const total = res?.total ?? 0

  const statusColor = (status?: string) => {
    switch (status) {
      case 'approved':
        return 'badge-accent'
      case 'needs_review':
        return 'badge-warning'
      case 'rejected':
        return 'badge-destructive'
      default:
        return 'badge-info'
    }
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted-foreground)]" />
          <input
            type="text"
            placeholder="Search documents..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-[var(--popover)] border border-[var(--border)] rounded-lg pl-9 pr-3 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          />
        </div>
        <button
          onClick={() => refetch()}
          className="btn-ghost flex items-center gap-2"
        >
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
                Document
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                Vendor
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                Type
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                Status
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                Date
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((doc) => (
              <tr
                key={doc.id}
                className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--muted)]/50 transition-colors"
              >
                <td className="px-4 py-3">
                  <span className="text-[var(--foreground)] font-medium">
                    {doc.filename ?? `Doc #${doc.id}`}
                  </span>
                </td>
                <td className="px-4 py-3 text-[var(--muted-foreground)]">
                  {doc.vendor_name ?? '—'}
                </td>
                <td className="px-4 py-3 text-[var(--muted-foreground)]">
                  {doc.document_type ?? '—'}
                </td>
                <td className="px-4 py-3">
                  <span className={statusColor(doc.status)}>
                    {doc.status ?? 'unknown'}
                  </span>
                </td>
                <td className="px-4 py-3 text-[var(--muted-foreground)] tabular-nums">
                  {doc.created_at
                    ? new Date(doc.created_at).toLocaleDateString()
                    : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {docs.length === 0 && (
          <div className="py-12">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center space-y-3">
                <div className="w-8 h-8 border-2 border-[var(--primary)]/30 border-t-[var(--primary)] rounded-full animate-spin" />
                <span className="text-sm text-[var(--muted-foreground)] font-medium">Fetching documents...</span>
              </div>
            ) : (
              <EmptyState
                icon={FileText}
                title={search ? "No matching documents" : "No documents found"}
                description={search ? `No documents found matching "${search}"` : "You haven't uploaded any documents yet."}
              />
            )}
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-[var(--muted-foreground)]">
            {total} documents
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
