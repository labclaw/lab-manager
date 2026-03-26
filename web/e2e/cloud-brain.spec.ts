import { test, expect } from './fixtures'

test.describe('Cloud Brain Page', () => {
  test.beforeEach(async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Cloud Brain' }).click()
    await expect(page).toHaveURL(/\/cloud-brain/)
  })

  test('shows ToolUniverse skill card', async ({ authedPage: page }) => {
    await expect(page.locator('text=ToolUniverse').first()).toBeVisible()
  })

  test('shows K-Dense AI skill card', async ({ authedPage: page }) => {
    await expect(page.locator('text=K-Dense AI').first()).toBeVisible()
  })

  test('shows Biomni skill card', async ({ authedPage: page }) => {
    await expect(page.locator('text=Biomni').first()).toBeVisible()
  })

  test('skill cards show tool counts', async ({ authedPage: page }) => {
    // ToolUniverse has 2,124 tools -- may be rendered as "2,124" or "2124"
    await expect(page.getByText(/2,?124/)).toBeVisible()
  })

  test('skill cards show description text', async ({ authedPage: page }) => {
    // Description contains "scientific tools" or "databases"
    await expect(page.getByText(/databases/).first()).toBeVisible()
  })

  test('skill cards show example queries', async ({ authedPage: page }) => {
    // Examples like "Look up protein" -- may be truncated
    await expect(page.getByText(/protein|PubChem|clinical trials|UniProt/i).first()).toBeVisible()
  })

  test('skill cards show source references', async ({ authedPage: page }) => {
    await expect(page.getByText(/mims-harvard/).first()).toBeVisible()
  })

  test('skill cards show category tags', async ({ authedPage: page }) => {
    await expect(page.getByText('Genomics')).toBeVisible()
  })

  test('query input area exists', async ({ authedPage: page }) => {
    const input = page.getByRole('textbox', { name: /search ai skills/i })
    await expect(input).toBeVisible()
  })

  test('page shows Cloud Brain heading area', async ({ authedPage: page }) => {
    await expect(page.getByText('Cloud Brain').first()).toBeVisible()
  })

  test('Available AI Skills section visible', async ({ authedPage: page }) => {
    await expect(page.getByText(/available ai skills/i)).toBeVisible()
  })
})
