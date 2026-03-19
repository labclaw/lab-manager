import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { documents as docApi } from '@/lib/api'

interface ReviewPageProps {
  readonly onError: (msg: string) => void
}

function confBadgeStyle(confidence?: number): {
  bg: string
  text: string
  border: string
} {
  const c = confidence ?? 0
  if (c >= 0.8)
    return {
      bg: 'rgba(16,185,129,0.15)',
      text: '#34d399',
      border: 'rgba(16,185,129,0.3)',
    }
  if (c >= 0.6)
    return {
      bg: 'rgba(245,158,11,0.15)',
      text: '#f59e0b',
      border: 'rgba(245,158,11,0.3)',
    }
  return {
    bg: 'rgba(239,68,68,0.15)',
    text: '#ef4444',
    border: 'rgba(239,68,68,0.3)',
  }
}

function confLabel(confidence?: number): string {
  if (confidence == null) return '--'
  return `${Math.round(confidence * 100)}% Conf.`
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: '2-digit',
    year: 'numeric',
  })
}

export function ReviewPage({ onError }: ReviewPageProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [rejecting, setRejecting] = useState(false)
  const [rejectReason, setRejectReason] = useState('')

  // Fetch review queue
  const {
    data: queueRes,
    isLoading,
  } = useQuery({
    queryKey: ['reviewQueue'],
    queryFn: () => docApi.reviewQueue(),
  })

  const queue = useMemo(() => {
    const items = queueRes?.items ?? []
    return [...items].sort((a, b) => (a.confidence ?? 1) - (b.confidence ?? 1))
  }, [queueRes])

  // Auto-select first item
  const selected = useMemo(() => {
    if (queue.length === 0) return null
    if (selectedId != null) {
      const found = queue.find((d) => d.id === selectedId)
      if (found) return found
    }
    return queue[0]
  }, [queue, selectedId])

  // Fetch detail for selected doc
  const { data: detail } = useQuery({
    queryKey: ['document', selected?.id],
    queryFn: () => docApi.get(selected!.id),
    enabled: selected != null,
  })

  // Mutations
  const approveMutation = useMutation({
    mutationFn: (id: number) => docApi.approve(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reviewQueue'] })
      setSelectedId(null)
    },
    onError: (err: Error) => onError(err.message),
  })

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      docApi.reject(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reviewQueue'] })
      setSelectedId(null)
      setRejecting(false)
      setRejectReason('')
    },
    onError: (err: Error) => onError(err.message),
  })

  const actionLoading = approveMutation.isPending || rejectMutation.isPending

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 space-y-3">
        <div className="w-8 h-8 border-2 border-[var(--primary)]/30 border-t-[var(--primary)] rounded-full animate-spin" />
        <span className="text-sm text-[var(--muted-foreground)] font-medium">
          Checking queue...
        </span>
      </div>
    )
  }

  if (queue.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 space-y-4">
        <div className="w-12 h-12 rounded-2xl bg-[var(--muted)] flex items-center justify-center">
          <span className="material-symbols-outlined text-2xl text-[var(--muted-foreground)]">
            check_circle
          </span>
        </div>
        <h3 className="text-base font-semibold text-[var(--foreground)]">
          No documents waiting for review
        </h3>
        <p className="text-sm text-[var(--muted-foreground)]">
          Upload a packing list or invoice to begin.
        </p>
        <button
          onClick={() => navigate('/upload')}
          className="flex items-center gap-2 bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium"
        >
          <span className="material-symbols-outlined text-lg">upload_file</span>
          Upload Document
        </button>
      </div>
    )
  }

  const doc = selected ?? queue[0]
  const docDetail = detail ?? doc

  return (
    <div className="-m-6 flex flex-col h-[calc(100vh-4rem)]">
      {/* Top Bar */}
      <div className="h-16 border-b border-[var(--border)] flex items-center justify-between px-6 shrink-0">
        <div>
          <h2 className="text-xl font-bold text-[var(--foreground)] leading-tight">
            Review Queue
          </h2>
          <p className="text-xs text-[var(--muted-foreground)] font-medium">
            {queue.length} document{queue.length !== 1 ? 's' : ''} awaiting verification
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="relative">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] text-lg">
              search
            </span>
            <input
              type="text"
              placeholder="Search filename..."
              className="bg-[var(--card)] border border-[var(--border)] text-sm rounded-lg pl-10 pr-4 py-1.5 w-64 text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
            />
          </div>
        </div>
      </div>

      {/* Split Pane */}
      <div className="flex-1 flex overflow-hidden min-h-0">
        {/* Document List (40%) */}
        <section className="w-[40%] border-r border-[var(--border)] flex flex-col bg-[var(--card)]/30">
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {queue.map((item) => {
              const isSelected = item.id === doc.id
              const badgeStyle = confBadgeStyle(item.confidence)
              return (
                <div
                  key={item.id}
                  onClick={() => {
                    setSelectedId(item.id)
                    setRejecting(false)
                    setRejectReason('')
                  }}
                  className={`p-4 rounded-xl cursor-pointer transition-all ${
                    isSelected
                      ? 'border-2 border-[var(--primary)] bg-[var(--primary)]/5'
                      : 'border border-[var(--border)] bg-[var(--card)]/50 hover:bg-[var(--card)]'
                  }`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <h3
                      className={`text-sm font-bold truncate w-4/5 ${
                        isSelected
                          ? 'text-[var(--foreground)]'
                          : 'text-[var(--foreground)]/80'
                      }`}
                    >
                      {item.filename ?? `Doc #${item.id}`}
                    </h3>
                    <span
                      className="text-xs font-bold px-2 py-1 rounded whitespace-nowrap"
                      style={{
                        backgroundColor: badgeStyle.bg,
                        color: badgeStyle.text,
                        border: `1px solid ${badgeStyle.border}`,
                      }}
                    >
                      {confLabel(item.confidence)}
                    </span>
                  </div>
                  <div className="flex justify-between items-end">
                    <div className="space-y-0.5">
                      <p className="text-xs text-[var(--muted-foreground)] font-medium">
                        {item.vendor_name ?? 'Unknown vendor'}
                      </p>
                      <p className="text-[10px] text-[var(--muted-foreground)] italic">
                        Extracted: {formatDate(item.created_at)}
                      </p>
                    </div>
                    {isSelected && (
                      <span className="material-symbols-outlined text-[var(--primary)] text-xl">
                        arrow_forward_ios
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </section>

        {/* Detail Panel (60%) */}
        <section className="flex-1 flex flex-col overflow-hidden relative">
          {/* Document Preview Area */}
          <div className="h-[35%] min-h-[250px] p-6 bg-black/80 flex flex-col border-b border-[var(--border)]/50">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest">
                  Document Preview
                </span>
                <div className="h-4 w-px bg-[var(--border)]" />
                {docDetail.confidence != null && (
                  <span
                    className="text-xs flex items-center gap-1 font-semibold"
                    style={{
                      color: confBadgeStyle(docDetail.confidence).text,
                    }}
                  >
                    <span className="material-symbols-outlined text-xs">verified</span>
                    {docDetail.confidence >= 0.8
                      ? 'High'
                      : docDetail.confidence >= 0.6
                        ? 'Medium'
                        : 'Low'}{' '}
                    extraction confidence (
                    {Math.round((docDetail.confidence ?? 0) * 100)}%)
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                <button className="p-1.5 rounded bg-[var(--card)] hover:bg-[var(--muted)] text-[var(--muted-foreground)]">
                  <span className="material-symbols-outlined text-sm">zoom_in</span>
                </button>
                <button className="p-1.5 rounded bg-[var(--card)] hover:bg-[var(--muted)] text-[var(--muted-foreground)]">
                  <span className="material-symbols-outlined text-sm">zoom_out</span>
                </button>
                <button className="p-1.5 rounded bg-[var(--card)] hover:bg-[var(--muted)] text-[var(--muted-foreground)]">
                  <span className="material-symbols-outlined text-sm">
                    open_in_new
                  </span>
                </button>
              </div>
            </div>
            <div className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--card)]/20 flex items-center justify-center overflow-hidden">
              <div className="text-center">
                <div className="mb-4 bg-[var(--primary)]/20 p-8 inline-block rounded-full">
                  <span className="material-symbols-outlined text-[var(--primary)] text-5xl">
                    picture_as_pdf
                  </span>
                </div>
                <p className="text-sm text-[var(--foreground)]/80 font-medium">
                  {docDetail.filename ?? `Document #${docDetail.id}`}
                </p>
                <p className="text-[10px] text-[var(--muted-foreground)]">
                  Page 1 of 1
                </p>
              </div>
            </div>
          </div>

          {/* Extraction Details */}
          <div className="flex-1 overflow-y-auto pb-24">
            <div className="p-6">
              {/* Extracted Data Grid */}
              <div className="mb-8">
                <h4 className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-4 flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm">grid_view</span>
                  Extracted Header Data
                </h4>
                <div className="grid grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-5">
                  <div className="space-y-1.5">
                    <label className="block text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-wide">
                      Vendor
                    </label>
                    <div className="relative">
                      <input
                        type="text"
                        readOnly
                        value={docDetail.vendor_name ?? ''}
                        className="w-full bg-[var(--card)] border border-[var(--border)] rounded-lg py-2.5 pl-3 pr-10 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
                      />
                      <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-[var(--accent)] text-lg">
                        check_circle
                      </span>
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-wide">
                      PO Number
                    </label>
                    <div className="relative">
                      <input
                        type="text"
                        readOnly
                        value="--"
                        className="w-full bg-[var(--card)] border border-[var(--border)] rounded-lg py-2.5 pl-3 pr-10 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
                      />
                      <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-[var(--warning)] text-lg">
                        warning
                      </span>
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-wide">
                      Document Type
                    </label>
                    <select
                      disabled
                      value={docDetail.document_type ?? ''}
                      className="w-full bg-[var(--card)] border border-[var(--border)] rounded-lg py-2.5 px-3 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
                    >
                      <option value="packing_list">Packing List</option>
                      <option value="invoice">Invoice</option>
                      <option value="shipping_label">Shipping Label</option>
                      <option value="certificate_of_analysis">
                        Certificate of Analysis
                      </option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-wide">
                      Created Date
                    </label>
                    <input
                      type="text"
                      readOnly
                      value={formatDate(docDetail.created_at)}
                      className="w-full bg-[var(--card)] border border-[var(--border)] rounded-lg py-2.5 px-3 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-wide">
                      Status
                    </label>
                    <input
                      type="text"
                      readOnly
                      value={docDetail.status ?? 'needs_review'}
                      className="w-full bg-[var(--card)] border border-[var(--border)] rounded-lg py-2.5 px-3 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-wide">
                      Confidence
                    </label>
                    <input
                      type="text"
                      readOnly
                      value={
                        docDetail.confidence != null
                          ? `${Math.round(docDetail.confidence * 100)}%`
                          : '--'
                      }
                      className="w-full bg-[var(--card)] border border-[var(--border)] rounded-lg py-2.5 px-3 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
                    />
                  </div>
                </div>
              </div>

              {/* Line Items Table */}
              <div>
                <h4 className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-4 flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm">list_alt</span>
                  Extracted Line Items
                </h4>
                <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]/30">
                  <table className="w-full text-left text-sm border-collapse">
                    <thead>
                      <tr className="bg-[var(--muted)]/30 text-[var(--muted-foreground)] font-bold border-b border-[var(--border)]">
                        <th className="px-4 py-3 text-[10px] uppercase tracking-wider">
                          Catalog #
                        </th>
                        <th className="px-4 py-3 text-[10px] uppercase tracking-wider">
                          Description
                        </th>
                        <th className="px-4 py-3 text-[10px] uppercase tracking-wider w-16 text-center">
                          Qty
                        </th>
                        <th className="px-4 py-3 text-[10px] uppercase tracking-wider w-20">
                          Unit
                        </th>
                        <th className="px-4 py-3 text-[10px] uppercase tracking-wider">
                          Lot Number
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border)] text-[var(--foreground)]/80">
                      <tr className="hover:bg-[var(--primary)]/5 transition-colors">
                        <td className="px-4 py-3 font-mono text-xs text-[var(--muted-foreground)]" colSpan={5}>
                          <span className="italic">
                            Line item data will appear here after extraction
                          </span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>

          {/* Rejection dialog */}
          {rejecting && (
            <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-20">
              <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-6 w-full max-w-md space-y-4 shadow-2xl">
                <h3 className="text-base font-semibold text-[var(--foreground)]">
                  Reject Document
                </h3>
                <p className="text-sm text-[var(--muted-foreground)]">
                  Provide a reason for rejecting{' '}
                  <span className="font-medium text-[var(--foreground)]">
                    {doc.filename}
                  </span>
                </p>
                <textarea
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Describe the issue..."
                  className="w-full h-24 bg-[var(--background)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)] resize-none"
                />
                <div className="flex items-center gap-3 justify-end">
                  <button
                    onClick={() => {
                      setRejecting(false)
                      setRejectReason('')
                    }}
                    className="px-4 py-2 rounded-lg text-sm font-medium text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() =>
                      rejectMutation.mutate({
                        id: doc.id,
                        reason: rejectReason || 'No reason provided',
                      })
                    }
                    disabled={rejectMutation.isPending}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--destructive)] text-white font-medium hover:brightness-110 transition-all text-sm"
                  >
                    {rejectMutation.isPending ? 'Rejecting...' : 'Confirm Rejection'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Footer Action Bar */}
          <footer className="p-4 border-t border-[var(--border)] bg-[var(--background)]/95 backdrop-blur-md absolute bottom-0 left-0 right-0 z-10 shadow-2xl">
            <div className="flex items-center justify-between">
              <div className="flex gap-4">
                <button
                  onClick={() => approveMutation.mutate(doc.id)}
                  disabled={actionLoading}
                  className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg text-sm transition-all shadow-lg flex items-center gap-2 ring-1 ring-emerald-500/50 disabled:opacity-50"
                >
                  <span className="material-symbols-outlined text-lg">
                    check_circle
                  </span>
                  {approveMutation.isPending ? 'Approving...' : 'Approve'}
                </button>
                <button
                  disabled={actionLoading}
                  className="px-6 py-2.5 bg-[var(--card)] border border-[var(--primary)]/40 hover:border-[var(--primary)] text-[var(--foreground)] font-bold rounded-lg text-sm transition-all flex items-center gap-2 hover:bg-[var(--primary)]/5 disabled:opacity-50"
                >
                  <span className="material-symbols-outlined text-lg text-[var(--primary)]">
                    edit_document
                  </span>
                  Edit & Approve
                </button>
              </div>
              <button
                onClick={() => setRejecting(true)}
                disabled={actionLoading}
                className="px-6 py-2.5 border-2 border-[var(--destructive)]/30 text-[var(--destructive)] hover:text-white hover:bg-[var(--destructive)]/80 hover:border-[var(--destructive)] font-bold rounded-lg text-sm transition-all flex items-center gap-2 disabled:opacity-50"
              >
                <span className="material-symbols-outlined text-lg">block</span>
                Reject
              </button>
            </div>
          </footer>
        </section>
      </div>
    </div>
  )
}
