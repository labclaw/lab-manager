import { test, expect } from './fixtures'

test.describe('Settings Page', () => {
  test.beforeEach(async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Settings' }).click()
    await expect(page).toHaveURL(/\/settings/)
  })

  test('shows Lab Profile section', async ({ authedPage: page }) => {
    await expect(page.getByRole('heading', { name: 'Lab Profile' })).toBeVisible()
  })

  test('shows lab name from config', async ({ authedPage: page }) => {
    // Mock returns lab_name: 'Shen Lab' — shown in an input field
    await expect(page.locator('input[value="Shen Lab"]')).toBeVisible()
  })

  test('shows lab subtitle from config', async ({ authedPage: page }) => {
    await expect(page.locator('input[value="MGH Neuroscience"]')).toBeVisible()
  })

  test('shows User Account section', async ({ authedPage: page }) => {
    await expect(page.getByText('User Account')).toBeVisible()
  })

  test('shows user name', async ({ authedPage: page }) => {
    // The user name "Admin" is shown in an input field
    const adminInputs = page.locator('input[value="Admin"]')
    await expect(adminInputs.first()).toBeVisible()
  })

  test('shows Change Password section', async ({ authedPage: page }) => {
    await expect(page.getByText('Change Password')).toBeVisible()
  })

  test('shows AI Configuration section', async ({ authedPage: page }) => {
    await expect(page.getByText('AI Configuration')).toBeVisible()
  })

  test('shows OCR Model dropdown', async ({ authedPage: page }) => {
    await expect(page.getByLabel('OCR Model')).toBeVisible()
  })

  test('shows Extraction Model dropdown', async ({ authedPage: page }) => {
    await expect(page.getByLabel('Extraction Model')).toBeVisible()
  })

  test('shows RAG Model dropdown', async ({ authedPage: page }) => {
    await expect(page.getByLabel('RAG Model')).toBeVisible()
  })

  test('shows Notifications section', async ({ authedPage: page }) => {
    await expect(page.getByRole('heading', { name: 'Notifications' })).toBeVisible()
  })

  test('shows notification toggle options', async ({ authedPage: page }) => {
    await expect(page.getByText('Email notifications')).toBeVisible()
    await expect(page.getByText('Low stock alerts')).toBeVisible()
    await expect(page.getByText('Expiring reagents alerts')).toBeVisible()
  })

  test('shows Data Management section', async ({ authedPage: page }) => {
    await expect(page.getByText(/data management|data.*export/i)).toBeVisible()
  })

  test('shows Coming Soon badges', async ({ authedPage: page }) => {
    const badges = page.getByText('Coming Soon')
    await expect(badges.first()).toBeVisible()
  })

  test('Lab Profile fields are disabled', async ({ authedPage: page }) => {
    const labNameInput = page.locator('input[value="Shen Lab"]')
    await expect(labNameInput).toBeDisabled()
  })
})
