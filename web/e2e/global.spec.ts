import { test, expect, mockAllAPIs, APP_ROUTES } from './fixtures'

test.describe('Global: Route Accessibility', () => {
  test('every authenticated route loads without error', async ({ page }) => {
    await mockAllAPIs(page)

    for (const route of APP_ROUTES) {
      const response = await page.goto(route.path)
      expect(response?.status(), `Route ${route.path} should return 200`).toBeLessThan(400)
    }
  })

  test('all routes render content (no blank pages)', async ({ page }) => {
    await mockAllAPIs(page)

    for (const route of APP_ROUTES) {
      await page.goto(route.path)
      // Wait for at least some meaningful content
      await page.waitForTimeout(1000)
      const bodyText = await page.locator('body').innerText()
      expect(bodyText.length, `Route ${route.path} should have content`).toBeGreaterThan(10)
    }
  })
})

test.describe('Global: Console Errors', () => {
  test('no unexpected console errors on any page', async ({ page }) => {
    await mockAllAPIs(page)

    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text()
        // Ignore expected non-critical errors
        if (text.includes('favicon')) return
        if (text.includes('Failed to load resource')) return
        if (text.includes('net::ERR')) return
        if (text.includes('404')) return
        // Ignore React dev warnings
        if (text.includes('Warning:')) return
        errors.push(`[${msg.location().url}] ${text}`)
      }
    })

    for (const route of APP_ROUTES) {
      await page.goto(route.path)
      await page.waitForTimeout(1000)
    }

    expect(errors, 'Should have no unexpected console errors').toHaveLength(0)
  })
})

test.describe('Global: Light Theme', () => {
  test('all pages use light theme (no dark mode)', async ({ page }) => {
    await mockAllAPIs(page)

    for (const route of APP_ROUTES) {
      await page.goto(route.path)
      await page.waitForTimeout(500)

      // Verify no dark class on html element
      const htmlClasses = await page.locator('html').getAttribute('class')
      expect(htmlClasses ?? '', `Route ${route.path} should not have dark mode`).not.toContain('dark')

      // Verify no dark mode in localStorage
      const darkMode = await page.evaluate(() => localStorage.getItem('darkMode'))
      expect(darkMode, `Route ${route.path} should not store darkMode`).toBeNull()
    }
  })
})

test.describe('Global: Responsiveness', () => {
  test('app renders at mobile viewport', async ({ page }) => {
    await mockAllAPIs(page)
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/')
    await page.waitForTimeout(1000)

    // Mobile menu toggle should be visible
    await expect(page.getByLabel(/open navigation menu/i)).toBeVisible()
  })

  test('mobile menu toggle opens sidebar', async ({ page }) => {
    await mockAllAPIs(page)
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/')
    await page.waitForTimeout(1000)

    await page.getByLabel(/open navigation menu/i).click()
    // After clicking, sidebar nav items should appear
    await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible()
  })
})

test.describe('Global: Search', () => {
  test('search bar is present in header on dashboard', async ({ page }) => {
    await mockAllAPIs(page)
    await page.goto('/')
    await page.waitForTimeout(1000)
    await expect(page.getByPlaceholder(/search products.*vendors.*orders/i)).toBeAttached()
  })

  test('search bar is hidden on Ask AI page', async ({ page }) => {
    await mockAllAPIs(page)
    await page.goto('/ask')
    await page.waitForTimeout(1000)
    // The search bar should be hidden (showSearch={false} for /ask)
    await expect(page.getByPlaceholder(/search products.*vendors.*orders/i)).not.toBeVisible()
  })
})
