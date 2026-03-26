import { http, HttpResponse } from 'msw'

// Default mock data
const mockUser = {
  id: 1,
  name: 'Dr. Aris Thorne',
  email: 'aris@example.com',
  role: 'admin',
}

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
    { id: 1, name: 'Sigma-Aldrich', email: 'orders@sigma.com', phone: '+1-800-325-3010', website: 'https://sigmaaldrich.com', notes: 'Primary chemical supplier', product_count: 15, order_count: 8 },
    { id: 2, name: 'Fisher Scientific', email: 'info@fisher.com', phone: '+1-800-766-7000', website: 'https://fishersci.com', notes: '', product_count: 22, order_count: 12 },
  ],
  total: 2, page: 1, page_size: 20, pages: 1,
}

const mockProducts = {
  items: [
    { id: 1, name: 'Sodium Chloride', catalog_number: 'S1234', vendor_id: 1, vendor_name: 'Sigma-Aldrich', category: 'Chemicals', cas_number: '7647-14-5', storage_temp: 'Room Temperature', unit: 'kg' },
    { id: 2, name: 'Ethanol 95%', catalog_number: 'E5678', vendor_id: 2, vendor_name: 'Fisher Scientific', category: 'Solvents', cas_number: '64-17-5', storage_temp: '15-25C', unit: 'L' },
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
    { id: 1, product_id: 1, product_name: 'Sodium Chloride', catalog_number: 'S1234', category: 'Chemicals', vendor_name: 'Sigma-Aldrich', location_name: 'Shelf A1', lot_number: 'LOT-ABC', quantity_on_hand: 5, quantity_display: '5', unit: 'kg', status: 'available', expiry_date: '2027-01-15' },
    { id: 2, product_id: 2, product_name: 'Ethanol 95%', catalog_number: 'E5678', category: 'Solvents', vendor_name: 'Fisher Scientific', location_name: null, lot_number: 'LOT-DEF', quantity_on_hand: 2, quantity_display: '2', unit: 'L', status: 'opened', expiry_date: '2026-06-30' },
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
    { id: 1, alert_type: 'low_stock', severity: 'warning', message: 'Sodium Chloride below reorder level', entity_type: 'inventory', entity_id: 1, is_acknowledged: false, is_resolved: false, created_at: '2026-03-19T10:00:00' },
    { id: 2, alert_type: 'expiring_soon', severity: 'critical', message: 'Ethanol 95% expires in 3 days', entity_type: 'inventory', entity_id: 2, is_acknowledged: false, is_resolved: false, created_at: '2026-03-19T08:00:00' },
  ],
  total: 2, page: 1, page_size: 50, pages: 1,
}

const mockAlertsSummary = {
  total: 15,
  by_severity: { critical: 2, warning: 8, info: 5 },
  by_type: { low_stock: 4, expiring_soon: 3, expired: 2, pending_review: 6 },
  unacknowledged: 10,
}

const mockNotifications = {
  items: [
    {
      id: 1,
      type: 'low_stock',
      title: 'Low stock alert',
      message: 'Sodium Chloride is below reorder level',
      is_read: false,
      created_at: '2026-03-19T10:00:00Z',
    },
    {
      id: 2,
      type: 'document_review',
      title: 'Document ready for review',
      message: 'A new invoice needs attention',
      is_read: false,
      created_at: '2026-03-19T09:00:00Z',
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
  pages: 1,
}

const mockSearchResults = {
  items: [
    { id: 1, type: 'product', name: 'Sodium Chloride', description: 'NaCl, laboratory grade' },
  ],
  total: 1, page: 1, page_size: 20, pages: 1,
}

const mockSearchSuggestions = {
  suggestions: [
    { type: 'product', text: 'Sodium Chloride', id: 1 },
    { type: 'product', text: 'Sodium Hydroxide', id: 2 },
    { type: 'product', text: 'Sodium Bicarbonate', id: 3 },
  ],
}

const mockLowStock = {
  items: [
    { id: 3, product_name: 'Potassium Chloride', lot_number: 'LOT-GHI', quantity_on_hand: 1, unit: 'kg', status: 'available' },
  ],
  total: 1, page: 1, page_size: 20, pages: 1,
}

const mockExpiring = {
  items: [
    { id: 2, product_name: 'Ethanol 95%', lot_number: 'LOT-DEF', quantity_on_hand: 2, unit: 'L', status: 'opened', expiry_date: '2026-03-22' },
  ],
  total: 1, page: 1, page_size: 20, pages: 1,
}

export const handlers = [
  // Auth
  http.get('/api/v1/auth/me', () => HttpResponse.json({ user: mockUser })),
  http.post('/api/v1/auth/login', () => HttpResponse.json({ status: 'ok', user: mockUser })),
  http.post('/api/v1/auth/logout', () => HttpResponse.json({})),

  // Setup
  http.get('/api/v1/setup/status', () => HttpResponse.json({ needs_setup: false })),

  // Config
  http.get('/api/v1/config', () =>
    HttpResponse.json({
      lab_name: 'Research Lab',
      lab_subtitle: 'Neuroscience Department',
      version: '0.1.10',
      ocr_model: 'nvidia_nim/meta/llama-3.2-90b-vision-instruct',
      extraction_model: 'nvidia_nim/z-ai/glm5',
      rag_model: 'nvidia_nim/z-ai/glm5-turbo',
      ocr_tier: 'auto',
    }),
  ),

  // Analytics
  http.get('/api/v1/analytics/dashboard', () => HttpResponse.json(mockDashboard)),
  http.get('/api/v1/analytics/spending', () => HttpResponse.json({ monthly: [{ month: '2026-03', total: 12500 }] })),

  // Vendors
  http.get('/api/v1/vendors/', () => HttpResponse.json(mockVendors)),
  http.get('/api/v1/vendors/:id/', ({ params }) => {
    const v = mockVendors.items.find(i => i.id === Number(params.id))
    return v ? HttpResponse.json(v) : new HttpResponse(null, { status: 404 })
  }),
  http.post('/api/v1/vendors/', () => HttpResponse.json({ id: 3, name: 'New Vendor', email: null, phone: null, website: null, notes: null }, { status: 201 })),
  http.patch('/api/v1/vendors/:id/', () => HttpResponse.json({ id: 1, name: 'Updated Vendor' })),
  http.delete('/api/v1/vendors/:id/', () => new HttpResponse(null, { status: 204 })),
  http.get('/api/v1/vendors/:id/products/', () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20, pages: 0 })),
  http.get('/api/v1/vendors/:id/orders/', () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20, pages: 0 })),

  // Products
  http.get('/api/v1/products/', () => HttpResponse.json(mockProducts)),
  http.get('/api/v1/products/:id/', ({ params }) => {
    const p = mockProducts.items.find(i => i.id === Number(params.id))
    return p ? HttpResponse.json(p) : new HttpResponse(null, { status: 404 })
  }),
  http.post('/api/v1/products/', () => HttpResponse.json({ id: 3, name: 'New Product', catalog_number: 'NP001' }, { status: 201 })),
  http.patch('/api/v1/products/:id/', () => HttpResponse.json({ id: 1, name: 'Updated Product' })),
  http.delete('/api/v1/products/:id/', () => new HttpResponse(null, { status: 204 })),
  http.get('/api/v1/products/:id/inventory/', () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20, pages: 0 })),

  // Orders
  http.get('/api/v1/orders', ({ request }) => {
    const url = new URL(request.url)
    const statusGroup = url.searchParams.get('status_group')
    if (statusGroup === 'active') {
      return HttpResponse.json({
        items: mockOrders.items.filter(o => o.status !== 'received' && o.status !== 'cancelled'),
        total: mockOrders.items.filter(o => o.status !== 'received' && o.status !== 'cancelled').length,
        page: 1, page_size: 20, pages: 1,
      })
    }
    if (statusGroup === 'past') {
      return HttpResponse.json({
        items: mockOrders.items.filter(o => o.status === 'received' || o.status === 'cancelled'),
        total: mockOrders.items.filter(o => o.status === 'received' || o.status === 'cancelled').length,
        page: 1, page_size: 20, pages: 1,
      })
    }
    if (statusGroup === 'drafts') {
      return HttpResponse.json({
        items: mockOrders.items.filter(o => o.status === 'draft'),
        total: mockOrders.items.filter(o => o.status === 'draft').length,
        page: 1, page_size: 20, pages: 1,
      })
    }
    return HttpResponse.json(mockOrders)
  }),
  http.get('/api/v1/orders/:id', ({ params }) => {
    const o = mockOrders.items.find(i => i.id === Number(params.id))
    return o ? HttpResponse.json(o) : new HttpResponse(null, { status: 404 })
  }),

  // Inventory
  http.get('/api/v1/inventory', () => HttpResponse.json(mockInventory)),
  http.get('/api/v1/inventory/low-stock', () => HttpResponse.json(mockLowStock)),
  http.get('/api/v1/inventory/expiring', () => HttpResponse.json(mockExpiring)),
  http.get('/api/v1/inventory/:id/reorder-url', ({ params }) => {
    const urls: Record<string, string> = { '1': 'https://www.sigmaaldrich.com/product/S1234', '2': 'https://www.fishersci.com/product/E5678' }
    const url = urls[String(params.id)]
    return url ? HttpResponse.json({ url }) : HttpResponse.json({ url: null })
  }),
  http.get('/api/v1/inventory/:id', ({ params }) => {
    const item = mockInventory.items.find(i => i.id === Number(params.id))
    return item ? HttpResponse.json(item) : new HttpResponse(null, { status: 404 })
  }),

  // Documents
  http.get('/api/v1/documents', ({ request }) => {
    const url = new URL(request.url)
    const status = url.searchParams.get('status')
    if (status === 'needs_review') return HttpResponse.json(mockReviewQueue)
    return HttpResponse.json(mockDocuments)
  }),
  http.get('/api/v1/documents/:id', ({ params }) => {
    const all = [...mockDocuments.items, ...mockReviewQueue.items]
    const d = all.find(i => i.id === Number(params.id))
    return d ? HttpResponse.json(d) : new HttpResponse(null, { status: 404 })
  }),
  http.post('/api/v1/documents/:id/review', () => HttpResponse.json({ status: 'ok' })),
  http.post('/api/v1/documents/upload', () => HttpResponse.json({ id: 99, file_name: 'uploaded.pdf', status: 'needs_review' })),

  // Search
  http.get('/api/v1/search', () => HttpResponse.json(mockSearchResults)),
  http.get('/api/v1/search/suggest', () => HttpResponse.json(mockSearchSuggestions)),

  // Alerts
  http.get('/api/v1/alerts', () => HttpResponse.json(mockAlerts)),
  http.get('/api/v1/alerts/summary', () => HttpResponse.json(mockAlertsSummary)),
  http.post('/api/v1/alerts/check', () => HttpResponse.json({ new_alerts: 3, summary: mockAlertsSummary })),
  http.post('/api/v1/alerts/:id/acknowledge', () => HttpResponse.json({ status: 'ok' })),
  http.post('/api/v1/alerts/:id/resolve', () => HttpResponse.json({ status: 'ok' })),

  // Notifications
  http.get('/api/v1/notifications/count/', () =>
    HttpResponse.json({ unread_count: mockNotifications.items.filter((item) => !item.is_read).length }),
  ),
  http.get('/api/v1/notifications/', () => HttpResponse.json(mockNotifications)),
  http.post('/api/v1/notifications/:id/read/', ({ params }) => {
    const item = mockNotifications.items.find((entry) => entry.id === Number(params.id))
    return item
      ? HttpResponse.json({ ...item, is_read: true })
      : new HttpResponse(null, { status: 404 })
  }),
  http.post('/api/v1/notifications/read-all/', () =>
    HttpResponse.json({ marked: mockNotifications.items.length }),
  ),
  http.get('/api/v1/notifications/preferences/', () =>
    HttpResponse.json({
      id: 1,
      staff_id: 1,
      in_app: true,
      email_weekly: false,
      order_requests: true,
      document_reviews: true,
      inventory_alerts: true,
      team_changes: false,
    }),
  ),
]
