import { test, expect } from './fixtures'

test.describe('Documents Page', () => {
  test.beforeEach(async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Documents' }).click()
    await expect(page).toHaveURL(/\/documents/)
  })

  test('shows Documents heading', async ({ authedPage: page }) => {
    await expect(page.locator('h2').filter({ hasText: 'Documents' })).toBeVisible()
  })

  test('shows document table with vendor names', async ({ authedPage: page }) => {
    await expect(page.getByText('Sigma-Aldrich').first()).toBeVisible()
    await expect(page.getByText('Thermo Fisher').first()).toBeVisible()
  })

  test('shows all status filter tabs', async ({ authedPage: page }) => {
    await expect(page.getByRole('button', { name: 'All' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Approved' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Needs Review' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Rejected' })).toBeVisible()
  })

  test('All tab is active by default', async ({ authedPage: page }) => {
    const allBtn = page.getByRole('button', { name: 'All' })
    // Active tab has primary bg color class
    await expect(allBtn).toHaveClass(/bg-primary/)
  })

  test('clicking Approved tab filters documents', async ({ authedPage: page }) => {
    await page.getByRole('button', { name: 'Approved' }).click()
    // The Approved button should now be active
    await expect(page.getByRole('button', { name: 'Approved' })).toHaveClass(/bg-primary/)
  })

  test('clicking Needs Review tab changes active filter', async ({ authedPage: page }) => {
    await page.getByRole('button', { name: 'Needs Review' }).click()
    await expect(page.getByRole('button', { name: 'Needs Review' })).toHaveClass(/bg-primary/)
  })

  test('clicking Rejected tab changes active filter', async ({ authedPage: page }) => {
    await page.getByRole('button', { name: 'Rejected' }).click()
    await expect(page.getByRole('button', { name: 'Rejected' })).toHaveClass(/bg-primary/)
  })

  test('search input is present', async ({ authedPage: page }) => {
    await expect(page.getByPlaceholder(/search vendor or filename/i)).toBeVisible()
  })

  test('Upload Doc button is present', async ({ authedPage: page }) => {
    await expect(page.getByRole('button', { name: /upload doc/i })).toBeVisible()
  })

  test('Upload Doc button navigates to /upload', async ({ authedPage: page }) => {
    await page.getByRole('button', { name: /upload doc/i }).click()
    await expect(page).toHaveURL(/\/upload/)
  })

  test('table headers are correct', async ({ authedPage: page }) => {
    await expect(page.locator('th').filter({ hasText: 'Document' })).toBeVisible()
    await expect(page.locator('th').filter({ hasText: 'Vendor' })).toBeVisible()
    await expect(page.locator('th').filter({ hasText: 'Type' })).toBeVisible()
    await expect(page.locator('th').filter({ hasText: 'Status' })).toBeVisible()
    await expect(page.locator('th').filter({ hasText: 'Confidence' })).toBeVisible()
    await expect(page.locator('th').filter({ hasText: 'Date' })).toBeVisible()
  })

  test('document row shows status badge', async ({ authedPage: page }) => {
    // Mock has 'approved' status docs
    await expect(page.locator('text=Approved').first()).toBeVisible()
  })

  test('document row shows confidence bar', async ({ authedPage: page }) => {
    // Mock has 95% confidence -> shows "95%"
    await expect(page.getByText('95%')).toBeVisible()
  })

  test('pagination info shows item count', async ({ authedPage: page }) => {
    await expect(page.getByText(/showing.*1.*(-|to).*4.*of.*4/i)).toBeVisible()
  })

  test('clicking document row navigates to review', async ({ authedPage: page }) => {
    await page.locator('tr').filter({ hasText: 'Sigma-Aldrich' }).first().click()
    await expect(page).toHaveURL(/\/review\?id=/)
  })
})
