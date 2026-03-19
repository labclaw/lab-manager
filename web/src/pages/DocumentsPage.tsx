import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { documents as docApi } from '@/lib/api'

interface DocumentsPageProps {
  readonly onError: (msg: string) => void
}

const STATUS_FILTERS = [
  { key: 'all', label: 'All', dot: null },
  { key: 'approved', label: 'Approved', dot: 'var(--accent)' },
  { key: 'needs_review', label: 'Needs Review', dot: 'var(--warning)' },
  { key: 'rejected', label: 'Rejected', dot: 'var(--destructive)' },
] as const

function statusBadge(status?: string) {
  switch (status) {
    case 'approved':
      return {
        bg: 'rgba(16,185,129,0.1)',
        text: 'var(--accent)',
        border: 'rgba(16,185,129,0.2)',
        label: 'Approved',
      }
    case 'needs_review':
      return {
        bg: 'rgba(245,158,11,0.1)',
        text: 'var(--warning)',
        border: 'rgba(245,158,11,0.2)',
        label: 'Needs Review',
      }
    case 'rejected':
      return {
        bg: 'rgba(239,68,68,0.1)',
        text: 'var(--destructive)',
        border: 'rgba(239,68,68,0.2)',
        label: 'Rejected',
      }
    default:
      return {
        bg: 'rgba(100,116,139,0.1)',
        text: 'var(--muted-foreground)',
        border: 'rgba(100,116,139,0.2)',
        label: status ?? 'Unknown',
      }
  }
}

function confidenceColor(c: number): string {
  if (c >= 0.8) return 'var(--accent)'
  if (c >= 0.6) return 'var(--warning)'
  return 'var(--destructive)'
}

function formatShortDate(dateStr?: string): string {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function DocumentsPage({ onError }: DocumentsPageProps) {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const pageSize = 20

  const { data: res, isLoading, error } = useQuery({
    queryKey: ['documents', page, statusFilter],
    queryFn: () =>
      docApi.list(page, pageSize, statusFilter !== 'all' ? statusFilter : undefined),
  })

  useEffect(() => {
    if (error) {
      onError(error instanceof Error ? error.message : 'Failed to load documents')
    }
  }, [error, onError])

  const docs = res?.items ?? []
  const total = res?.total ?? 0
  const totalPages = res?.pages ?? Math.ceil(total / pageSize)

  const filteredDocs = search
    ? docs.filter(
        (d) =>
          (d.filename ?? '').toLowerCase().includes(search.toLowerCase()) ||
          (d.vendor_name ?? '').toLowerCase().includes(search.toLowerCase()),
      )
    : docs

  const startItem = (page - 1) * pageSize + 1
  const endItem = Math.min(page * pageSize, total)

  return (
    <div className="space-y-0 -m-6 flex flex-col h-[calc(100vh-4rem)]">
      {/* Top Bar */}
      <div className="px-8 h-16 flex items-center justify-between border-b border-[var(--border)] shrink-0">
        <h2 className="text-xl font-bold text-[var(--foreground)]">Documents</h2>
        <div className="flex items-center gap-4 flex-1 max-w-2xl px-8">
          <div className="relative w-full">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]">
              search
            </span>
            <input
              type="text"
              placeholder="Search vendor or filename..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-[var(--card)] border border-[var(--border)] rounded-lg pl-10 pr-4 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)] transition-all"
            />
          </div>
        </div>
        <button
          onClick={() => navigate('/upload')}
          className="flex items-center gap-2 bg-[var(--accent)] hover:opacity-90 text-white px-4 py-2 rounded-lg text-sm font-bold transition-colors"
        >
          <span className="material-symbols-outlined">upload_file</span>
          Upload Doc
        </button>
      </div>

      {/* Filter Row */}
      <div className="px-8 py-6 flex items-center gap-3 flex-wrap shrink-0">
        {STATUS_FILTERS.map((f) => {
          const isActive = statusFilter === f.key
          return (
            <button
              key={f.key}
              onClick={() => {
                setStatusFilter(f.key)
                setPage(1)
              }}
              className={`px-4 py-1.5 rounded-full text-sm font-medium flex items-center gap-2 transition-colors ${
                isActive
                  ? 'bg-[var(--primary)] text-white shadow-lg'
                  : 'bg-[var(--card)] text-[var(--muted-foreground)] border border-[var(--border)] hover:border-[var(--primary)]/30'
              }`}
            >
              {f.dot && !isActive && (
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: f.dot }}
                />
              )}
              {f.label}
            </button>
          )
        })}
      </div>

      {/* Table Container */}
      <div className="px-8 pb-8 flex-1 min-h-0 flex flex-col">
        <div className="bg-[var(--card)] rounded-xl border border-[var(--border)] overflow-hidden shadow-sm flex-1 min-h-0">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-64 space-y-3">
              <div className="w-8 h-8 border-2 border-[var(--primary)]/30 border-t-[var(--primary)] rounded-full animate-spin" />
              <span className="text-sm text-[var(--muted-foreground)] font-medium">
                Fetching documents...
              </span>
            </div>
          ) : filteredDocs.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 space-y-3">
              <span className="material-symbols-outlined text-4xl text-[var(--muted-foreground)]">
                description
              </span>
              <p className="text-sm text-[var(--muted-foreground)]">
                {search ? `No documents matching "${search}"` : 'No documents found'}
              </p>
              {!search && (
                <button
                  onClick={() => navigate('/upload')}
                  className="flex items-center gap-2 bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium mt-2"
                >
                  <span className="material-symbols-outlined text-lg">upload_file</span>
                  Upload Document
                </button>
              )}
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[var(--muted)]/50 border-b border-[var(--border)]">
                  <th className="px-4 py-4 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
                    Filename
                  </th>
                  <th className="px-4 py-4 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
                    Vendor
                  </th>
                  <th className="px-4 py-4 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-4 py-4 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-4 py-4 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
                    Confidence
                  </th>
                  <th className="px-4 py-4 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider text-right">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {filteredDocs.map((doc) => {
                  const badge = statusBadge(doc.status)
                  const conf = doc.confidence ?? 0
                  const confPct = Math.round(conf * 100)
                  return (
                    <tr
                      key={doc.id}
                      className="hover:bg-[var(--muted)]/30 transition-colors cursor-pointer group"
                      onClick={() => navigate(`/review`)}
                    >
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-3">
                          <span className="material-symbols-outlined text-[var(--muted-foreground)] group-hover:text-[var(--primary)] transition-colors">
                            picture_as_pdf
                          </span>
                          <span className="text-sm font-medium text-[var(--foreground)]">
                            {doc.filename ?? `Doc #${doc.id}`}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-4 text-sm text-[var(--muted-foreground)]">
                        {doc.vendor_name ?? '--'}
                      </td>
                      <td className="px-4 py-4 text-xs font-mono text-[var(--muted-foreground)]">
                        {doc.document_type ?? '--'}
                      </td>
                      <td className="px-4 py-4">
                        <span
                          className="px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wide whitespace-nowrap"
                          style={{
                            backgroundColor: badge.bg,
                            color: badge.text,
                            border: `1px solid ${badge.border}`,
                          }}
                        >
                          {badge.label}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        {doc.confidence != null ? (
                          <div className="flex items-center gap-2">
                            <div className="w-12 bg-[var(--muted)] h-1.5 rounded-full overflow-hidden">
                              <div
                                className="h-full rounded-full"
                                style={{
                                  width: `${confPct}%`,
                                  backgroundColor: confidenceColor(conf),
                                }}
                              />
                            </div>
                            <span className="text-xs font-medium text-[var(--muted-foreground)]">
                              {conf.toFixed(2)}
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs text-[var(--muted-foreground)]">--</span>
                        )}
                      </td>
                      <td className="px-4 py-4 text-sm text-[var(--muted-foreground)] text-right">
                        {formatShortDate(doc.created_at)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {total > 0 && (
          <div className="mt-6 flex items-center justify-between">
            <p className="text-sm text-[var(--muted-foreground)]">
              Showing{' '}
              <span className="font-semibold text-[var(--foreground)]">{startItem}</span> to{' '}
              <span className="font-semibold text-[var(--foreground)]">{endItem}</span> of{' '}
              <span className="font-semibold text-[var(--foreground)]">{total}</span>{' '}
              documents
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="flex items-center justify-center w-10 h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] text-[var(--muted-foreground)] hover:text-[var(--primary)] hover:border-[var(--primary)]/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Previous page"
              >
                <span className="material-symbols-outlined">chevron_left</span>
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="flex items-center justify-center w-10 h-10 rounded-lg border border-[var(--border)] bg-[var(--card)] text-[var(--muted-foreground)] hover:text-[var(--primary)] hover:border-[var(--primary)]/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Next page"
              >
                <span className="material-symbols-outlined">chevron_right</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
