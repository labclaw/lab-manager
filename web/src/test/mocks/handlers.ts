import { http, HttpResponse } from 'msw'

// Default mock data
const mockUser = { id: 1, name: 'Dr. Aris Thorne' }

const mockDashboard = {
  total_documents: 42,
  documents_approved: 30,
  documents_pending_review: 5,
  total_orders: 18,
  total_inventory_items: 120,
  total_vendors: 8,
}

const mockVendors = {
  items: [
    { id: 1, name: 'Sigma-Aldrich', contact_email: 'orders@sigma.com', product_count: 15, order_count: 8 },
    { id: 2, name: 'Fisher Scientific', contact_email: 'info@fisher.com', product_count: 22, order_count: 12 },
  ],
  total: 2, page: 1, page_size: 20, pages: 1,
}

const mockProducts = {
  items: [
    { id: 1, name: 'Sodium Chloride', catalog_number: 'S1234', vendor_name: 'Sigma-Aldrich', unit_price: 45.00 },
    { id: 2, name: 'Ethanol 95%', catalog_number: 'E5678', vendor_name: 'Fisher Scientific', unit_price: 32.00 },
  ],
  total: 2, page: 1, page_size: 20, pages: 1,
}

const mockOrders = {
  items: [
    { id: 1, vendor_name: 'Sigma-Aldrich', po_number: 'PO-2026-001', status: 'received', total_amount: 450.00, item_count: 3 },
    { id: 2, vendor_name: 'Fisher Scientific', po_number: 'PO-2026-002', status: 'pending', total_amount: 320.00, item_count: 2 },
  ],
  total: 2, page: 1, page_size: 20, pages: 1,
}

const mockInventory = {
  items: [
    { id: 1, product_name: 'Sodium Chloride', lot_number: 'LOT-ABC', quantity: 5, unit: 'kg', status: 'available', expiry_date: '2027-01-15' },
    { id: 2, product_name: 'Ethanol 95%', lot_number: 'LOT-DEF', quantity: 2, unit: 'L', status: 'opened', expiry_date: '2026-06-30' },
  ],
  total: 2, page: 1, page_size: 20, pages: 1,
}

const mockDocuments = {
  items: [
    { id: 1, file_name: 'invoice_001.pdf', vendor_name: 'Sigma-Aldrich', document_type: 'invoice', status: 'approved', extraction_confidence: 0.95, created_at: '2026-03-15T10:00:00' },
    { id: 2, file_name: 'packing_list_002.pdf', vendor_name: 'Fisher Scientific', document_type: 'packing_list', status: 'needs_review', extraction_confidence: 0.72, created_at: '2026-03-18T14:30:00' },
  ],
  total: 2, page: 1, page_size: 20, pages: 1,
}

const mockReviewQueue = {
  items: [
    { id: 10, file_name: 'review_doc_1.pdf', vendor_name: 'Sigma-Aldrich', document_type: 'invoice', status: 'needs_review', extraction_confidence: 0.65, created_at: '2026-03-19T09:00:00' },
    { id: 11, file_name: 'review_doc_2.pdf', vendor_name: 'Fisher Scientific', document_type: 'packing_list', status: 'needs_review', extraction_confidence: 0.88, created_at: '2026-03-19T10:00:00' },
  ],
  total: 2, page: 1, page_size: 20, pages: 1,
}

const mockAlerts = {
  items: [
    { id: 1, alert_type: 'low_stock', severity: 'warning', message: 'Sodium Chloride below reorder level', is_acknowledged: false, created_at: '2026-03-19T10:00:00' },
    { id: 2, alert_type: 'expiring_soon', severity: 'critical', message: 'Ethanol 95% expires in 3 days', is_acknowledged: false, created_at: '2026-03-19T08:00:00' },
  ],
  total: 2, page: 1, page_size: 20, pages: 1,
}

const mockAlertsSummary = {
  total: 15,
  by_severity: { critical: 2, warning: 8, info: 5 },
  by_type: { low_stock: 4, expiring_soon: 3, expired: 2, pending_review: 6 },
  unacknowledged: 10,
}

const mockSearchResults = {
  items: [
    { id: 1, type: 'product', name: 'Sodium Chloride', description: 'NaCl, laboratory grade' },
  ],
  total: 1, page: 1, page_size: 20, pages: 1,
}

const mockSearchSuggestions = {
  suggestions: ['Sodium Chloride', 'Sodium Hydroxide', 'Sodium Bicarbonate'],
}

const mockLowStock = {
  items: [
    { id: 3, product_name: 'Potassium Chloride', lot_number: 'LOT-GHI', quantity: 1, unit: 'kg', status: 'available' },
  ],
  total: 1, page: 1, page_size: 20, pages: 1,
}

const mockExpiring = {
  items: [
    { id: 2, product_name: 'Ethanol 95%', lot_number: 'LOT-DEF', quantity: 2, unit: 'L', status: 'opened', expiry_date: '2026-03-22' },
  ],
  total: 1, page: 1, page_size: 20, pages: 1,
}

export const handlers = [
  // Auth
  http.get('/api/auth/me', () => HttpResponse.json({ user: mockUser })),
  http.post('/api/auth/login', () => HttpResponse.json({ status: 'ok', user: mockUser })),
  http.post('/api/auth/logout', () => HttpResponse.json({})),

  // Setup
  http.get('/api/setup/status/', () => HttpResponse.json({ needs_setup: false })),

  // Analytics
  http.get('/api/analytics/dashboard/', () => HttpResponse.json(mockDashboard)),
  http.get('/api/analytics/spending', () => HttpResponse.json({ monthly: [{ month: '2026-03', total: 12500 }] })),

  // Vendors
  http.get('/api/vendors', () => HttpResponse.json(mockVendors)),
  http.get('/api/vendors/:id', ({ params }) => {
    const v = mockVendors.items.find(i => i.id === Number(params.id))
    return v ? HttpResponse.json(v) : new HttpResponse(null, { status: 404 })
  }),

  // Products
  http.get('/api/products', () => HttpResponse.json(mockProducts)),
  http.get('/api/products/:id', ({ params }) => {
    const p = mockProducts.items.find(i => i.id === Number(params.id))
    return p ? HttpResponse.json(p) : new HttpResponse(null, { status: 404 })
  }),

  // Orders
  http.get('/api/orders', () => HttpResponse.json(mockOrders)),
  http.get('/api/orders/:id', ({ params }) => {
    const o = mockOrders.items.find(i => i.id === Number(params.id))
    return o ? HttpResponse.json(o) : new HttpResponse(null, { status: 404 })
  }),

  // Inventory
  http.get('/api/inventory', () => HttpResponse.json(mockInventory)),
  http.get('/api/inventory/low-stock/', () => HttpResponse.json(mockLowStock)),
  http.get('/api/inventory/expiring/', () => HttpResponse.json(mockExpiring)),
  http.get('/api/inventory/:id', ({ params }) => {
    const item = mockInventory.items.find(i => i.id === Number(params.id))
    return item ? HttpResponse.json(item) : new HttpResponse(null, { status: 404 })
  }),

  // Documents
  http.get('/api/documents', ({ request }) => {
    const url = new URL(request.url)
    const status = url.searchParams.get('status')
    if (status === 'needs_review') return HttpResponse.json(mockReviewQueue)
    return HttpResponse.json(mockDocuments)
  }),
  http.get('/api/documents/:id', ({ params }) => {
    const all = [...mockDocuments.items, ...mockReviewQueue.items]
    const d = all.find(i => i.id === Number(params.id))
    return d ? HttpResponse.json(d) : new HttpResponse(null, { status: 404 })
  }),
  http.post('/api/documents/:id/review', () => HttpResponse.json({ status: 'ok' })),
  http.post('/api/v1/documents/upload', () => HttpResponse.json({ id: 99, file_name: 'uploaded.pdf', status: 'pending' })),

  // Search
  http.get('/api/search', () => HttpResponse.json(mockSearchResults)),
  http.get('/api/search/suggest', () => HttpResponse.json(mockSearchSuggestions)),

  // Alerts
  http.get('/api/alerts', () => HttpResponse.json(mockAlerts)),
  http.get('/api/alerts/summary/', () => HttpResponse.json(mockAlertsSummary)),
  http.post('/api/alerts/check', () => HttpResponse.json({ new_alerts: 3, summary: mockAlertsSummary })),
  http.post('/api/alerts/:id/acknowledge', () => HttpResponse.json({ status: 'ok' })),
  http.post('/api/alerts/:id/resolve', () => HttpResponse.json({ status: 'ok' })),
]
