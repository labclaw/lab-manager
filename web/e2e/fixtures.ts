import { test as base, expect, type Page } from '@playwright/test'

// ── Constants ────────────────────────────────────────────────────────────

export const TEST_USER = {
  name: 'Test Admin',
  email: 'admin@lab.test',
  password: 'testpassword123',
}

/** All authenticated routes in the app */
export const APP_ROUTES = [
  { path: '/', title: 'Dashboard' },
  { path: '/documents', title: 'Documents' },
  { path: '/review', title: 'Review Queue' },
  { path: '/ask', title: 'Ask AI' },
  { path: '/inventory', title: 'Inventory' },
  { path: '/orders', title: 'Orders' },
  { path: '/upload', title: 'Upload Documents' },
  { path: '/analytics', title: 'Analytics' },
  { path: '/settings', title: 'Settings' },
  { path: '/cloud-brain', title: 'Cloud Brain' },
] as const

// ── Sidebar nav items (matches Sidebar.tsx navItems) ─────────────────────

export const SIDEBAR_NAV = [
  { path: '/', label: 'Dashboard' },
  { path: '/analytics', label: 'Analytics' },
  { path: '/ask', label: 'Ask AI' },
  { path: '/documents', label: 'Documents' },
  { path: '/review', label: 'Review Queue' },
  { path: '/inventory', label: 'Inventory' },
  { path: '/orders', label: 'Orders' },
  { path: '/upload', label: 'Upload' },
  { path: '/cloud-brain', label: 'Cloud Brain' },
] as const

// ── Helper: JSON response factory ───────────────────────────────────────

function json(data: unknown) {
  return {
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(data),
  }
}

// ── Helper: mock all API endpoints ──────────────────────────────────────
// NOTE: apiFetch adds trailing slashes, so /inventory?page=1 becomes
// /inventory/?page=1. We use regex patterns to handle both forms.

export async function mockSetupAndAuth(page: Page) {
  await page.route(/\/api\/v1\/setup\/status/, (route) =>
    route.fulfill(json({ needs_setup: false })),
  )
  await page.route(/\/api\/v1\/auth\/me/, (route) =>
    route.fulfill(json({ user: { id: 1, name: 'Admin' } })),
  )
  await page.route(/\/api\/v1\/auth\/login/, (route) =>
    route.fulfill(json({ status: 'ok', user: { id: 1, name: 'Admin' } })),
  )
  await page.route(/\/api\/v1\/auth\/logout/, (route) =>
    route.fulfill(json({ status: 'ok' })),
  )
}

const DASHBOARD_STATS = {
  total_documents: 42,
  documents_approved: 35,
  documents_pending_review: 5,
  total_orders: 18,
  total_inventory_items: 120,
  total_vendors: 8,
}

const MOCK_DOCUMENTS = [
  { id: 1, file_name: 'packing_list_001.pdf', vendor_name: 'Sigma-Aldrich', document_type: 'packing_list', status: 'approved', extraction_confidence: 0.95, created_at: '2026-03-20T10:00:00Z' },
  { id: 2, file_name: 'invoice_002.pdf', vendor_name: 'Thermo Fisher', document_type: 'invoice', status: 'needs_review', extraction_confidence: 0.72, created_at: '2026-03-21T14:30:00Z' },
  { id: 3, file_name: 'coa_003.pdf', vendor_name: 'Bio-Rad', document_type: 'certificate_of_analysis', status: 'approved', extraction_confidence: 0.88, created_at: '2026-03-22T09:15:00Z' },
  { id: 4, file_name: 'label_004.jpg', vendor_name: 'Sigma-Aldrich', document_type: 'shipping_label', status: 'rejected', extraction_confidence: 0.45, created_at: '2026-03-19T16:00:00Z' },
]

const MOCK_INVENTORY = [
  {
    id: 1, product_name: 'DMEM Medium', lot_number: 'LOT-001', quantity_on_hand: 25, unit: 'bottles', status: 'in_stock',
    product: { id: 1, name: 'DMEM Medium', catalog_number: 'D5796', vendor: { id: 1, name: 'Sigma-Aldrich' } },
    location_name: 'Cold Room A',
  },
  {
    id: 2, product_name: 'Fetal Bovine Serum', lot_number: 'LOT-002', quantity_on_hand: 3, unit: 'bottles', status: 'low_stock',
    product: { id: 2, name: 'Fetal Bovine Serum', catalog_number: 'F7524', vendor: { id: 1, name: 'Sigma-Aldrich' } },
    location_name: 'Freezer B',
  },
  {
    id: 3, product_name: 'PBS Buffer', lot_number: 'LOT-003', quantity_on_hand: 0, unit: 'liters', status: 'out_of_stock',
    product: { id: 3, name: 'PBS Buffer', catalog_number: 'P3813', vendor: { id: 1, name: 'Sigma-Aldrich' } },
    location_name: 'Shelf C',
  },
]

const MOCK_ORDERS = [
  { id: 1, vendor_name: 'Sigma-Aldrich', po_number: 'PO-2026-001', order_date: '2026-03-15', status: 'shipped', total_amount: 1250.00, item_count: 5 },
  { id: 2, vendor_name: 'Thermo Fisher', po_number: 'PO-2026-002', order_date: '2026-03-18', status: 'ordered', total_amount: 890.50, item_count: 3 },
  { id: 3, vendor_name: 'Bio-Rad', po_number: 'PO-2026-003', order_date: '2026-03-01', status: 'received', total_amount: 2100.00, item_count: 8 },
]

export async function mockDashboardAPIs(page: Page) {
  await page.route(/\/api\/v1\/analytics\/dashboard/, (route) =>
    route.fulfill(json(DASHBOARD_STATS)),
  )
  await page.route(/\/api\/v1\/inventory\/low-stock/, (route) =>
    route.fulfill(json({ items: [{ id: 1, product_name: 'DMEM', quantity_on_hand: 2, status: 'low_stock' }], total: 1 })),
  )
  await page.route(/\/api\/v1\/inventory\/expiring/, (route) =>
    route.fulfill(json({ items: [{ id: 2, product_name: 'FBS', expiry_date: '2026-04-01' }], total: 1 })),
  )
  await page.route(/\/api\/v1\/vendors/, (route) =>
    route.fulfill(json({
      items: [
        { id: 1, name: 'Sigma-Aldrich', order_count: 12 },
        { id: 2, name: 'Thermo Fisher', order_count: 8 },
        { id: 3, name: 'Bio-Rad', order_count: 5 },
      ],
      total: 3,
    })),
  )
  // Documents list — matches both /documents/?... and /documents?...
  await page.route(/\/api\/v1\/documents\/?\?/, (route) =>
    route.fulfill(json({ items: MOCK_DOCUMENTS, total: 4, pages: 1 })),
  )
  await page.route(/\/api\/v1\/alerts/, (route) =>
    route.fulfill(json({ items: [], total: 0 })),
  )
}

export async function mockAllAPIs(page: Page) {
  await mockSetupAndAuth(page)
  await mockDashboardAPIs(page)

  // Inventory list — /inventory/?page=... or /inventory?page=...
  await page.route(/\/api\/v1\/inventory\/?\?/, (route) =>
    route.fulfill(json({ items: MOCK_INVENTORY, total: 3, pages: 1 })),
  )

  // Inventory reorder URL
  await page.route(/\/api\/v1\/inventory\/\d+\/reorder-url/, (route) =>
    route.fulfill(json({ url: 'https://www.sigmaaldrich.com/product/D5796' })),
  )

  // Orders list
  await page.route(/\/api\/v1\/orders\/?\?/, (route) =>
    route.fulfill(json({ items: MOCK_ORDERS, total: 3, pages: 1 })),
  )

  // Document detail (by ID)
  await page.route(/\/api\/v1\/documents\/\d+\/?$/, (route) =>
    route.fulfill(json({
      id: 1, file_name: 'packing_list_001.pdf', vendor_name: 'Sigma-Aldrich',
      document_type: 'packing_list', status: 'needs_review', extraction_confidence: 0.95,
      extraction_model: 'gemini-3-pro-preview', created_at: '2026-03-20T10:00:00Z',
      extracted_data: {
        vendor_name: 'Sigma-Aldrich', po_number: 'PO-2026-001', document_type: 'packing_list',
        ship_date: '2026-03-18', received_date: '2026-03-20', received_by: 'John Doe',
        items: [
          { catalog_number: 'D5796', description: 'DMEM Medium', quantity: 6, unit: 'bottles', lot_number: 'SLCM1234', unit_price: 45.00 },
          { catalog_number: 'F7524', description: 'Fetal Bovine Serum', quantity: 2, unit: 'bottles', lot_number: 'SLCM5678', unit_price: 320.00 },
        ],
      },
    })),
  )

  // Document review action
  await page.route(/\/api\/v1\/documents\/\d+\/review/, (route) =>
    route.fulfill(json({ id: 1, status: 'approved' })),
  )

  // Ask AI
  await page.route(/\/api\/v1\/ask/, (route) =>
    route.fulfill(json({
      question: 'test',
      answer: 'Based on the lab data, there are 42 documents processed.',
      sql: 'SELECT count(*) FROM documents',
      raw_results: [{ count: 42 }],
      row_count: 1,
      source: 'sql',
    })),
  )

  // Analytics spending
  await page.route(/\/api\/v1\/analytics\/spending/, (route) =>
    route.fulfill(json({ monthly: [{ month: '2026-03', total: 4240.50 }] })),
  )

  // Analytics documents stats
  await page.route(/\/api\/v1\/analytics\/documents\/stats/, (route) =>
    route.fulfill(json({
      total_documents: 42, by_type: { packing_list: 20, invoice: 15, certificate_of_analysis: 5, shipping_label: 2 },
      by_status: { approved: 35, needs_review: 5, rejected: 2 }, avg_confidence: 0.85,
    })),
  )

  // Config
  await page.route(/\/api\/v1\/config/, (route) =>
    route.fulfill(json({ lab_name: 'Research Lab', lab_subtitle: 'Neuroscience Department', version: '0.1.9' })),
  )

  // Search
  await page.route(/\/api\/v1\/search/, (route) =>
    route.fulfill(json({ items: [], suggestions: [] })),
  )

  // Cloud Brain health
  await page.route(/\/api\/v1\/cloud-brain\/health/, (route) =>
    route.fulfill(json({ status: 'ok', skills: { tooluniverse: true, kdense: true }, tool_count: 2294, version: '0.1.0' })),
  )

  // Document upload
  await page.route(/\/api\/v1\/documents\/upload/, (route) =>
    route.fulfill(json({
      id: 99, file_name: 'test_upload.pdf', vendor_name: 'Test Vendor',
      document_type: 'packing_list', status: 'needs_review', extraction_confidence: 0.88,
    })),
  )
}

// ── Custom test fixture with mocked APIs ─────────────────────────────────

export const test = base.extend<{ authedPage: Page }>({
  authedPage: async ({ page }, use) => {
    await mockAllAPIs(page)
    await page.goto('/')
    // Wait for app to load past the loading spinner
    await page.waitForSelector('text=Dashboard', { timeout: 10_000 }).catch(() => {
      // Fallback: wait for any nav or sidebar element
    })
    await use(page)
  },
})

export { expect }
