import { useEffect, useState } from 'react'
import { documents as docApi } from '@/lib/api'
import type { Document } from '@/lib/api'
import { CheckCircle2, XCircle, AlertTriangle, RefreshCw, ChevronRight } from 'lucide-react'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn } from '@/lib/utils'

interface ReviewPageProps {
  onError?: (error: string) => void
}

export function ReviewPage({ onError }: ReviewPageProps) {
  const [queue, setQueue] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Document | null>(null)
  const [rejecting, setRejecting] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [actionLoading, setActionLoading] = useState(false)

  const loadQueue = async () => {
    setLoading(true)
    try {
      const res = await docApi.reviewQueue()
      const items = res.items ?? []
      setQueue(items)
      // Auto-select first if nothing selected or selected was processed
      if (items.length > 0 && (!selected || !items.find(d => d.id === selected.id))) {
        setSelected(items[0])
      }
      if (items.length === 0) setSelected(null)
    } catch (err) {
      console.error('Failed to load review queue:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadQueue()
  }, [])

  const handleApprove = async () => {
    if (!selected) return
    setActionLoading(true)
    try {
      await docApi.approve(selected.id)
      await loadQueue()
    } catch (err) {
      console.error('Approve failed:', err)
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async () => {
    if (!selected) return
    setActionLoading(true)
    try {
      await docApi.reject(selected.id, rejectReason || 'No reason provided')
      setRejecting(false)
      setRejectReason('')
      await loadQueue()
    } catch (err) {
      console.error('Reject failed:', err)
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 space-y-3">
        <div className="w-8 h-8 border-2 border-[var(--primary)]/30 border-t-[var(--primary)] rounded-full animate-spin" />
        <span className="text-sm text-[var(--muted-foreground)] font-medium">Checking queue...</span>
      </div>
    )
  }

  if (queue.length === 0) {
    return (
      <EmptyState
        icon={CheckCircle2}
        title="All caught up!"
        description="No documents are currently pending manual review."
      />
    )
  }

  return (
    <div className="flex gap-4 h-[calc(100vh-8rem)]">
      {/* Left panel — document list */}
      <div className="w-2/5 flex flex-col min-w-0">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-[var(--warning)]" />
            <h2 className="text-lg font-display font-semibold text-[var(--foreground)]">
              Review Queue
            </h2>
            <span className="badge badge-warning">{queue.length}</span>
          </div>
          <button onClick={loadQueue} className="btn-ghost flex items-center gap-1 text-sm px-2 py-1">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto space-y-1">
          {queue.map((doc) => (
            <button
              key={doc.id}
              onClick={() => { setSelected(doc); setRejecting(false); setRejectReason('') }}
              className={cn(
                'w-full text-left px-3 py-3 rounded-lg border transition-colors',
                selected?.id === doc.id
                  ? 'bg-[var(--primary)]/10 border-[var(--primary)]/30'
                  : 'border-transparent hover:bg-[var(--muted)]'
              )}
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-[var(--foreground)] truncate flex-1">
                  {doc.filename ?? `Doc #${doc.id}`}
                </span>
                <ChevronRight className="w-4 h-4 text-[var(--muted-foreground)] shrink-0" />
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs text-[var(--muted-foreground)]">{doc.vendor_name ?? 'Unknown vendor'}</span>
                <span className="badge badge-info text-[10px]">{doc.document_type ?? 'Unknown'}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Right panel — detail + actions */}
      <div className="w-3/5 card overflow-y-auto">
        {selected ? (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-display font-semibold text-[var(--foreground)]">
                {selected.filename ?? `Document #${selected.id}`}
              </h3>
              <p className="text-sm text-[var(--muted-foreground)] mt-1">
                Review the extracted data and approve or reject.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider">Vendor</span>
                <p className="text-sm text-[var(--foreground)] mt-1">{selected.vendor_name ?? 'Unknown'}</p>
              </div>
              <div>
                <span className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider">Type</span>
                <p className="text-sm text-[var(--foreground)] mt-1">{selected.document_type ?? 'Unknown'}</p>
              </div>
              <div>
                <span className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider">Date</span>
                <p className="text-sm text-[var(--foreground)] mt-1">
                  {selected.created_at ? new Date(selected.created_at).toLocaleString() : '—'}
                </p>
              </div>
              <div>
                <span className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider">Status</span>
                <p className="text-sm mt-1">
                  <span className="badge badge-warning">{selected.status ?? 'needs_review'}</span>
                </p>
              </div>
            </div>

            {selected.source_url && (
              <div>
                <a href={selected.source_url} target="_blank" rel="noopener noreferrer"
                  className="text-sm text-[var(--info)] hover:underline">
                  View original scan
                </a>
              </div>
            )}

            {/* Actions */}
            <div className="border-t border-[var(--border)] pt-4 space-y-3">
              {rejecting ? (
                <div className="space-y-3">
                  <p className="text-sm font-medium text-[var(--foreground)]">Rejection Reason</p>
                  <textarea
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    placeholder="Describe the issue..."
                    className="w-full h-24 bg-[var(--popover)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)] resize-none"
                  />
                  <div className="flex items-center gap-2">
                    <button onClick={handleReject} disabled={actionLoading}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--destructive)] text-white font-medium hover:brightness-110 transition-all text-sm">
                      {actionLoading ? 'Rejecting...' : 'Confirm Rejection'}
                    </button>
                    <button onClick={() => { setRejecting(false); setRejectReason('') }} className="btn-ghost text-sm">
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <button onClick={handleApprove} disabled={actionLoading}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--accent)]/10 text-[var(--accent)] hover:bg-[var(--accent)]/20 font-medium transition-colors text-sm">
                    <CheckCircle2 className="w-4 h-4" />
                    {actionLoading ? 'Approving...' : 'Approve'}
                  </button>
                  <button onClick={() => setRejecting(true)}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--destructive)]/10 text-[var(--destructive)] hover:bg-[var(--destructive)]/20 font-medium transition-colors text-sm">
                    <XCircle className="w-4 h-4" />
                    Reject
                  </button>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-[var(--muted-foreground)] text-sm">
            Select a document to review
          </div>
        )}
      </div>
    </div>
  )
}
