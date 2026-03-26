import { test, expect } from './fixtures'

const REVIEW_DOCS = [
  { id: 1, file_name: 'packing_list_001.pdf', vendor_name: 'Sigma-Aldrich', document_type: 'packing_list', status: 'needs_review', extraction_confidence: 0.95, created_at: '2026-03-20T10:00:00Z' },
  { id: 2, file_name: 'invoice_002.pdf', vendor_name: 'Thermo Fisher', document_type: 'invoice', status: 'needs_review', extraction_confidence: 0.72, created_at: '2026-03-21T14:30:00Z' },
]

test.describe('Review Page', () => {
  test('shows review queue heading', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: /review queue/i }).click()
    await expect(page.locator('h2').filter({ hasText: 'Review Queue' })).toBeVisible()
  })

  test('shows document count in subtitle', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: /review queue/i }).click()
    await expect(page.getByText(/document.*awaiting/i)).toBeVisible()
  })

  test('shows Document Preview area', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Review Queue' }).click()
    await expect(page.getByText('Document Preview')).toBeVisible()
  })

  test('shows Document Details section', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Review Queue' }).click()
    await expect(page.getByText('Document Details')).toBeVisible()
  })

  test('shows Extracted Line Items table', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Review Queue' }).click()
    await expect(page.getByText('Extracted Line Items')).toBeVisible()
  })

  test('shows Activity Log sidebar', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Review Queue' }).click()
    await expect(page.getByText('Activity Log')).toBeVisible()
  })

  test('Approve button is visible', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Review Queue' }).click()
    await expect(page.getByRole('button', { name: /approve/i })).toBeVisible()
  })

  test('Reject button is visible', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Review Queue' }).click()
    await expect(page.getByRole('button', { name: /reject/i })).toBeVisible()
  })

  test('Reject button opens rejection dialog', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Review Queue' }).click()
    await page.getByRole('button', { name: /reject/i }).click()
    await expect(page.getByText('Reject Document')).toBeVisible()
    await expect(page.getByPlaceholder(/describe the issue/i)).toBeVisible()
    await expect(page.getByRole('button', { name: /confirm rejection/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /cancel/i })).toBeVisible()
  })

  test('empty queue shows upload prompt', async ({ page }) => {
    // Override: return empty queue
    await page.route(/\/api\/v1\/setup\/status/, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ needs_setup: false }) }),
    )
    await page.route(/\/api\/v1\/auth\/me/, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user: { id: 1, name: 'Admin' } }) }),
    )
    await page.route(/\/api\/v1\/alerts/, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) }),
    )
    await page.route(/\/api\/v1\/documents/, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], total: 0 }) }),
    )
    await page.goto('/review')
    await expect(page.getByText(/no documents waiting/i)).toBeVisible()
    await expect(page.getByRole('button', { name: /upload document/i })).toBeVisible()
  })

  test('shows Review Tip box', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Review Queue' }).click()
    await expect(page.getByText('Review Tip')).toBeVisible()
  })
})
