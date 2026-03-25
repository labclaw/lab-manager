import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { documents as docApi } from '@/lib/api'
import { Search, Upload, FileText, ChevronLeft, ChevronRight } from 'lucide-react'
import { formatEnum } from '@/lib/utils'

interface DocumentsPageProps {
  readonly onError: (msg: string) => void
}

const STATUS_FILTERS = [
  { key: 'all', label: 'All', dotClass: null },
  { key: 'approved', label: 'Approved', dotClass: 'bg-emerald-500' },
  { key: 'needs_review', label: 'Needs Review', dotClass: 'bg-amber-500' },
  { key: 'rejected', label: 'Rejected', dotClass: 'bg-red-500' },
] as const

function statusBadgeClasses(status?: string): { wrapperClass: string; label: string } {
  switch (status) {
    case 'approved':
      return {
        wrapperClass:
          'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 whitespace-nowrap',
        label: 'Approved',
      }
    case 'needs_review':
      return {
        wrapperClass:
          'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200 whitespace-nowrap',
        label: 'Needs Review',
      }
    case 'rejected':
      return {
        wrapperClass:
          'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200 whitespace-nowrap',
        label: 'Rejected',
      }
    default:
      return {
        wrapperClass:
          'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-slate-50 text-slate-600 border border-slate-200 whitespace-nowrap',
        label: status ? formatEnum(status) : 'Unknown',
      }
  }
}

function confidenceBarColor(c: number): string {
  if (c >= 0.8) return 'bg-emerald-500'
  if (c >= 0.6) return 'bg-amber-500'
  return 'bg-red-500'
}

function formatShortDate(dateStr?: string): string {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function DocumentsPage({ onError }: DocumentsPageProps) {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const vendorFilter = searchParams.get('vendor') ?? undefined
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const pageSize = 20

  const {
    data: res,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['documents', page, statusFilter, vendorFilter],
    queryFn: () =>
      docApi.list(page, pageSize, statusFilter !== 'all' ? statusFilter : undefined, vendorFilter),
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
          (d.file_name ?? '').toLowerCase().includes(search.toLowerCase()) ||
          (d.vendor_name ?? '').toLowerCase().includes(search.toLowerCase()),
      )
    : docs

  const startItem = (page - 1) * pageSize + 1
  const endItem = Math.min(page * pageSize, total)

  return (
    <div className="space-y-0 -m-6 flex flex-col h-[calc(100vh-4rem)]">
      {/* Top Bar */}
      <header className="h-16 border-b border-slate-200 dark:border-slate-800 px-8 flex items-center justify-between sticky top-0 bg-white/80 dark:bg-background-dark/80 backdrop-blur-md z-10 shrink-0">
        <h2 className="text-xl font-bold">Documents</h2>
        <div className="flex items-center gap-4 flex-1 max-w-2xl px-8">
          <div className="relative w-full">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search vendor or filename..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-slate-50 dark:bg-card-dark border border-slate-200 dark:border-slate-700 rounded-lg pl-10 pr-4 py-2 text-sm focus:ring-2 focus:ring-primary focus:border-primary transition-all"
            />
          </div>
        </div>
        <button
          onClick={() => navigate('/upload')}
          className="flex items-center gap-2 bg-primary hover:bg-primary/90 text-white px-4 py-2 rounded-lg text-sm font-bold transition-colors"
        >
          <Upload />
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
        {vendorFilter && (
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium bg-blue-50 text-blue-700 border border-blue-200">
            Vendor: {vendorFilter}
            <button
              onClick={() => {
                searchParams.delete('vendor')
                setSearchParams(searchParams)
                setPage(1)
              }}
              className="ml-1 text-blue-400 hover:text-blue-700"
              aria-label="Clear vendor filter"
            >
              &times;
            </button>
          </span>
        )}
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
              <FileText className="size-10 text-slate-500" />
              <p className="text-sm text-slate-500">
                {search ? `No documents matching "${search}"` : 'No documents found'}
              </p>
              {!search && (
                <button
                  onClick={() => navigate('/upload')}
                  className="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium mt-2"
                >
                  <Upload className="size-5" />
                  Upload Document
                </button>
              )}
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-800">
                  <th className="px-5 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Document
                  </th>
                  <th className="px-5 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Vendor
                  </th>
                  <th className="px-5 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-5 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-5 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Confidence
                  </th>
                  <th className="px-5 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider text-right">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredDocs.map((doc, idx) => {
                  const badge = statusBadgeClasses(doc.status)
                  const conf = doc.extraction_confidence ?? 0
                  const confPct = Math.round(conf * 100)
                  return (
                    <tr
                      key={doc.id}
                      className={`hover:bg-primary/[0.03] dark:hover:bg-slate-800/30 transition-colors duration-150 cursor-pointer group ${
                        idx % 2 === 1 ? 'bg-slate-50/40 dark:bg-white/[0.01]' : 'bg-white'
                      }`}
                      onClick={() => navigate(`/review?id=${doc.id}`)}
                    >
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <div className="size-9 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-center group-hover:bg-primary/5 group-hover:border-primary/20 transition-colors shrink-0">
                            <FileText className="size-4 text-slate-400 group-hover:text-primary transition-colors" />
                          </div>
                          <div className="min-w-0">
                            <span
                              className="text-sm font-medium text-slate-900 block truncate max-w-[240px]"
                              title={doc.vendor_name ?? doc.file_name ?? `Doc #${doc.id}`}
                            >
                              {doc.vendor_name ?? 'Unknown'}
                            </span>
                            <span className="text-[11px] text-slate-400 block truncate max-w-[240px]" title={doc.file_name ?? ''}>
                              {doc.file_name ?? `Doc #${doc.id}`}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
                        {doc.vendor_name ?? 'Unknown'}
                      </td>
                      <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-400 max-w-[140px] whitespace-nowrap overflow-hidden text-ellipsis">
                        {doc.document_type ? formatEnum(doc.document_type) : '--'}
                      </td>
                      <td className="px-5 py-4">
                        <span className={badge.wrapperClass}>{badge.label}</span>
                      </td>
                      <td className="px-5 py-4">
                        {doc.extraction_confidence != null ? (
                          <div className="flex items-center gap-3">
                            <div className="w-20 bg-slate-100 dark:bg-slate-700 h-2 rounded-full overflow-hidden">
                              <div
                                className={`${confidenceBarColor(conf)} h-full rounded-full transition-all`}
                                style={{ width: `${confPct}%` }}
                              />
                            </div>
                            <span className="text-xs font-semibold text-slate-600 tabular-nums">
                              {confPct}%
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">--</span>
                        )}
                      </td>
                      <td className="px-5 py-4 text-sm text-slate-500 text-right">
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
                <ChevronLeft />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="flex items-center justify-center w-10 h-10 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-card-dark text-slate-400 hover:text-primary hover:border-primary/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Next page"
              >
                <ChevronRight />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
