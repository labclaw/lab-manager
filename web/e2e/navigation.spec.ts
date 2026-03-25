import { test, expect, SIDEBAR_NAV } from './fixtures'

test.describe('Navigation', () => {
  test('sidebar shows Lab Manager branding', async ({ authedPage: page }) => {
    await expect(page.getByText('Lab Manager')).toBeVisible()
    await expect(page.getByText('Laboratory')).toBeVisible()
  })

  test('all sidebar nav links are visible', async ({ authedPage: page }) => {
    for (const nav of SIDEBAR_NAV) {
      await expect(page.getByRole('link', { name: nav.label })).toBeVisible()
    }
  })

  test('Settings link is visible in sidebar footer', async ({ authedPage: page }) => {
    await expect(page.getByRole('link', { name: 'Settings' })).toBeVisible()
  })

  test('Sign Out button is visible in sidebar footer', async ({ authedPage: page }) => {
    await expect(page.getByRole('button', { name: /sign out/i })).toBeVisible()
  })

  test('Admin user shown in sidebar', async ({ authedPage: page }) => {
    await expect(page.getByText('Admin').first()).toBeVisible()
  })

  test('sidebar collapse toggle is present', async ({ authedPage: page }) => {
    await expect(
      page.getByRole('button', { name: /collapse sidebar|expand sidebar/i })
    ).toBeAttached()
  })

  test('Dashboard link navigates to /', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Analytics' }).click()
    await page.getByRole('link', { name: 'Dashboard' }).click()
    // URL should end with / or have no path after the host
    await expect(page).toHaveURL(/:\d+\/?$/)
  })

  test('Analytics link navigates to /analytics', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Analytics' }).click()
    await expect(page).toHaveURL(/\/analytics/)
  })

  test('Ask AI link navigates to /ask', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Ask AI' }).click()
    await expect(page).toHaveURL(/\/ask/)
  })

  test('Documents link navigates to /documents', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Documents' }).click()
    await expect(page).toHaveURL(/\/documents/)
  })

  test('Review Queue link navigates to /review', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Review Queue' }).click()
    await expect(page).toHaveURL(/\/review/)
  })

  test('Inventory link navigates to /inventory', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Inventory' }).click()
    await expect(page).toHaveURL(/\/inventory/)
  })

  test('Orders link navigates to /orders', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Orders' }).click()
    await expect(page).toHaveURL(/\/orders/)
  })

  test('Upload link navigates to /upload', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Upload' }).click()
    await expect(page).toHaveURL(/\/upload/)
  })

  test('Cloud Brain link navigates to /cloud-brain', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Cloud Brain' }).click()
    await expect(page).toHaveURL(/\/cloud-brain/)
  })

  test('Settings link navigates to /settings', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Settings' }).click()
    await expect(page).toHaveURL(/\/settings/)
  })

  test('active sidebar link has correct styling', async ({ authedPage: page }) => {
    // On dashboard, the Dashboard link should be active
    const dashLink = page.getByRole('link', { name: 'Dashboard' })
    await expect(dashLink).toHaveClass(/bg-primary\/10/)
  })

  test('navigating changes active sidebar link', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Inventory' }).click()
    const invLink = page.getByRole('link', { name: 'Inventory' })
    await expect(invLink).toHaveClass(/bg-primary\/10/)
    // Dashboard should no longer be active
    const dashLink = page.getByRole('link', { name: 'Dashboard' })
    await expect(dashLink).not.toHaveClass(/bg-primary\/10/)
  })

  test('browser back navigation works', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Inventory' }).click()
    await expect(page).toHaveURL(/\/inventory/)
    await page.goBack()
    await expect(page).toHaveURL(/:\d+\/?$/)
  })

  test('browser forward navigation works', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Inventory' }).click()
    await page.goBack()
    await page.goForward()
    await expect(page).toHaveURL(/\/inventory/)
  })

  test('direct URL navigation works for all routes', async ({ authedPage: page }) => {
    const routes = ['/documents', '/review', '/ask', '/inventory', '/orders', '/upload', '/analytics', '/settings', '/cloud-brain']
    for (const route of routes) {
      await page.goto(route)
      // Should not redirect to login (we are authed)
      await expect(page).not.toHaveURL(/\/login/)
    }
  })

  test('unknown route redirects to dashboard', async ({ authedPage: page }) => {
    await page.goto('/nonexistent-page')
    await expect(page).toHaveURL(/:\d+\/?$/)
  })

  test('header has action buttons', async ({ authedPage: page }) => {
    // Header contains buttons (bell, menu toggle, etc.)
    await expect(page.locator('header').locator('button').first()).toBeAttached()
  })

  test('header shows Admin text', async ({ authedPage: page }) => {
    await expect(page.locator('header').getByText('Admin')).toBeVisible()
  })
})
