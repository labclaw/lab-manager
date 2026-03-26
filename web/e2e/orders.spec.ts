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
    await expect(page.getByText(/orders shown|no orders yet/i)).toBeVisible()
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
    const draftsTab = page.getByRole('button', { name: 'Drafts' })
    await expect(draftsTab).toHaveClass(/text-primary/)
  })
})
