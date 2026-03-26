import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Building2,
  PlusCircle,
  Pencil,
  Trash2,
  Search,
  X,
  ChevronLeft,
  ChevronRight,
  Globe,
  Mail,
  Phone,
  Package,
  ShoppingCart,
} from 'lucide-react'
import { vendors as vendorApi, type Vendor, type VendorCreate, type VendorUpdate } from '@/lib/api'

interface VendorsPageProps {
  readonly onError: (msg: string) => void
}

interface VendorFormData {
  name: string
  email: string
  phone: string
  website: string
  notes: string
}

const emptyForm: VendorFormData = { name: '', email: '', phone: '', website: '', notes: '' }

function vendorToForm(v: Vendor): VendorFormData {
  return {
    name: v.name ?? '',
    email: v.email ?? '',
    phone: v.phone ?? '',
    website: v.website ?? '',
    notes: v.notes ?? '',
  }
}

export function VendorsPage({ onError }: VendorsPageProps) {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [searchTerm, setSearchTerm] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Vendor | null>(null)
  const [form, setForm] = useState<VendorFormData>(emptyForm)
  const [deleteConfirm, setDeleteConfirm] = useState<Vendor | null>(null)
  const pageSize = 15

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm)
      setPage(1)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchTerm])

  const { data: res, isLoading, error } = useQuery({
    queryKey: ['vendors', page, debouncedSearch],
    queryFn: () => vendorApi.list(page, pageSize, debouncedSearch || undefined),
  })

  useEffect(() => {
    if (error) {
      onError(error instanceof Error ? error.message : 'Failed to load vendors')
    }
  }, [error, onError])

  const createMutation = useMutation({
    mutationFn: (data: VendorCreate) => vendorApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vendors'] })
      closeModal()
    },
    onError: (err) => onError(err instanceof Error ? err.message : 'Failed to create vendor'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: VendorUpdate }) => vendorApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vendors'] })
      closeModal()
    },
    onError: (err) => onError(err instanceof Error ? err.message : 'Failed to update vendor'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => vendorApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vendors'] })
      setDeleteConfirm(null)
    },
    onError: (err) => onError(err instanceof Error ? err.message : 'Failed to delete vendor'),
  })

  const items = res?.items ?? []
  const total = res?.total ?? 0
  const totalPages = res?.pages ?? Math.ceil(total / pageSize)

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

  function openCreate() {
    setEditing(null)
    setForm(emptyForm)
    setModalOpen(true)
  }

  function openEdit(vendor: Vendor) {
    setEditing(vendor)
    setForm(vendorToForm(vendor))
    setModalOpen(true)
  }

  function closeModal() {
    setModalOpen(false)
    setEditing(null)
    setForm(emptyForm)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const data = {
      name: form.name.trim(),
      email: form.email.trim() || undefined,
      phone: form.phone.trim() || undefined,
      website: form.website.trim() || undefined,
      notes: form.notes.trim() || undefined,
    }
    if (editing) {
      updateMutation.mutate({ id: editing.id, data })
    } else {
      createMutation.mutate(data as VendorCreate)
    }
  }

  const isSaving = createMutation.isPending || updateMutation.isPending

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-8">
      {/* Filters & Actions Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-[var(--muted-foreground)]" />
            <input
              type="text"
              placeholder="Search vendors..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 pr-8 py-2 bg-[var(--card)] rounded-xl shadow-sm text-sm border border-outline focus:outline-none focus:ring-2 focus:ring-primary/30 w-64"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 hover:bg-surface-container-highest rounded"
              >
                <X className="size-3.5 text-[var(--muted-foreground)]" />
              </button>
            )}
          </div>
          <div className="h-6 w-px bg-[var(--border)] mx-2" />
          <span className="text-xs text-[var(--muted-foreground)] font-medium">
            {total.toLocaleString()} Vendors total
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={openCreate}
            className="bg-primary text-white font-semibold px-6 py-2.5 rounded-xl text-sm flex items-center gap-2 shadow-lg shadow-primary/20 hover:bg-primary/90 transition-colors"
          >
            <PlusCircle className="size-5" />
            <span>New Vendor</span>
          </button>
        </div>
      </div>

      {/* Vendors Data Table */}
      <section className="bg-[var(--card)] rounded-[2rem] shadow-sm overflow-hidden flex flex-col flex-1 border border-outline">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-surface-container-high/50">
                <th className="px-8 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Vendor</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Email</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Phone</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Website</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline">
              {items.map((vendor) => (
                <tr key={vendor.id} className="hover:bg-surface-container-high/30 transition-colors group">
                  <td className="px-8 py-6">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                        <Building2 className="size-5 text-primary" />
                      </div>
                      <div>
                        <p className="font-bold text-on-surface">{vendor.name}</p>
                        <div className="flex items-center gap-3 mt-0.5">
                          {vendor.product_count != null && (
                            <span className="text-[11px] text-[var(--muted-foreground)] flex items-center gap-1">
                              <Package className="size-3" />
                              {vendor.product_count} products
                            </span>
                          )}
                          {vendor.order_count != null && (
                            <span className="text-[11px] text-[var(--muted-foreground)] flex items-center gap-1">
                              <ShoppingCart className="size-3" />
                              {vendor.order_count} orders
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-6 text-sm text-[var(--muted-foreground)]">
                    {vendor.email ? (
                      <a href={`mailto:${vendor.email}`} className="flex items-center gap-1.5 hover:text-primary transition-colors">
                        <Mail className="size-3.5" />
                        {vendor.email}
                      </a>
                    ) : (
                      '\u2014'
                    )}
                  </td>
                  <td className="px-6 py-6 text-sm text-[var(--muted-foreground)]">
                    {vendor.phone ? (
                      <span className="flex items-center gap-1.5">
                        <Phone className="size-3.5" />
                        {vendor.phone}
                      </span>
                    ) : (
                      '\u2014'
                    )}
                  </td>
                  <td className="px-6 py-6 text-sm">
                    {vendor.website ? (
                      <a
                        href={vendor.website.startsWith('http') ? vendor.website : `https://${vendor.website}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1.5 text-primary hover:underline"
                      >
                        <Globe className="size-3.5" />
                        {vendor.website.replace(/^https?:\/\//, '')}
                      </a>
                    ) : (
                      <span className="text-[var(--muted-foreground)]">{'\u2014'}</span>
                    )}
                  </td>
                  <td className="px-6 py-6 text-right">
                    <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => openEdit(vendor)}
                        className="p-2 hover:bg-surface-container-highest text-[var(--muted-foreground)] rounded-lg transition-colors"
                        title="Edit Vendor"
                      >
                        <Pencil className="size-5" />
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(vendor)}
                        className="p-2 hover:bg-red-500/10 text-[var(--muted-foreground)] hover:text-red-500 rounded-lg transition-colors"
                        title="Delete Vendor"
                      >
                        <Trash2 className="size-5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {items.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center space-y-4">
              <div className="w-12 h-12 rounded-2xl bg-surface-container-high flex items-center justify-center">
                <Building2 className="size-5 text-[var(--muted-foreground)]" />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-semibold text-on-surface">No vendors found</h3>
                <p className="text-sm text-[var(--muted-foreground)] max-w-xs mx-auto">
                  {debouncedSearch
                    ? `No vendors matching "${debouncedSearch}".`
                    : 'Add your first vendor to get started.'}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Pagination Footer */}
        {total > 0 && (
          <div className="mt-auto px-8 py-4 bg-surface-container-lowest/30 border-t border-outline flex items-center justify-between">
            <span className="text-xs text-[var(--muted-foreground)] font-medium">
              Showing {startItem}-{endItem} of {total.toLocaleString()} vendors
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-surface-container-highest transition-colors disabled:opacity-30"
              >
                <ChevronLeft className="size-4" />
              </button>
              {pageNumbers.map((pn, idx) =>
                pn === 'ellipsis' ? (
                  <span key={`e${idx}`} className="text-slate-500/50 text-xs px-1">...</span>
                ) : (
                  <button
                    key={pn}
                    onClick={() => setPage(pn)}
                    className={`w-8 h-8 flex items-center justify-center rounded-lg text-xs font-bold transition-colors ${
                      pn === page
                        ? 'bg-primary text-white'
                        : 'hover:bg-surface-container-highest font-medium'
                    }`}
                  >
                    {pn}
                  </button>
                )
              )}
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-surface-container-highest transition-colors disabled:opacity-30"
              >
                <ChevronRight className="size-4" />
              </button>
            </div>
          </div>
        )}
      </section>

      {/* Create/Edit Modal */}
      {modalOpen && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-[var(--card)] rounded-2xl shadow-xl w-full max-w-lg border border-outline">
            <div className="flex items-center justify-between px-6 py-4 border-b border-outline">
              <h3 className="text-lg font-bold text-on-surface">
                {editing ? 'Edit Vendor' : 'New Vendor'}
              </h3>
              <button onClick={closeModal} className="p-1 hover:bg-surface-container-highest rounded-lg transition-colors">
                <X className="size-5 text-[var(--muted-foreground)]" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-on-surface mb-1">
                  Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full px-3 py-2 bg-[var(--background)] rounded-lg border border-outline text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  placeholder="e.g. Sigma-Aldrich"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-on-surface mb-1">Email</label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="w-full px-3 py-2 bg-[var(--background)] rounded-lg border border-outline text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                    placeholder="orders@vendor.com"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-on-surface mb-1">Phone</label>
                  <input
                    type="text"
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    className="w-full px-3 py-2 bg-[var(--background)] rounded-lg border border-outline text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                    placeholder="+1 (555) 000-0000"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-on-surface mb-1">Website</label>
                <input
                  type="text"
                  value={form.website}
                  onChange={(e) => setForm({ ...form, website: e.target.value })}
                  className="w-full px-3 py-2 bg-[var(--background)] rounded-lg border border-outline text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  placeholder="https://vendor.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-on-surface mb-1">Notes</label>
                <textarea
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2 bg-[var(--background)] rounded-lg border border-outline text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none"
                  placeholder="Additional notes about this vendor..."
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={closeModal}
                  className="px-4 py-2 text-sm font-medium text-[var(--muted-foreground)] hover:text-on-surface transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSaving || !form.name.trim()}
                  className="bg-primary text-white px-6 py-2 rounded-xl text-sm font-semibold shadow-lg shadow-primary/20 hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSaving ? 'Saving...' : editing ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-[var(--card)] rounded-2xl shadow-xl w-full max-w-sm border border-outline p-6">
            <h3 className="text-lg font-bold text-on-surface mb-2">Delete Vendor</h3>
            <p className="text-sm text-[var(--muted-foreground)] mb-6">
              Are you sure you want to delete <strong>{deleteConfirm.name}</strong>? This cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 text-sm font-medium text-[var(--muted-foreground)] hover:text-on-surface transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMutation.mutate(deleteConfirm.id)}
                disabled={deleteMutation.isPending}
                className="bg-red-500 text-white px-6 py-2 rounded-xl text-sm font-semibold hover:bg-red-600 transition-colors disabled:opacity-50"
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
