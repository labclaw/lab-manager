const BASE = '/api'

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
  location_id?: number
  location_name?: string
  lot_number?: string
  quantity?: number
  unit?: string
  expiry_date?: string
  status?: string
}

export interface Document {
  id: number
  filename?: string
  vendor_name?: string
  document_type?: string
  status?: string
  created_at?: string
  review_status?: string
  source_url?: string
  extraction_confidence?: number | null
}

export interface DashboardStats {
  total_spending?: number
  inventory_value?: number
  recent_orders?: number
  low_stock_count?: number
  pending_review?: number
}

export interface Alert {
  id: number
  type: string
  message: string
  severity: string
  acknowledged: boolean
  created_at: string
}

async function apiFetch<T>(url: string, opts?: RequestInit): Promise<T> {
  // Ensure trailing slash for FastAPI compatibility
  const cleanUrl = url.endsWith('/') || opts?.method === 'POST' || url.includes('?') ? url : url + '/'
  const res = await fetch(`${BASE}${cleanUrl}`, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...opts?.headers,
    },
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
    apiFetch<{ status: string; user: User }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  me: () => apiFetch<{ user: User }>('/auth/me'),
  logout: () =>
    fetch(`${BASE}/auth/logout`, { method: 'POST' }).then(() => {}),
}

// Analytics
export const analytics = {
  dashboard: () =>
    apiFetch<DashboardStats>('/analytics/dashboard'),
  spending: (months?: number) =>
    apiFetch<{ monthly: Array<{ month: string; total: number }> }>(
      `/analytics/spending${months ? `?months=${months}` : ''}`,
    ),
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
  list: (page = 1, pageSize = 20) =>
    apiFetch<ApiResponse<Order>>(`/orders?page=${page}&page_size=${pageSize}`),
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
  list: (page = 1, pageSize = 20) =>
    apiFetch<ApiResponse<Document>>(
      `/documents?page=${page}&page_size=${pageSize}`,
    ),
  get: (id: number) => apiFetch<Document>(`/documents/${id}`),
  reviewQueue: () =>
    apiFetch<ApiResponse<Document>>('/documents/?status=needs_review'),
  approve: (id: number) =>
    apiFetch<Document>(`/documents/${id}/approve`, { method: 'POST' }),
  reject: (id: number, reason: string) =>
    apiFetch<Document>(`/documents/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
}

// Search
export const search = {
  query: (q: string) =>
    apiFetch<ApiResponse<unknown>>(`/search?q=${encodeURIComponent(q)}`),
  suggest: (q: string) =>
    apiFetch<{ suggestions: string[] }>(
      `/search/suggest?q=${encodeURIComponent(q)}`,
    ),
}

// Alerts
export const alerts = {
  list: () => apiFetch<ApiResponse<Alert>>('/alerts'),
  acknowledge: (id: number) =>
    apiFetch<Alert>(`/alerts/${id}/acknowledge`, { method: 'POST' }),
}
