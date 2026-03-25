const BASE = '/api/v1'

interface ApiResponse<T> {
  items?: T[]
  total?: number
  page?: number
  page_size?: number
  pages?: number
  detail?: string
}

export interface User {
  id: number
  name: string
}

export interface Vendor {
  id: number
  name: string
  contact_email?: string
  contact_phone?: string
  website?: string
  notes?: string
  product_count?: number
  order_count?: number
}

export interface Product {
  id: number
  name: string
  catalog_number?: string
  vendor_id?: number
  vendor_name?: string
  category?: string
  unit?: string
  unit_price?: number
  description?: string
}

export interface Order {
  id: number
  vendor_id?: number
  vendor_name?: string
  po_number?: string
  order_date?: string
  received_date?: string
  total_amount?: number
  status?: string
  item_count?: number
}

export interface InventoryItem {
  id: number
  product_id?: number
  product_name?: string
  product?: {
    id: number
    name: string
    vendor_id?: number
    vendor?: { id: number; name: string }
  }
  location_id?: number
  location_name?: string
  lot_number?: string
  quantity_on_hand?: number
  unit?: string
  expiry_date?: string
  status?: string
}

export interface ExtractedItem {
  catalog_number?: string
  description?: string
  quantity?: number
  unit?: string
  lot_number?: string
  batch_number?: string
  cas_number?: string
  storage_temp?: string
  unit_price?: number
}

export interface ExtractedDocument {
  vendor_name?: string
  document_type?: string
  po_number?: string
  order_number?: string
  invoice_number?: string
  delivery_number?: string
  order_date?: string
  ship_date?: string
  received_date?: string
  received_by?: string
  ship_to_address?: string
  bill_to_address?: string
  items?: ExtractedItem[]
  confidence?: number
}

export interface Document {
  id: number
  file_name?: string
  file_path?: string
  vendor_name?: string
  document_type?: string
  status?: string
  extraction_confidence?: number
  created_at?: string
  updated_at?: string
  review_status?: string
  source_url?: string
  ocr_text?: string
  extracted_data?: ExtractedDocument
  extraction_model?: string
  review_notes?: string
  reviewed_by?: string
}

export interface DashboardStats {
  total_documents: number
  documents_approved: number
  documents_pending_review: number
  total_orders: number
  total_inventory_items: number
  total_vendors: number
}

export interface DocumentStats {
  total_documents: number
  by_type: Record<string, number>
  by_status: Record<string, number>
  avg_confidence?: number
}

export interface Alert {
  id: number
  type: string
  message: string
  severity: string
  acknowledged: boolean
  created_at: string
}

export interface AskEvidenceRow {
  [key: string]: unknown
}

export interface AskResponse {
  question: string
  answer: string
  sql?: string | null
  raw_results: AskEvidenceRow[]
  row_count?: number
  source: 'sql' | 'search' | string
}

async function apiFetch<T>(url: string, opts?: RequestInit): Promise<T> {
  const headers = new Headers(opts?.headers)
  // Only set Content-Type for non-FormData bodies
  if (!(opts?.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  // Ensure trailing slash on path (before query string) to avoid 307 redirects
  const qIdx = url.indexOf('?')
  const path = qIdx >= 0 ? url.slice(0, qIdx) : url
  const query = qIdx >= 0 ? url.slice(qIdx) : ''
  const normalizedUrl = path.endsWith('/') ? `${path}${query}` : `${path}/${query}`
  const res = await fetch(`${BASE}${normalizedUrl}`, {
    ...opts,
    headers,
  })
  if (res.status === 401) {
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// Auth
export const auth = {
  login: (email: string, password: string) =>
    fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    }).then(async (res) => {
      if (res.status === 401) throw new Error('Unauthorized')
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      return res.json() as Promise<{ status: string; user: User }>
    }),
  me: () =>
    fetch('/api/v1/auth/me').then(async (res) => {
      if (res.status === 401) throw new Error('Unauthorized')
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      return res.json() as Promise<{ user: User }>
    }),
  logout: () =>
    fetch('/api/v1/auth/logout', { method: 'POST' }).then(() => {}),
}

// Setup
export const setup = {
  status: () =>
    fetch('/api/v1/setup/status').then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json() as Promise<{ needs_setup: boolean }>
    }),
  complete: (data: { admin_name: string; admin_email: string; admin_password: string }) =>
    fetch('/api/v1/setup/complete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(async (res) => {
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      return res.json() as Promise<{ status: string }>
    }),
}

// Analytics
export const analytics = {
  dashboard: () =>
    apiFetch<DashboardStats>('/analytics/dashboard'),
  spending: (months?: number) =>
    apiFetch<{ monthly: Array<{ month: string; total: number }> }>(
      `/analytics/spending${months ? `?months=${months}` : ''}`,
    ),
  documentStats: () =>
    apiFetch<DocumentStats>('/analytics/documents/stats'),
}

// Vendors
export const vendors = {
  list: (page = 1, pageSize = 20) =>
    apiFetch<ApiResponse<Vendor>>(`/vendors?page=${page}&page_size=${pageSize}`),
  get: (id: number) => apiFetch<Vendor>(`/vendors/${id}`),
}

// Products
export const products = {
  list: (page = 1, pageSize = 20) =>
    apiFetch<ApiResponse<Product>>(`/products?page=${page}&page_size=${pageSize}`),
  get: (id: number) => apiFetch<Product>(`/products/${id}`),
}

// Orders
export const orders = {
  list: (page = 1, pageSize = 20, statusGroup?: string) =>
    apiFetch<ApiResponse<Order>>(
      `/orders?page=${page}&page_size=${pageSize}${statusGroup ? `&status_group=${statusGroup}` : ""}`,
    ),
  get: (id: number) => apiFetch<Order>(`/orders/${id}`),
}

// Inventory
export const inventory = {
  list: (page = 1, pageSize = 20) =>
    apiFetch<ApiResponse<InventoryItem>>(
      `/inventory?page=${page}&page_size=${pageSize}`,
    ),
  get: (id: number) => apiFetch<InventoryItem>(`/inventory/${id}`),
  lowStock: () =>
    apiFetch<ApiResponse<InventoryItem>>('/inventory/low-stock'),
  expiring: () =>
    apiFetch<ApiResponse<InventoryItem>>('/inventory/expiring'),
}

// Documents
export const documents = {
  list: (page = 1, pageSize = 20, status?: string) =>
    apiFetch<ApiResponse<Document>>(
      `/documents?page=${page}&page_size=${pageSize}${status ? `&status=${status}` : ''}`,
    ),
  get: (id: number) => apiFetch<Document>(`/documents/${id}`),
  reviewQueue: () =>
    apiFetch<ApiResponse<Document>>('/documents?status=needs_review'),
  review: (id: number, body: { action: 'approve' | 'reject'; reviewed_by: string; review_notes?: string }) =>
    apiFetch<Document>(`/documents/${id}/review`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  update: (id: number, data: Record<string, unknown>) =>
    apiFetch<Document>(`/documents/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  upload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return fetch(`${BASE}/documents/upload`, { method: 'POST', body: form })
      .then(async (res) => {
        if (res.status === 401) throw new Error('Unauthorized')
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }))
          throw new Error(err.detail || `HTTP ${res.status}`)
        }
        return res.json() as Promise<Document>
      })
  },
}

export interface SearchResult {
  id: number
  type: string
  name: string
  description?: string
  url?: string
}

// Search
export const search = {
  query: (q: string) =>
    apiFetch<ApiResponse<SearchResult>>(`/search?q=${encodeURIComponent(q)}`),
  suggest: (q: string) =>
    apiFetch<{ suggestions: Array<{ type: string; text: string; id: number }> }>(
      `/search/suggest?q=${encodeURIComponent(q)}`,
    ),
}

// Alerts
export const alerts = {
  list: (filters?: { alert_type?: string; severity?: string; acknowledged?: boolean; resolved?: boolean }) => {
    const params = new URLSearchParams()
    if (filters?.alert_type) params.set('alert_type', filters.alert_type)
    if (filters?.severity) params.set('severity', filters.severity)
    if (filters?.acknowledged != null) params.set('acknowledged', String(filters.acknowledged))
    if (filters?.resolved != null) params.set('resolved', String(filters.resolved))
    const qs = params.toString()
    return apiFetch<ApiResponse<Alert>>(`/alerts${qs ? `?${qs}` : ''}`)
  },
  summary: () => apiFetch<{ total: number; by_severity: Record<string, number>; by_type: Record<string, number>; unacknowledged: number }>('/alerts/summary'),
  check: () => apiFetch<{ new_alerts: number }>('/alerts/check', { method: 'POST' }),
  acknowledge: (id: number) =>
    apiFetch<Alert>(`/alerts/${id}/acknowledge`, { method: 'POST' }),
  resolve: (id: number) =>
    apiFetch<Alert>(`/alerts/${id}/resolve`, { method: 'POST' }),
}

export const ask = {
  query: (question: string) =>
    apiFetch<AskResponse>('/ask', {
      method: 'POST',
      body: JSON.stringify({ question }),
    }),
}
