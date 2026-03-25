import { test, expect } from './fixtures'

test.describe('Inventory Page', () => {
  test.beforeEach(async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Inventory' }).click()
    await expect(page).toHaveURL(/\/inventory/)
  })

  test('shows inventory table with items', async ({ authedPage: page }) => {
    await expect(page.getByText('DMEM Medium')).toBeVisible()
    await expect(page.getByText('Fetal Bovine Serum')).toBeVisible()
    await expect(page.getByText('PBS Buffer')).toBeVisible()
  })

  test('table headers are correct', async ({ authedPage: page }) => {
    await expect(page.getByRole('columnheader', { name: 'Item Name' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Lot #' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Vendor' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Location' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Stock' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Actions' })).toBeVisible()
  })

  test('shows lot numbers', async ({ authedPage: page }) => {
    // Lot numbers appear in the Lot # column cells
    await expect(page.locator('td').filter({ hasText: /^LOT-001$/ })).toBeVisible()
    await expect(page.locator('td').filter({ hasText: /^LOT-002$/ })).toBeVisible()
  })

  test('shows vendor names from product data', async ({ authedPage: page }) => {
    await expect(page.getByRole('cell', { name: 'Sigma-Aldrich' }).first()).toBeVisible()
  })

  test('shows location names', async ({ authedPage: page }) => {
    await expect(page.getByText('Cold Room A')).toBeVisible()
    await expect(page.getByText('Freezer B')).toBeVisible()
  })

  test('shows stock quantities', async ({ authedPage: page }) => {
    await expect(page.getByText('25 bottles')).toBeVisible()
    await expect(page.getByText('3 bottles')).toBeVisible()
  })

  test('Low Stock badge visible for low stock items', async ({ authedPage: page }) => {
    await expect(page.getByText('Low Stock')).toBeVisible()
  })

  test('Out of Stock badge visible for zero-quantity items', async ({ authedPage: page }) => {
    await expect(page.getByText('Out of Stock')).toBeVisible()
  })

  test('Filters button is present', async ({ authedPage: page }) => {
    await expect(page.getByRole('button', { name: /filters/i })).toBeVisible()
  })

  test('Category button is present', async ({ authedPage: page }) => {
    await expect(page.getByRole('button', { name: /category/i })).toBeVisible()
  })

  test('total item count shown', async ({ authedPage: page }) => {
    await expect(page.getByText(/3 items total/i)).toBeVisible()
  })

  test('New Item button is present (disabled)', async ({ authedPage: page }) => {
    const btn = page.getByRole('button', { name: /new item/i })
    await expect(btn).toBeVisible()
    await expect(btn).toBeDisabled()
  })

  test('Bulk Order button is present (disabled)', async ({ authedPage: page }) => {
    const btn = page.getByRole('button', { name: /bulk order/i })
    await expect(btn).toBeVisible()
    await expect(btn).toBeDisabled()
  })

  test('guidance banner shows for few items', async ({ authedPage: page }) => {
    await expect(page.getByText(/review and approve more documents/i)).toBeVisible()
  })

  test('Review Queue button in guidance banner works', async ({ authedPage: page }) => {
    await page.getByRole('button', { name: 'Review Queue' }).click()
    await expect(page).toHaveURL(/\/review/)
  })

  test('pagination footer shows item range', async ({ authedPage: page }) => {
    await expect(page.getByText(/showing 1-3 of 3/i)).toBeVisible()
  })

  test('reorder links go to vendor websites', async ({ authedPage: page }) => {
    const reorderLink = page.getByRole('link', { name: /reorder from sigma/i }).first()
    await expect(reorderLink).toBeVisible()
    await expect(reorderLink).toHaveAttribute('href', /sigmaaldrich\.com/)
    await expect(reorderLink).toHaveAttribute('target', '_blank')
  })
})
