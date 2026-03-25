import { test, expect } from './fixtures'

test.describe('Dashboard Page', () => {
  test('shows all stat cards with correct labels', async ({ authedPage: page }) => {
    await expect(page.getByText('Total Documents').first()).toBeVisible()
    await expect(page.locator('.text-\\[11px\\]').filter({ hasText: 'Approved' }).first()).toBeVisible()
    await expect(page.locator('.text-\\[11px\\]').filter({ hasText: 'Needs Review' }).first()).toBeVisible()
    await expect(page.locator('.text-\\[11px\\]').filter({ hasText: 'Orders Created' }).first()).toBeVisible()
    await expect(page.locator('.text-\\[11px\\]').filter({ hasText: 'Vendors' }).first()).toBeVisible()
  })

  test('shows document count from API', async ({ authedPage: page }) => {
    // The mock returns total_documents: 42
    await expect(page.locator('.text-3xl').filter({ hasText: '42' })).toBeVisible()
  })

  test('shows vendor count from API', async ({ authedPage: page }) => {
    // The mock returns total_vendors: 8
    // The Vendors stat card has a 3xl font number
    const vendorsCard = page.locator('div').filter({ hasText: /^Vendors$/ }).locator('..')
    await expect(vendorsCard.locator('.text-3xl')).toBeVisible()
  })

  test('shows approved count from API', async ({ authedPage: page }) => {
    await expect(page.getByText('35')).toBeVisible()
  })

  test('Quick Actions section is visible', async ({ authedPage: page }) => {
    await expect(page.getByText('Quick Actions')).toBeVisible()
  })

  test('Upload Document button navigates to /upload', async ({ authedPage: page }) => {
    await page.getByRole('button', { name: /upload document/i }).click()
    await expect(page).toHaveURL(/\/upload/)
  })

  test('New Order button navigates to /orders', async ({ authedPage: page }) => {
    await page.getByRole('button', { name: /new order/i }).click()
    await expect(page).toHaveURL(/\/orders/)
  })

  test('Update Stock button navigates to /inventory', async ({ authedPage: page }) => {
    await page.getByRole('button', { name: /update stock/i }).click()
    await expect(page).toHaveURL(/\/inventory/)
  })

  test('Manage Lab button navigates to /settings', async ({ authedPage: page }) => {
    await page.getByRole('button', { name: /manage lab/i }).click()
    await expect(page).toHaveURL(/\/settings/)
  })

  test('Top Lab Vendors chart section visible', async ({ authedPage: page }) => {
    await expect(page.getByText('Top Lab Vendors')).toBeVisible()
  })

  test('Document Classification section visible', async ({ authedPage: page }) => {
    await expect(page.getByText('Document Classification')).toBeVisible()
  })

  test('View All Files link navigates to /documents', async ({ authedPage: page }) => {
    await page.getByText('View All Files').click()
    await expect(page).toHaveURL(/\/documents/)
  })

  test('shows low stock alert when items exist', async ({ authedPage: page }) => {
    await expect(page.getByText(/low stock item/i)).toBeVisible()
  })

  test('shows expiring alert when items exist', async ({ authedPage: page }) => {
    await expect(page.getByText(/expiring item/i)).toBeVisible()
  })

  test('low stock alert navigates to inventory', async ({ authedPage: page }) => {
    await page.getByText(/low stock item/i).click()
    await expect(page).toHaveURL(/\/inventory/)
  })

  test('vendor chart shows vendor names from API', async ({ authedPage: page }) => {
    await expect(page.getByText('Sigma-Aldrich')).toBeVisible()
    await expect(page.getByText('Thermo Fisher')).toBeVisible()
  })
})
