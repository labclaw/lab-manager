import { useEffect, useState } from 'react'
import { documents as docApi } from '@/lib/api'
import type { Document } from '@/lib/api'
import { CheckCircle2, XCircle, AlertTriangle, RefreshCw, ClipboardCheck } from 'lucide-react'
import { EmptyState } from '@/components/ui/EmptyState'

interface ReviewPageProps {
  onError?: (error: string) => void
}

export function ReviewPage({ onError }: ReviewPageProps) {
  const [queue, setQueue] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [action, setAction] = useState<{ id: number; type: 'approve' | 'reject' } | null>(null)
  const [rejectReason, setRejectReason] = useState('')

  const loadQueue = async () => {
    setLoading(true)
    try {
      const res = await docApi.reviewQueue()
      setQueue(res.items ?? [])
    } catch (err) {
      console.error('Failed to load review queue:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadQueue()
  }, [])

  const handleAction = async () => {
    if (!action) return
    try {
      if (action.type === 'approve') {
        await docApi.approve(action.id)
      } else {
        await docApi.reject(action.id, rejectReason || 'No reason provided')
      }
      setAction(null)
      setRejectReason('')
      loadQueue()
    } catch (err) {
      console.error('Action failed:', err)
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
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-[var(--warning)]" />
          <h2 className="text-lg font-display font-semibold text-[var(--foreground)]">
            Review Queue
          </h2>
          <span className="badge badge-warning">{queue.length}</span>
        </div>
        <button onClick={loadQueue} className="btn-ghost flex items-center gap-2">
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {queue.map((doc) => (
        <div key={doc.id} className="card">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 space-y-2">
              <div className="flex items-center gap-3">
                <span className="text-[var(--foreground)] font-medium">
                  {doc.filename ?? `Doc #${doc.id}`}
                </span>
                <span className="badge badge-info">
                  {doc.document_type ?? 'Unknown'}
                </span>
              </div>
              <p className="text-sm text-[var(--muted-foreground)]">
                Vendor: {doc.vendor_name ?? 'Unknown'}
              </p>
              {doc.source_url && (
                <a
                  href={doc.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-[var(--info)] hover:underline"
                >
                  View original scan
                </a>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setAction({ id: doc.id, type: 'approve' })}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--accent)]/10 text-[var(--accent)] hover:bg-[var(--accent)]/20 text-sm font-medium transition-colors"
              >
                <CheckCircle2 className="w-4 h-4" />
                Approve
              </button>
              <button
                onClick={() => setAction({ id: doc.id, type: 'reject' })}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--destructive)]/10 text-[var(--destructive)] hover:bg-[var(--destructive)]/20 text-sm font-medium transition-colors"
              >
                <XCircle className="w-4 h-4" />
                Reject
              </button>
            </div>
          </div>
        </div>
      ))}

      {/* Reject modal */}
      {action && action.type === 'reject' && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-md space-y-4">
            <h3 className="text-lg font-display font-semibold text-[var(--foreground)]">
              Reject Document #{action.id}
            </h3>
            <p className="text-sm text-[var(--muted-foreground)]">
              Provide a reason for rejection. This helps improve the extraction pipeline.
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Describe the issue..."
              className="w-full h-24 bg-[var(--popover)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)] resize-none"
            />
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => {
                  setAction(null)
                  setRejectReason('')
                }}
                className="btn-ghost"
              >
                Cancel
              </button>
              <button
                onClick={handleAction}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--destructive)] text-white font-medium hover:brightness-110 transition-all"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
