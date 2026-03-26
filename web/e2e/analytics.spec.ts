import { test, expect } from './fixtures'

test.describe('Analytics Page', () => {
  test.beforeEach(async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Analytics' }).click()
    await expect(page).toHaveURL(/\/analytics/)
  })

  test('shows Lab Intelligence tab (default)', async ({ authedPage: page }) => {
    const tab = page.getByRole('button', { name: /lab intelligence/i })
    await expect(tab).toBeVisible()
  })

  test('shows Vendors tab', async ({ authedPage: page }) => {
    await expect(page.getByRole('button', { name: /vendors/i })).toBeVisible()
  })

  test('shows Documents tab', async ({ authedPage: page }) => {
    await expect(page.getByRole('button', { name: /documents/i })).toBeVisible()
  })

  test('shows Inventory tab', async ({ authedPage: page }) => {
    await expect(page.getByRole('button', { name: /inventory/i })).toBeVisible()
  })

  test('Lab Intelligence tab shows insights', async ({ authedPage: page }) => {
    // Overview tab should show stats/insights from API data
    await page.waitForTimeout(1000)
    // Should show some stats or chart content
    await expect(
      page.getByText(/document|vendor|inventory|order/i).first()
    ).toBeVisible()
  })

  test('clicking Vendors tab switches view', async ({ authedPage: page }) => {
    await page.getByRole('button', { name: /vendors/i }).click()
    await page.waitForTimeout(500)
    // Vendor tab content should be visible
    await expect(page.getByRole('button', { name: /vendors/i })).toHaveClass(/text-primary|border-primary/)
  })

  test('clicking Documents tab switches view', async ({ authedPage: page }) => {
    await page.getByRole('button', { name: /documents/i }).click()
    await page.waitForTimeout(500)
    await expect(page.getByRole('button', { name: /documents/i })).toHaveClass(/text-primary|border-primary/)
  })

  test('clicking Inventory tab switches view', async ({ authedPage: page }) => {
    await page.getByRole('button', { name: /inventory/i }).click()
    await page.waitForTimeout(500)
    await expect(page.getByRole('button', { name: /inventory/i })).toHaveClass(/text-primary|border-primary/)
  })
})
