import { test, expect } from './fixtures'

test.describe('Orders Page', () => {
  test.beforeEach(async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Orders' }).click()
    await expect(page).toHaveURL(/\/orders/)
  })

  test('shows Orders heading', async ({ authedPage: page }) => {
    await expect(page.locator('h2').filter({ hasText: 'Orders' })).toBeVisible()
  })

  test('shows order summary text', async ({ authedPage: page }) => {
    await expect(page.getByText(/active.*completed|total orders/i)).toBeVisible()
  })

  test('Active Orders tab is visible and active by default', async ({ authedPage: page }) => {
    const activeTab = page.getByRole('button', { name: 'Active Orders' })
    await expect(activeTab).toBeVisible()
    await expect(activeTab).toHaveClass(/text-primary/)
  })

  test('Past Orders tab is visible', async ({ authedPage: page }) => {
    await expect(page.getByRole('button', { name: 'Past Orders' })).toBeVisible()
  })

  test('Drafts tab is visible', async ({ authedPage: page }) => {
    await expect(page.getByRole('button', { name: 'Drafts' })).toBeVisible()
  })

  test('clicking Past Orders tab switches view', async ({ authedPage: page }) => {
    await page.getByRole('button', { name: 'Past Orders' }).click()
    const pastTab = page.getByRole('button', { name: 'Past Orders' })
    await expect(pastTab).toHaveClass(/text-primary/)
  })

  test('clicking Drafts tab switches view', async ({ authedPage: page }) => {
    await page.getByRole('button', { name: 'Drafts' }).click()
    // Drafts tab should show empty state heading
    await expect(page.getByRole('heading', { name: /no orders found/i })).toBeVisible()
  })

  test('shows featured order card with PO number', async ({ authedPage: page }) => {
    await expect(page.getByText(/PO-2026-001|PO-2026-002/).first()).toBeVisible()
  })

  test('shows vendor name on order card', async ({ authedPage: page }) => {
    await expect(page.getByText('Sigma-Aldrich').first()).toBeVisible()
  })

  test('shows order status badge', async ({ authedPage: page }) => {
    await expect(page.getByText(/shipped|ordered/i).first()).toBeVisible()
  })

  test('progress tracker steps are visible', async ({ authedPage: page }) => {
    await expect(page.getByText('Ordered').first()).toBeVisible()
    await expect(page.getByText('Shipped').first()).toBeVisible()
    await expect(page.getByText('Out for Delivery').first()).toBeVisible()
    await expect(page.getByText('Received').first()).toBeVisible()
  })

  test('Total Monthly Spend card is visible', async ({ authedPage: page }) => {
    await expect(page.getByText('Total Monthly Spend')).toBeVisible()
  })

  test('Items in Transit card is visible', async ({ authedPage: page }) => {
    await expect(page.getByText('Items in Transit')).toBeVisible()
  })

  test('New Requisition button is present (disabled)', async ({ authedPage: page }) => {
    const btn = page.getByRole('button', { name: /new requisition/i })
    await expect(btn).toBeVisible()
    await expect(btn).toBeDisabled()
  })
})
