import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { documents as docApi } from '@/lib/api'
import { SkeletonTable } from '@/components/ui/SkeletonTable'
import {
  CheckCircle,
  CircleCheck,
  Filter,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  ExternalLink,
  FileText,
  LayoutGrid,
  List,
  History,
  CirclePlus,
  Ban,
  AlertTriangle,
  Upload,
  Pencil,
} from 'lucide-react'

interface ReviewPageProps {
  readonly onError: (msg: string) => void
}

function confBadgeClasses(confidence?: number): {
  wrapperClass: string
} {
  const c = confidence ?? 0
  if (c >= 0.8)
    return {
      wrapperClass:
        'bg-emerald-500/20 text-emerald-400 text-xs font-bold px-2 py-1 rounded border border-emerald-500/30',
    }
  if (c >= 0.6)
    return {
      wrapperClass:
        'bg-amber-500/20 text-amber-500 text-xs font-bold px-2 py-1 rounded border border-amber-500/30',
    }
  return {
    wrapperClass:
      'bg-red-500/20 text-red-500 text-xs font-bold px-2 py-1 rounded border border-red-500/30',
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
  const { data: queueRes, isLoading } = useQuery({
    queryKey: ['reviewQueue'],
    queryFn: () => docApi.reviewQueue(),
  })

  const queue = useMemo(() => {
    const items = queueRes?.items ?? []
    return [...items].sort((a, b) => (a.extraction_confidence ?? 1) - (b.extraction_confidence ?? 1))
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
    mutationFn: (id: number) => docApi.review(id, { action: 'approve', reviewed_by: 'admin' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reviewQueue'] })
      setSelectedId(null)
    },
    onError: (err: Error) => onError(err.message),
  })

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      docApi.review(id, { action: 'reject', reviewed_by: 'admin', review_notes: reason }),
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
      <div className="p-8">
        <SkeletonTable rows={5} columns={4} />
      </div>
    )
  }

  if (queue.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 space-y-4">
        <div className="w-12 h-12 rounded-2xl bg-[var(--card)] flex items-center justify-center">
          <CheckCircle className="size-6 text-[var(--muted-foreground)]" />
        </div>
        <h3 className="text-base font-semibold text-[var(--foreground)]">
          No documents waiting for review
        </h3>
        <p className="text-sm text-[var(--muted-foreground)]">
          Upload a packing list or invoice to begin.
        </p>
        <button
          onClick={() => navigate('/upload')}
          className="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium"
        >
          <Upload className="size-5" />
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
      <header className="h-16 border-b border-[var(--border)] flex items-center justify-between px-6 bg-[var(--background)] shrink-0">
        <div>
          <h2 className="text-xl font-bold text-[var(--foreground)] leading-tight">Review Queue</h2>
          <p className="text-xs text-[var(--muted-foreground)] font-medium">
            {queue.length} document{queue.length !== 1 ? 's' : ''} awaiting verification
          </p>
        </div>
        <div className="flex items-center gap-4">
          <button className="p-2 text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
            <Filter />
          </button>
        </div>
      </header>

      {/* Workspace Split */}
      <div className="flex-1 flex overflow-hidden min-h-0">
        {/* Document List (40%) */}
        <section className="w-[40%] border-r border-[var(--border)] flex flex-col bg-[var(--card)]/30">
          <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-3">
            {queue.map((item) => {
              const isSelected = item.id === doc.id
              const badgeInfo = confBadgeClasses(item.extraction_confidence)
              return (
                <div
                  key={item.id}
                  onClick={() => {
                    setSelectedId(item.id)
                    setRejecting(false)
                    setRejectReason('')
                  }}
                  className={
                    isSelected
                      ? 'p-4 rounded-xl border border-[var(--border)] border-l-4 border-l-primary bg-purple-50 dark:bg-purple-900/20 cursor-pointer relative group'
                      : 'p-4 rounded-xl border border-[var(--border)] bg-[var(--card)]/50 hover:bg-[var(--card)] cursor-pointer transition-all'
                  }
                >
                  <div className="flex justify-between items-start mb-2">
                    <h3
                      className={`text-sm font-bold truncate w-4/5 ${
                        isSelected ? 'text-[var(--foreground)]' : 'text-[var(--foreground)]'
                      }`}
                    >
                      {item.file_name ?? `Doc #${item.id}`}
                    </h3>
                    <span className={badgeInfo.wrapperClass}>
                      {confLabel(item.extraction_confidence)}
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
                      <ChevronRight className="size-5 text-primary" />
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </section>

        {/* Detail Panel (60%) */}
        <section className="flex-1 flex flex-col bg-[var(--background)] overflow-hidden relative">
          {/* Document Preview Area */}
          <div className="h-[35%] min-h-[300px] p-6 bg-black flex flex-col border-b border-[var(--border)]/50">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest">
                  Document Preview
                </span>
                <div className="h-4 w-px bg-[var(--border)]" />
                {docDetail.extraction_confidence != null && (
                  <span
                    className={`text-xs flex items-center gap-1 font-semibold ${
                      (docDetail.extraction_confidence ?? 0) >= 0.8
                        ? 'text-emerald-400'
                        : (docDetail.extraction_confidence ?? 0) >= 0.6
                          ? 'text-amber-500'
                          : 'text-red-500'
                    }`}
                  >
                    <CircleCheck className="size-3.5" />
                    {(docDetail.extraction_confidence ?? 0) >= 0.8
                      ? 'High'
                      : (docDetail.extraction_confidence ?? 0) >= 0.6
                        ? 'Medium'
                        : 'Low'}{' '}
                    extraction confidence (
                    {Math.round((docDetail.extraction_confidence ?? 0) * 100)}%)
                  </span>
                )}
                {docDetail.extraction_model && (
                  <>
                    <div className="h-4 w-px bg-[var(--border)]" />
                    <span className="text-[10px] text-[var(--muted-foreground)] font-mono">
                      {docDetail.extraction_model}
                    </span>
                  </>
                )}
              </div>
              <div className="flex gap-2">
                <button className="p-1.5 rounded bg-[var(--card)] hover:bg-[var(--border)] text-[var(--muted-foreground)]">
                  <ZoomIn className="size-4" />
                </button>
                <button className="p-1.5 rounded bg-[var(--card)] hover:bg-[var(--border)] text-[var(--muted-foreground)]">
                  <ZoomOut className="size-4" />
                </button>
                <button className="p-1.5 rounded bg-[var(--card)] hover:bg-[var(--border)] text-[var(--muted-foreground)]">
                  <ExternalLink className="size-4" />
                </button>
              </div>
            </div>
            <div className="flex-1 rounded-lg border border-slate-800 bg-[var(--card)]/20 flex items-center justify-center overflow-hidden relative group">
              {docDetail.file_name && /\.(jpg|jpeg|png|gif|webp|bmp)$/i.test(docDetail.file_name) ? (
                <img
                  src={`/uploads/${docDetail.file_name}`}
                  alt={docDetail.file_name}
                  className="max-w-full max-h-full object-contain"
                />
              ) : (
                <div className="text-center transition-transform group-hover:scale-105 duration-500">
                  <div className="mb-4 bg-primary/20 p-8 inline-block rounded-full relative">
                    <FileText className="text-primary size-12" />
                    <div className="absolute inset-0 bg-gradient-to-tr from-primary/30 to-transparent animate-pulse rounded-full" />
                  </div>
                  <p className="text-sm text-[var(--foreground)] font-medium">
                    {docDetail.file_name ?? `Document #${docDetail.id}`}
                  </p>
                  <p className="text-[10px] text-[var(--muted-foreground)]">Page 1 of 1</p>
                </div>
              )}
              {/* Grid pattern for technical feel */}
              <div
                className="absolute inset-x-0 inset-y-0 opacity-[0.03] pointer-events-none"
                style={{
                  backgroundImage:
                    'linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)',
                  backgroundSize: '32px 32px',
                }}
              />
            </div>
          </div>

          {/* Extraction Details and Activity Split */}
          <div className="flex-1 overflow-y-auto custom-scrollbar flex">
            {/* Data Extraction Fields (Main content) */}
            <div className="flex-1 p-6 pb-28">
              {/* Extracted Data Grid */}
              <div className="mb-8">
                <h4 className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-4 flex items-center gap-2">
                  <LayoutGrid className="size-4" />
                  Extracted Header Data
                </h4>
                <div className="grid grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-5">
                  <div className="space-y-1.5">
                    <label className="block text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-wide">
                      Vendor
                    </label>
                    <div className="relative group">
                      <input
                        className="w-full bg-[var(--card)] border-[var(--border)] rounded-lg py-2.5 pl-3 pr-10 text-sm focus:ring-primary focus:border-primary transition-all hover:bg-[var(--card)]/80"
                        type="text"
                        readOnly
                        value={docDetail.vendor_name ?? ''}
                      />
                      <CheckCircle className="absolute right-3 top-1/2 -translate-y-1/2 text-emerald-500 size-5" />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-wide">
                      PO Number
                    </label>
                    <div className="relative">
                      <input
                        className="w-full bg-[var(--card)] border-[var(--border)] rounded-lg py-2.5 pl-3 pr-10 text-sm focus:ring-primary focus:border-primary transition-all hover:bg-[var(--card)]/80"
                        type="text"
                        readOnly
                        value={docDetail.extracted_data?.po_number ?? ''}
                        placeholder="No PO number extracted"
                      />
                      {docDetail.extracted_data?.po_number ? (
                        <CheckCircle className={`absolute right-3 top-1/2 -translate-y-1/2 size-5 text-emerald-500`} />
                      ) : (
                        <AlertTriangle className="absolute right-3 top-1/2 -translate-y-1/2 size-5 text-amber-500" />
                      )}
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-wide">
                      Document Type
                    </label>
                    <select
                      disabled
                      value={docDetail.document_type ?? ''}
                      className="w-full bg-[var(--card)] border-[var(--border)] rounded-lg py-2.5 px-3 text-sm focus:ring-primary focus:border-primary transition-all hover:bg-[var(--card)]/80"
                    >
                      <option value="packing_list">Packing List</option>
                      <option value="invoice">Invoice</option>
                      <option value="shipping_label">Tracking Slips</option>
                      <option value="certificate_of_analysis">
                        Certificate of Analysis
                      </option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-wide">
                      Ship Date
                    </label>
                    <input
                      className="w-full bg-[var(--card)] border-[var(--border)] rounded-lg py-2.5 px-3 text-sm focus:ring-primary focus:border-primary transition-all hover:bg-[var(--card)]/80"
                      type="date"
                      readOnly
                      value={docDetail.extracted_data?.ship_date?.split('T')[0] ?? ''}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-wide">
                      Received Date
                    </label>
                    <input
                      className="w-full bg-[var(--card)] border-[var(--border)] rounded-lg py-2.5 px-3 text-sm focus:ring-primary focus:border-primary transition-all hover:bg-[var(--card)]/80"
                      type="date"
                      readOnly
                      value={docDetail.extracted_data?.received_date?.split('T')[0] ?? docDetail.created_at?.split('T')[0] ?? ''}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-wide">
                      Received By
                    </label>
                    <div className="relative">
                      <input
                        className="w-full bg-[var(--card)] border-[var(--border)] rounded-lg py-2.5 pl-3 pr-10 text-sm focus:ring-primary focus:border-primary transition-all hover:bg-[var(--card)]/80"
                        placeholder="Not extracted"
                        type="text"
                        readOnly
                        value={docDetail.extracted_data?.received_by ?? ''}
                      />
                      {docDetail.extracted_data?.received_by ? (
                        <CheckCircle className={`absolute right-3 top-1/2 -translate-y-1/2 size-5 text-emerald-500`} />
                      ) : (
                        <Pencil className="absolute right-3 top-1/2 -translate-y-1/2 size-5 text-[var(--muted-foreground)]" />
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Line Items Table */}
              <div>
                <h4 className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-4 flex items-center gap-2">
                  <List className="size-4" />
                  Extracted Line Items
                </h4>
                <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]/30">
                  <table className="w-full text-left text-sm border-collapse">
                    <thead>
                      <tr className="bg-[var(--card)]/60 text-[var(--muted-foreground)] font-bold border-b border-[var(--border)]">
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
                        <th className="px-4 py-3 text-[10px] uppercase tracking-wider w-20 text-right">
                          Unit Price
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-dark text-[var(--foreground)]">
                      {docDetail.extracted_data?.items && docDetail.extracted_data.items.length > 0 ? (
                        docDetail.extracted_data.items.map((item, idx) => (
                          <tr key={idx} className="hover:bg-primary/5 transition-colors">
                            <td className="px-4 py-3 font-mono text-xs text-[var(--foreground)]">
                              {item.catalog_number ?? '--'}
                            </td>
                            <td className="px-4 py-3 text-xs text-[var(--foreground)]">
                              {item.description ?? '--'}
                            </td>
                            <td className="px-4 py-3 text-xs text-center">
                              {item.quantity ?? '--'}
                            </td>
                            <td className="px-4 py-3 text-xs">
                              {item.unit ?? '--'}
                            </td>
                            <td className="px-4 py-3 font-mono text-xs text-[var(--foreground)]">
                              {item.lot_number ?? '--'}
                            </td>
                            <td className="px-4 py-3 text-xs text-right">
                              {item.unit_price != null ? `$${item.unit_price.toFixed(2)}` : '--'}
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr className="hover:bg-primary/5 transition-colors">
                          <td className="px-4 py-3 font-mono text-xs text-[var(--foreground)]" colSpan={6}>
                            <span className="italic">No line items extracted</span>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
                <div className="mt-4 flex justify-end">
                  <button className="text-primary hover:text-primary/80 text-xs font-bold flex items-center gap-1">
                    <CirclePlus className="size-4" />
                    Add Manual Row
                  </button>
                </div>
              </div>
            </div>

            {/* Side Snippet: Activity Log */}
            <div className="w-64 border-l border-[var(--border)]/30 p-4 bg-[var(--card)]/10">
              <h4 className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-4 flex items-center gap-2">
                <History className="size-4" />
                Activity Log
              </h4>
              <div className="space-y-4">
                <div className="flex gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 shrink-0" />
                  <div>
                    <p className="text-[11px] text-[var(--foreground)] leading-tight">
                      Document uploaded: {docDetail.file_name ?? `#${docDetail.id}`}
                    </p>
                    <p className="text-[10px] text-[var(--muted-foreground)] mt-0.5">
                      {formatDate(docDetail.created_at)}
                    </p>
                  </div>
                </div>
                {docDetail.extraction_model && (
                  <div className="flex gap-3">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                    <div>
                      <p className="text-[11px] text-[var(--foreground)] leading-tight">
                        AI extraction via {docDetail.extraction_model}
                        {docDetail.extraction_confidence != null && (
                          <span className="ml-1 text-[var(--muted-foreground)]">
                            ({Math.round(docDetail.extraction_confidence * 100)}% confidence)
                          </span>
                        )}
                      </p>
                      <p className="text-[10px] text-[var(--muted-foreground)] mt-0.5">
                        {formatDate(docDetail.updated_at ?? docDetail.created_at)}
                      </p>
                    </div>
                  </div>
                )}
                <div className="flex gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-1.5 shrink-0" />
                  <div>
                    <p className="text-[11px] text-[var(--foreground)] leading-tight">
                      Pending review
                      {docDetail.reviewed_by && (
                        <span className="ml-1 text-[var(--muted-foreground)]">
                          — assigned to {docDetail.reviewed_by}
                        </span>
                      )}
                    </p>
                    <p className="text-[10px] text-[var(--muted-foreground)] mt-0.5">
                      {formatDate(docDetail.updated_at ?? docDetail.created_at)}
                    </p>
                  </div>
                </div>
              </div>
              <div className="mt-10 p-3 rounded-lg bg-primary/5 border border-primary/10">
                <p className="text-[10px] font-bold text-primary uppercase mb-2">
                  Review Tip
                </p>
                <p className="text-[11px] text-[var(--muted-foreground)] leading-relaxed">
                  Check extracted fields against the original document. Flag any
                  mismatches for correction.
                </p>
              </div>
            </div>
          </div>

          {/* Rejection dialog */}
          {rejecting && (
            <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-20">
              <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-6 w-full max-w-md space-y-4 shadow-2xl">
                <h3 className="text-base font-semibold text-[var(--foreground)]">Reject Document</h3>
                <p className="text-sm text-[var(--muted-foreground)]">
                  Provide a reason for rejecting{' '}
                  <span className="font-medium text-[var(--foreground)]">{doc.file_name ?? `Doc #${doc.id}`}</span>
                </p>
                <textarea
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Describe the issue..."
                  className="w-full h-24 bg-[var(--background)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-primary resize-none"
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
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-red-500 text-white font-medium hover:bg-red-400 transition-all text-sm"
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
                <div className="relative group">
                  <button
                    onClick={() => approveMutation.mutate(doc.id)}
                    disabled={actionLoading}
                    className="px-6 py-2.5 bg-primary hover:bg-primary/90 text-white font-bold rounded-lg text-sm transition-all shadow-lg shadow-primary/30 flex items-center gap-2 ring-1 ring-primary/50 disabled:opacity-50"
                  >
                    <CheckCircle className="size-5" />
                    {approveMutation.isPending ? 'Approving...' : 'Approve'}
                  </button>
                  <span className="absolute -top-1.5 -right-1.5 px-1.5 py-0.5 bg-[var(--background)] border border-[var(--border)] rounded text-[9px] font-bold text-[var(--muted-foreground)] opacity-0 group-hover:opacity-100 transition-opacity">
                    &#8984;&#8629;
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-6">
                <div className="hidden xl:flex items-center gap-4 text-[var(--muted-foreground)] mr-4">
                  <div className="flex items-center gap-1.5">
                    <kbd className="px-1.5 py-0.5 bg-[var(--card)] border border-[var(--border)] rounded text-[10px] font-bold">
                      ESC
                    </kbd>
                    <span className="text-[10px] font-medium uppercase tracking-wider">
                      Cancel
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <kbd className="px-1.5 py-0.5 bg-[var(--card)] border border-[var(--border)] rounded text-[10px] font-bold">
                      J
                    </kbd>
                    <kbd className="px-1.5 py-0.5 bg-[var(--card)] border border-[var(--border)] rounded text-[10px] font-bold">
                      K
                    </kbd>
                    <span className="text-[10px] font-medium uppercase tracking-wider">
                      Navigate
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => setRejecting(true)}
                  disabled={actionLoading}
                  className="px-6 py-2.5 border-2 border-red-500/30 text-red-400 hover:text-[var(--foreground)] hover:bg-red-500/80 hover:border-red-500 font-bold rounded-lg text-sm transition-all flex items-center gap-2 disabled:opacity-50"
                >
                  <Ban className="size-5" />
                  Reject
                </button>
              </div>
            </div>
          </footer>
        </section>
      </div>
    </div>
  )
}
