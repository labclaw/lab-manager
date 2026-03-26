import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { orderRequests, type OrderRequest } from '@/lib/api'
import {
  ClipboardList,
  Plus,
  Check,
  X,
  Clock,
  AlertTriangle,
  Ban,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'

interface RequestsPageProps {
  readonly onError: (msg: string) => void
}

type TabValue = 'my-requests' | 'review-queue'

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  pending: { bg: 'bg-yellow-500/15', text: 'text-yellow-600', label: 'Pending' },
  approved: { bg: 'bg-green-500/15', text: 'text-green-600', label: 'Approved' },
  rejected: { bg: 'bg-red-500/15', text: 'text-red-600', label: 'Rejected' },
  cancelled: { bg: 'bg-gray-500/15', text: 'text-gray-500', label: 'Cancelled' },
}

function StatusBadge({ status }: { readonly status: string }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.pending
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${style.bg} ${style.text}`}>
      {status === 'pending' && <Clock className="size-3" />}
      {status === 'approved' && <Check className="size-3" />}
      {status === 'rejected' && <X className="size-3" />}
      {status === 'cancelled' && <Ban className="size-3" />}
      {style.label}
    </span>
  )
}

function UrgencyBadge({ urgency }: { readonly urgency: string }) {
  if (urgency !== 'urgent') return null
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-orange-500/15 text-orange-600">
      <AlertTriangle className="size-3" />
      Urgent
    </span>
  )
}

export function RequestsPage({ onError }: RequestsPageProps) {
  const [activeTab, setActiveTab] = useState<TabValue>('my-requests')
  const [page, setPage] = useState(1)
  const [showForm, setShowForm] = useState(false)
  const [reviewingId, setReviewingId] = useState<number | null>(null)
  const [reviewNote, setReviewNote] = useState('')
  const queryClient = useQueryClient()
  const pageSize = 20

  // Form state
  const [form, setForm] = useState({
    description: '',
    catalog_number: '',
    quantity: '1',
    unit: '',
    estimated_price: '',
    justification: '',
    urgency: 'normal',
  })

  const statusFilter = activeTab === 'review-queue' ? 'pending' : undefined

  const { data: res, isLoading, error } = useQuery({
    queryKey: ['order-requests', page, activeTab, statusFilter],
    queryFn: () => orderRequests.list(page, pageSize, statusFilter),
  })

  const { data: stats } = useQuery({
    queryKey: ['order-request-stats'],
    queryFn: () => orderRequests.stats(),
  })

  useEffect(() => {
    if (error) {
      onError(error instanceof Error ? error.message : 'Failed to load requests')
    }
  }, [error, onError])

  const createMutation = useMutation({
    mutationFn: orderRequests.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['order-requests'] })
      queryClient.invalidateQueries({ queryKey: ['order-request-stats'] })
      setShowForm(false)
      setForm({ description: '', catalog_number: '', quantity: '1', unit: '', estimated_price: '', justification: '', urgency: 'normal' })
    },
    onError: (err) => onError(err instanceof Error ? err.message : 'Failed to create request'),
  })

  const approveMutation = useMutation({
    mutationFn: ({ id, note }: { id: number; note?: string }) => orderRequests.approve(id, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['order-requests'] })
      queryClient.invalidateQueries({ queryKey: ['order-request-stats'] })
      setReviewingId(null)
      setReviewNote('')
    },
    onError: (err) => onError(err instanceof Error ? err.message : 'Failed to approve'),
  })

  const rejectMutation = useMutation({
    mutationFn: ({ id, note }: { id: number; note?: string }) => orderRequests.reject(id, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['order-requests'] })
      queryClient.invalidateQueries({ queryKey: ['order-request-stats'] })
      setReviewingId(null)
      setReviewNote('')
    },
    onError: (err) => onError(err instanceof Error ? err.message : 'Failed to reject'),
  })

  const cancelMutation = useMutation({
    mutationFn: orderRequests.cancel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['order-requests'] })
      queryClient.invalidateQueries({ queryKey: ['order-request-stats'] })
    },
    onError: (err) => onError(err instanceof Error ? err.message : 'Failed to cancel'),
  })

  const requests = res?.items ?? []
  const total = res?.total ?? 0
  const totalPages = res?.pages ?? 0

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate({
      description: form.description || undefined,
      catalog_number: form.catalog_number || undefined,
      quantity: Number(form.quantity) || 1,
      unit: form.unit || undefined,
      estimated_price: form.estimated_price ? Number(form.estimated_price) : undefined,
      justification: form.justification || undefined,
      urgency: form.urgency,
    })
  }

  const formatDate = (d?: string) => {
    if (!d) return '--'
    return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  }

  const formatPrice = (p?: number) => {
    if (p == null) return '--'
    return `$${Number(p).toFixed(2)}`
  }

  return (
    <div className="space-y-6">
      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {(['pending', 'approved', 'rejected', 'cancelled'] as const).map((s) => (
            <div key={s} className="bg-[var(--card)] rounded-lg border border-primary/10 px-4 py-3">
              <p className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider">{s}</p>
              <p className="text-2xl font-bold text-[var(--foreground)] mt-1">{stats[s]}</p>
            </div>
          ))}
          <div className="bg-[var(--card)] rounded-lg border border-primary/10 px-4 py-3">
            <p className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider">Total</p>
            <p className="text-2xl font-bold text-[var(--foreground)] mt-1">{stats.total}</p>
          </div>
        </div>
      )}

      {/* Tabs + New button */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1 bg-[var(--card)] rounded-lg p-1 border border-primary/10">
          {([
            { value: 'my-requests' as const, label: 'My Requests' },
            { value: 'review-queue' as const, label: 'Review Queue' },
          ]).map((tab) => (
            <button
              key={tab.value}
              onClick={() => { setActiveTab(tab.value); setPage(1) }}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                activeTab === tab.value
                  ? 'bg-primary/10 text-primary'
                  : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
              }`}
            >
              {tab.label}
              {tab.value === 'review-queue' && stats && stats.pending > 0 && (
                <span className="ml-2 bg-yellow-500/20 text-yellow-600 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                  {stats.pending}
                </span>
              )}
            </button>
          ))}
        </div>

        {activeTab === 'my-requests' && (
          <button
            onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Plus className="size-4" />
            New Request
          </button>
        )}
      </div>

      {/* New request form */}
      {showForm && (
        <form onSubmit={handleSubmit} className="bg-[var(--card)] rounded-xl border border-primary/10 p-6 space-y-4">
          <h3 className="text-lg font-semibold text-[var(--foreground)]">New Supply Request</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-[var(--muted-foreground)] mb-1">Description *</label>
              <input
                type="text"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-primary/20 bg-[var(--background)] text-[var(--foreground)] text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                placeholder="e.g., 96-well PCR plates"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--muted-foreground)] mb-1">Catalog Number</label>
              <input
                type="text"
                value={form.catalog_number}
                onChange={(e) => setForm({ ...form, catalog_number: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-primary/20 bg-[var(--background)] text-[var(--foreground)] text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                placeholder="e.g., AB-1234"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--muted-foreground)] mb-1">Quantity *</label>
              <input
                type="number"
                min="1"
                value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-primary/20 bg-[var(--background)] text-[var(--foreground)] text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--muted-foreground)] mb-1">Unit</label>
              <input
                type="text"
                value={form.unit}
                onChange={(e) => setForm({ ...form, unit: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-primary/20 bg-[var(--background)] text-[var(--foreground)] text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                placeholder="e.g., pack, box, ea"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--muted-foreground)] mb-1">Estimated Price ($)</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.estimated_price}
                onChange={(e) => setForm({ ...form, estimated_price: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-primary/20 bg-[var(--background)] text-[var(--foreground)] text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                placeholder="0.00"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--muted-foreground)] mb-1">Urgency</label>
              <div className="flex gap-3 mt-1">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="urgency"
                    value="normal"
                    checked={form.urgency === 'normal'}
                    onChange={(e) => setForm({ ...form, urgency: e.target.value })}
                    className="accent-primary"
                  />
                  <span className="text-sm text-[var(--foreground)]">Normal</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="urgency"
                    value="urgent"
                    checked={form.urgency === 'urgent'}
                    onChange={(e) => setForm({ ...form, urgency: e.target.value })}
                    className="accent-primary"
                  />
                  <span className="text-sm text-orange-600">Urgent</span>
                </label>
              </div>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--muted-foreground)] mb-1">Justification</label>
            <textarea
              value={form.justification}
              onChange={(e) => setForm({ ...form, justification: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-primary/20 bg-[var(--background)] text-[var(--foreground)] text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              rows={2}
              placeholder="Why do you need this?"
            />
          </div>
          <div className="flex gap-3 justify-end">
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-2 rounded-lg text-sm font-medium text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {createMutation.isPending ? 'Submitting...' : 'Submit Request'}
            </button>
          </div>
        </form>
      )}

      {/* Request list */}
      {isLoading ? (
        <div className="text-center py-12">
          <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin mx-auto" />
          <p className="text-sm text-[var(--muted-foreground)] mt-2">Loading...</p>
        </div>
      ) : requests.length === 0 ? (
        <div className="text-center py-16 space-y-3">
          <ClipboardList className="size-12 mx-auto text-[var(--muted-foreground)]" />
          <h3 className="text-lg font-semibold text-[var(--foreground)]">
            {activeTab === 'review-queue' ? 'No pending requests' : 'No requests yet'}
          </h3>
          <p className="text-sm text-[var(--muted-foreground)]">
            {activeTab === 'review-queue'
              ? 'All requests have been reviewed.'
              : 'Click "New Request" to submit a supply request.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {requests.map((req: OrderRequest) => (
            <div
              key={req.id}
              className="bg-[var(--card)] rounded-xl border border-primary/10 p-5 hover:border-primary/20 transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-[var(--foreground)]">
                      #{req.id}
                    </span>
                    <StatusBadge status={req.status} />
                    <UrgencyBadge urgency={req.urgency} />
                    {req.catalog_number && (
                      <span className="text-xs text-[var(--muted-foreground)] bg-[var(--background)] px-2 py-0.5 rounded">
                        {req.catalog_number}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-[var(--foreground)] mt-1">
                    {req.description ?? 'No description'}
                  </p>
                  <div className="flex items-center gap-4 mt-2 text-xs text-[var(--muted-foreground)]">
                    <span>Qty: {Number(req.quantity)}{req.unit ? ` ${req.unit}` : ''}</span>
                    <span>{formatPrice(req.estimated_price)}</span>
                    <span>{formatDate(req.created_at)}</span>
                  </div>
                  {req.justification && (
                    <p className="text-xs text-[var(--muted-foreground)] mt-1 italic">
                      {req.justification}
                    </p>
                  )}
                  {req.review_note && (
                    <p className="text-xs mt-1">
                      <span className="font-medium text-[var(--foreground)]">Review note:</span>{' '}
                      <span className="text-[var(--muted-foreground)]">{req.review_note}</span>
                    </p>
                  )}
                  {req.order_id && (
                    <p className="text-xs text-green-600 mt-1">
                      Order #{req.order_id} created
                    </p>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 shrink-0">
                  {activeTab === 'review-queue' && req.status === 'pending' && reviewingId !== req.id && (
                    <button
                      onClick={() => { setReviewingId(req.id); setReviewNote('') }}
                      className="px-3 py-1.5 text-xs font-medium rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                    >
                      Review
                    </button>
                  )}
                  {activeTab === 'my-requests' && req.status === 'pending' && (
                    <button
                      onClick={() => cancelMutation.mutate(req.id)}
                      disabled={cancelMutation.isPending}
                      className="px-3 py-1.5 text-xs font-medium rounded-lg text-[var(--muted-foreground)] hover:bg-red-500/10 hover:text-red-500 transition-colors"
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </div>

              {/* Review panel */}
              {reviewingId === req.id && (
                <div className="mt-4 pt-4 border-t border-primary/10 space-y-3">
                  <textarea
                    value={reviewNote}
                    onChange={(e) => setReviewNote(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-primary/20 bg-[var(--background)] text-[var(--foreground)] text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                    rows={2}
                    placeholder="Add a note (optional)"
                  />
                  <div className="flex gap-2 justify-end">
                    <button
                      onClick={() => setReviewingId(null)}
                      className="px-3 py-1.5 text-xs font-medium rounded-lg text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => rejectMutation.mutate({ id: req.id, note: reviewNote || undefined })}
                      disabled={rejectMutation.isPending}
                      className="px-4 py-1.5 text-xs font-medium rounded-lg bg-red-500/10 text-red-600 hover:bg-red-500/20 transition-colors disabled:opacity-50"
                    >
                      Reject
                    </button>
                    <button
                      onClick={() => approveMutation.mutate({ id: req.id, note: reviewNote || undefined })}
                      disabled={approveMutation.isPending}
                      className="px-4 py-1.5 text-xs font-medium rounded-lg bg-green-500/10 text-green-600 hover:bg-green-500/20 transition-colors disabled:opacity-50"
                    >
                      Approve
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <p className="text-sm text-[var(--muted-foreground)]">
            {total} request{total !== 1 ? 's' : ''}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page <= 1}
              className="p-1.5 rounded-lg hover:bg-primary/10 disabled:opacity-30 transition-colors"
            >
              <ChevronLeft className="size-4" />
            </button>
            <span className="text-sm text-[var(--muted-foreground)]">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="p-1.5 rounded-lg hover:bg-primary/10 disabled:opacity-30 transition-colors"
            >
              <ChevronRight className="size-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
