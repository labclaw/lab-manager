import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { documents as docApi } from '@/lib/api'

interface DocumentsPageProps {
  readonly onError: (msg: string) => void
}

const STATUS_FILTERS = [
  { key: 'all', label: 'All', dotClass: null },
  { key: 'approved', label: 'Approved', dotClass: 'bg-success' },
  { key: 'needs_review', label: 'Needs Review', dotClass: 'bg-warning' },
  { key: 'rejected', label: 'Rejected', dotClass: 'bg-danger' },
] as const

function statusBadgeClasses(status?: string): { wrapperClass: string; label: string } {
  switch (status) {
    case 'approved':
      return {
        wrapperClass:
          'px-2.5 py-1 rounded-full text-[11px] font-bold bg-success/10 text-success border border-success/20 uppercase tracking-wide',
        label: 'Approved',
      }
    case 'needs_review':
      return {
        wrapperClass:
          'px-2.5 py-1 rounded-full text-[11px] font-bold bg-warning/10 text-warning border border-warning/20 uppercase tracking-wide whitespace-nowrap',
        label: 'Needs Review',
      }
    case 'rejected':
      return {
        wrapperClass:
          'px-2.5 py-1 rounded-full text-[11px] font-bold bg-danger/10 text-danger border border-danger/20 uppercase tracking-wide',
        label: 'Rejected',
      }
    default:
      return {
        wrapperClass:
          'px-2.5 py-1 rounded-full text-[11px] font-bold bg-slate-500/10 text-slate-500 border border-slate-500/20 uppercase tracking-wide',
        label: status ?? 'Unknown',
      }
  }
}

function confidenceBarColor(c: number): string {
  if (c >= 0.8) return 'bg-success'
  if (c >= 0.6) return 'bg-warning'
  return 'bg-danger'
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

  const {
    data: res,
    isLoading,
    error,
  } = useQuery({
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
      <header className="h-16 border-b border-slate-200 dark:border-slate-800 px-8 flex items-center justify-between sticky top-0 bg-background-light/80 dark:bg-background-dark/80 backdrop-blur-md z-10 shrink-0">
        <h2 className="text-xl font-bold">Documents</h2>
        <div className="flex items-center gap-4 flex-1 max-w-2xl px-8">
          <div className="relative w-full">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
              search
            </span>
            <input
              type="text"
              placeholder="Search vendor or filename..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-slate-100 dark:bg-card-dark border-none rounded-lg pl-10 pr-4 py-2 text-sm focus:ring-2 focus:ring-primary transition-all"
            />
          </div>
        </div>
        <button
          onClick={() => navigate('/upload')}
          className="flex items-center gap-2 bg-success hover:bg-success/90 text-white px-4 py-2 rounded-lg text-sm font-bold transition-colors"
        >
          <span className="material-symbols-outlined">upload_file</span>
          Upload Doc
        </button>
      </header>

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
              className={
                isActive
                  ? 'px-4 py-1.5 rounded-full text-sm font-medium bg-primary text-white shadow-lg shadow-primary/20'
                  : 'px-4 py-1.5 rounded-full text-sm font-medium bg-slate-100 dark:bg-card-dark text-slate-600 dark:text-slate-300 flex items-center gap-2 hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors border border-transparent'
              }
            >
              {f.dotClass && !isActive && (
                <span className={`w-2 h-2 rounded-full ${f.dotClass}`} />
              )}
              {f.label}
            </button>
          )
        })}
      </div>

      {/* Table Container */}
      <div className="px-8 pb-8 flex-1 min-h-0 flex flex-col">
        <div className="bg-white dark:bg-card-dark rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm flex-1 min-h-0">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-64 space-y-3">
              <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
              <span className="text-sm text-slate-500 font-medium">
                Fetching documents...
              </span>
            </div>
          ) : filteredDocs.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 space-y-3">
              <span className="material-symbols-outlined text-4xl text-slate-500">
                description
              </span>
              <p className="text-sm text-slate-500">
                {search ? `No documents matching "${search}"` : 'No documents found'}
              </p>
              {!search && (
                <button
                  onClick={() => navigate('/upload')}
                  className="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium mt-2"
                >
                  <span className="material-symbols-outlined text-lg">upload_file</span>
                  Upload Document
                </button>
              )}
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-800">
                  <th className="px-4 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Filename
                  </th>
                  <th className="px-4 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Vendor
                  </th>
                  <th className="px-4 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-4 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-4 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Confidence
                  </th>
                  <th className="px-4 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider text-right">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredDocs.map((doc, idx) => {
                  const badge = statusBadgeClasses(doc.status)
                  const conf = doc.confidence ?? 0
                  const confPct = Math.round(conf * 100)
                  return (
                    <tr
                      key={doc.id}
                      className={`hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors cursor-pointer group ${
                        idx % 2 === 1 ? 'bg-slate-50/30 dark:bg-white/[0.01]' : ''
                      }`}
                      onClick={() => navigate(`/review?id=${doc.id}`)}
                    >
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-3">
                          <span className="material-symbols-outlined text-slate-400 group-hover:text-primary transition-colors">
                            picture_as_pdf
                          </span>
                          <span className="text-sm font-medium">
                            {doc.filename ?? `Doc #${doc.id}`}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-4 text-sm text-slate-600 dark:text-slate-400">
                        {doc.vendor_name ?? '--'}
                      </td>
                      <td className="px-4 py-4 text-xs font-mono text-slate-500">
                        {doc.document_type ?? '--'}
                      </td>
                      <td className="px-4 py-4">
                        <span className={badge.wrapperClass}>{badge.label}</span>
                      </td>
                      <td className="px-4 py-4">
                        {doc.confidence != null ? (
                          <div className="flex items-center gap-2">
                            <div className="w-12 bg-slate-200 dark:bg-slate-700 h-1.5 rounded-full overflow-hidden">
                              <div
                                className={`${confidenceBarColor(conf)} h-full`}
                                style={{ width: `${confPct}%` }}
                              />
                            </div>
                            <span className="text-xs font-medium text-slate-500">
                              {conf.toFixed(2)}
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-500">--</span>
                        )}
                      </td>
                      <td className="px-4 py-4 text-sm text-slate-500 text-right">
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
            <p className="text-sm text-slate-500">
              Showing{' '}
              <span className="font-semibold text-slate-900 dark:text-slate-200">
                {startItem}
              </span>{' '}
              to{' '}
              <span className="font-semibold text-slate-900 dark:text-slate-200">
                {endItem}
              </span>{' '}
              of{' '}
              <span className="font-semibold text-slate-900 dark:text-slate-200">
                {total}
              </span>{' '}
              documents
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="flex items-center justify-center w-10 h-10 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-card-dark text-slate-400 hover:text-primary hover:border-primary/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Previous page"
              >
                <span className="material-symbols-outlined">chevron_left</span>
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="flex items-center justify-center w-10 h-10 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-card-dark text-slate-400 hover:text-primary hover:border-primary/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
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
