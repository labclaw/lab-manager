import { test, expect } from './fixtures'

test.describe('Authentication', () => {
  test('shows login page when not authenticated', async ({ page }) => {
    // Mock setup status OK, but auth returns 401
    await page.route('**/api/v1/setup/status', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ needs_setup: false }) }),
    )
    await page.route('**/api/v1/auth/me', (route) =>
      route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'Unauthorized' }) }),
    )
    await page.route('**/api/v1/alerts', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) }),
    )
    await page.route('**/api/v1/alerts/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) }),
    )

    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'LabClaw' })).toBeVisible()
    await expect(page.getByLabel('Email')).toBeVisible()
    await expect(page.getByLabel('Password')).toBeVisible()
    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible()
  })

  test('login form has email and password fields', async ({ page }) => {
    await page.route('**/api/v1/setup/status', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ needs_setup: false }) }),
    )
    await page.route('**/api/v1/auth/me', (route) =>
      route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'Unauthorized' }) }),
    )
    await page.route('**/api/v1/alerts', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) }),
    )
    await page.route('**/api/v1/alerts/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) }),
    )

    await page.goto('/')
    const emailInput = page.getByLabel('Email')
    const passwordInput = page.getByLabel('Password')

    await expect(emailInput).toHaveAttribute('type', 'email')
    await expect(emailInput).toHaveAttribute('required', '')
    await expect(passwordInput).toHaveAttribute('type', 'password')
    await expect(passwordInput).toHaveAttribute('required', '')
  })

  test('login with invalid credentials shows error', async ({ page }) => {
    await page.route('**/api/v1/setup/status', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ needs_setup: false }) }),
    )
    await page.route('**/api/v1/auth/me', (route) =>
      route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'Unauthorized' }) }),
    )
    await page.route('**/api/v1/auth/login', (route) =>
      route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'Invalid credentials' }) }),
    )
    await page.route('**/api/v1/alerts', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) }),
    )
    await page.route('**/api/v1/alerts/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) }),
    )

    await page.goto('/')
    await page.getByLabel('Email').fill('wrong@test.com')
    await page.getByLabel('Password').fill('badpassword')
    await page.getByRole('button', { name: /sign in/i }).click()

    // Error message should appear
    await expect(page.getByText(/unauthorized|invalid/i)).toBeVisible()
  })

  test('shows setup page when needs_setup is true', async ({ page }) => {
    await page.route('**/api/v1/setup/status', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ needs_setup: true }) }),
    )

    await page.goto('/')
    await expect(page.getByText('Welcome to LabClaw')).toBeVisible()
    await expect(page.getByLabel(/your name/i)).toBeVisible()
    await expect(page.getByLabel('Email')).toBeVisible()
    await expect(page.getByLabel('Password')).toBeVisible()
  })

  test('security badge visible on login page', async ({ page }) => {
    await page.route('**/api/v1/setup/status', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ needs_setup: false }) }),
    )
    await page.route('**/api/v1/auth/me', (route) =>
      route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'Unauthorized' }) }),
    )
    await page.route('**/api/v1/alerts', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) }),
    )
    await page.route('**/api/v1/alerts/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) }),
    )

    await page.goto('/')
    await expect(page.getByText('Secure Environment')).toBeVisible()
  })
})
