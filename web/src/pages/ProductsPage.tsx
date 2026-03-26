import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  FlaskConical,
  PlusCircle,
  Pencil,
  Trash2,
  Search,
  X,
  ChevronLeft,
  ChevronRight,
  Building2,
  Tag,
  Thermometer,
} from 'lucide-react'
import { products as prodApi, vendors as vendorApi, type Product, type ProductCreate, type ProductUpdate } from '@/lib/api'

interface ProductsPageProps {
  readonly onError: (msg: string) => void
}

interface ProductFormData {
  name: string
  catalog_number: string
  vendor_id: string
  category: string
  cas_number: string
  storage_temp: string
  unit: string
  hazard_info: string
}

const emptyForm: ProductFormData = {
  name: '', catalog_number: '', vendor_id: '', category: '',
  cas_number: '', storage_temp: '', unit: '', hazard_info: '',
}

function productToForm(p: Product): ProductFormData {
  return {
    name: p.name ?? '',
    catalog_number: p.catalog_number ?? '',
    vendor_id: p.vendor_id != null ? String(p.vendor_id) : '',
    category: p.category ?? '',
    cas_number: p.cas_number ?? '',
    storage_temp: p.storage_temp ?? '',
    unit: p.unit ?? '',
    hazard_info: p.hazard_info ?? '',
  }
}

export function ProductsPage({ onError }: ProductsPageProps) {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [searchTerm, setSearchTerm] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Product | null>(null)
  const [form, setForm] = useState<ProductFormData>(emptyForm)
  const [deleteConfirm, setDeleteConfirm] = useState<Product | null>(null)
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
    queryKey: ['products', page, debouncedSearch],
    queryFn: () => prodApi.list(page, pageSize, debouncedSearch || undefined),
  })

  // Fetch vendors for the dropdown in create/edit modal
  const { data: vendorsRes } = useQuery({
    queryKey: ['vendors-for-select'],
    queryFn: () => vendorApi.list(1, 200),
    enabled: modalOpen,
  })

  useEffect(() => {
    if (error) {
      onError(error instanceof Error ? error.message : 'Failed to load products')
    }
  }, [error, onError])

  const createMutation = useMutation({
    mutationFn: (data: ProductCreate) => prodApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] })
      closeModal()
    },
    onError: (err) => onError(err instanceof Error ? err.message : 'Failed to create product'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ProductUpdate }) => prodApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] })
      closeModal()
    },
    onError: (err) => onError(err instanceof Error ? err.message : 'Failed to update product'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => prodApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] })
      setDeleteConfirm(null)
    },
    onError: (err) => onError(err instanceof Error ? err.message : 'Failed to delete product'),
  })

  const items = res?.items ?? []
  const total = res?.total ?? 0
  const totalPages = res?.pages ?? Math.ceil(total / pageSize)
  const vendorOptions = vendorsRes?.items ?? []

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

  function openEdit(product: Product) {
    setEditing(product)
    setForm(productToForm(product))
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
      catalog_number: form.catalog_number.trim(),
      vendor_id: form.vendor_id ? Number(form.vendor_id) : undefined,
      category: form.category.trim() || undefined,
      cas_number: form.cas_number.trim() || undefined,
      storage_temp: form.storage_temp.trim() || undefined,
      unit: form.unit.trim() || undefined,
      hazard_info: form.hazard_info.trim() || undefined,
    }
    if (editing) {
      updateMutation.mutate({ id: editing.id, data })
    } else {
      createMutation.mutate(data as ProductCreate)
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
              placeholder="Search products..."
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
            {total.toLocaleString()} Products total
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={openCreate}
            className="bg-primary text-white font-semibold px-6 py-2.5 rounded-xl text-sm flex items-center gap-2 shadow-lg shadow-primary/20 hover:bg-primary/90 transition-colors"
          >
            <PlusCircle className="size-5" />
            <span>New Product</span>
          </button>
        </div>
      </div>

      {/* Products Data Table */}
      <section className="bg-[var(--card)] rounded-[2rem] shadow-sm overflow-hidden flex flex-col flex-1 border border-outline">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-surface-container-high/50">
                <th className="px-8 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Product</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Catalog #</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Vendor</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Category</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">Storage</th>
                <th className="px-6 py-5 text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline">
              {items.map((product) => (
                <tr key={product.id} className="hover:bg-surface-container-high/30 transition-colors group">
                  <td className="px-8 py-6">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                        <FlaskConical className="size-5 text-primary" />
                      </div>
                      <div>
                        <p className="font-bold text-on-surface">{product.name}</p>
                        {product.cas_number && (
                          <p className="text-[11px] text-[var(--muted-foreground)]">
                            CAS: {product.cas_number}
                          </p>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-6 text-sm font-mono text-[var(--muted-foreground)]">
                    {product.catalog_number ?? '\u2014'}
                  </td>
                  <td className="px-6 py-6 text-sm">
                    {product.vendor_name ?? product.vendor?.name ? (
                      <span className="flex items-center gap-1.5 text-[var(--muted-foreground)]">
                        <Building2 className="size-3.5" />
                        {product.vendor_name ?? product.vendor?.name}
                      </span>
                    ) : (
                      <span className="text-[var(--muted-foreground)]">{'\u2014'}</span>
                    )}
                  </td>
                  <td className="px-6 py-6">
                    {product.category ? (
                      <span className="inline-flex items-center px-2.5 py-1 rounded-lg bg-surface-container-high text-[var(--muted-foreground)] text-xs font-medium border border-outline">
                        <Tag className="size-3.5 mr-1" />
                        {product.category}
                      </span>
                    ) : (
                      <span className="text-[var(--muted-foreground)]">{'\u2014'}</span>
                    )}
                  </td>
                  <td className="px-6 py-6">
                    {product.storage_temp ? (
                      <span className="inline-flex items-center gap-1 text-sm text-[var(--muted-foreground)]">
                        <Thermometer className="size-3.5" />
                        {product.storage_temp}
                      </span>
                    ) : (
                      <span className="text-[var(--muted-foreground)]">{'\u2014'}</span>
                    )}
                  </td>
                  <td className="px-6 py-6 text-right">
                    <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => openEdit(product)}
                        className="p-2 hover:bg-surface-container-highest text-[var(--muted-foreground)] rounded-lg transition-colors"
                        title="Edit Product"
                      >
                        <Pencil className="size-5" />
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(product)}
                        className="p-2 hover:bg-red-500/10 text-[var(--muted-foreground)] hover:text-red-500 rounded-lg transition-colors"
                        title="Delete Product"
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
                <FlaskConical className="size-5 text-[var(--muted-foreground)]" />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-semibold text-on-surface">No products found</h3>
                <p className="text-sm text-[var(--muted-foreground)] max-w-xs mx-auto">
                  {debouncedSearch
                    ? `No products matching "${debouncedSearch}".`
                    : 'Add your first product to get started.'}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Pagination Footer */}
        {total > 0 && (
          <div className="mt-auto px-8 py-4 bg-surface-container-lowest/30 border-t border-outline flex items-center justify-between">
            <span className="text-xs text-[var(--muted-foreground)] font-medium">
              Showing {startItem}-{endItem} of {total.toLocaleString()} products
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
          <div className="bg-[var(--card)] rounded-2xl shadow-xl w-full max-w-lg border border-outline max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b border-outline sticky top-0 bg-[var(--card)] z-10">
              <h3 className="text-lg font-bold text-on-surface">
                {editing ? 'Edit Product' : 'New Product'}
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
                  placeholder="e.g. Sodium Chloride"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-on-surface mb-1">
                    Catalog # <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={form.catalog_number}
                    onChange={(e) => setForm({ ...form, catalog_number: e.target.value })}
                    className="w-full px-3 py-2 bg-[var(--background)] rounded-lg border border-outline text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                    placeholder="e.g. S1234"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-on-surface mb-1">Vendor</label>
                  <select
                    value={form.vendor_id}
                    onChange={(e) => setForm({ ...form, vendor_id: e.target.value })}
                    className="w-full px-3 py-2 bg-[var(--background)] rounded-lg border border-outline text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  >
                    <option value="">No vendor</option>
                    {vendorOptions.map((v) => (
                      <option key={v.id} value={v.id}>{v.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-on-surface mb-1">Category</label>
                  <input
                    type="text"
                    value={form.category}
                    onChange={(e) => setForm({ ...form, category: e.target.value })}
                    className="w-full px-3 py-2 bg-[var(--background)] rounded-lg border border-outline text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                    placeholder="e.g. Chemicals"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-on-surface mb-1">CAS Number</label>
                  <input
                    type="text"
                    value={form.cas_number}
                    onChange={(e) => setForm({ ...form, cas_number: e.target.value })}
                    className="w-full px-3 py-2 bg-[var(--background)] rounded-lg border border-outline text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                    placeholder="e.g. 7647-14-5"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-on-surface mb-1">Storage Temp</label>
                  <input
                    type="text"
                    value={form.storage_temp}
                    onChange={(e) => setForm({ ...form, storage_temp: e.target.value })}
                    className="w-full px-3 py-2 bg-[var(--background)] rounded-lg border border-outline text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                    placeholder="e.g. Room Temperature"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-on-surface mb-1">Unit</label>
                  <input
                    type="text"
                    value={form.unit}
                    onChange={(e) => setForm({ ...form, unit: e.target.value })}
                    className="w-full px-3 py-2 bg-[var(--background)] rounded-lg border border-outline text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                    placeholder="e.g. kg, L, mL"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-on-surface mb-1">Hazard Info</label>
                <input
                  type="text"
                  value={form.hazard_info}
                  onChange={(e) => setForm({ ...form, hazard_info: e.target.value })}
                  className="w-full px-3 py-2 bg-[var(--background)] rounded-lg border border-outline text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  placeholder="e.g. Flammable, Corrosive"
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
                  disabled={isSaving || !form.name.trim() || !form.catalog_number.trim()}
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
            <h3 className="text-lg font-bold text-on-surface mb-2">Delete Product</h3>
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
