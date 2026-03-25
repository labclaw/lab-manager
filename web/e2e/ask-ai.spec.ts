import { test, expect } from './fixtures'

test.describe('Ask AI Page', () => {
  test.beforeEach(async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Ask AI' }).click()
    await expect(page).toHaveURL(/\/ask/)
  })

  test('shows suggested prompts', async ({ authedPage: page }) => {
    await expect(page.getByText(/what orders were received/i)).toBeVisible()
    await expect(page.getByText(/which vendors have the most/i)).toBeVisible()
    await expect(page.getByText(/how many products/i)).toBeVisible()
    await expect(page.getByText(/which items are expiring/i)).toBeVisible()
  })

  test('has message input area', async ({ authedPage: page }) => {
    // The ask page has a textarea or input for questions
    const input = page.getByPlaceholder(/ask|question|type/i)
    await expect(input).toBeVisible()
  })

  test('has send button', async ({ authedPage: page }) => {
    // There should be a send/submit button
    const sendBtn = page.locator('button').filter({ has: page.locator('svg') }).last()
    await expect(sendBtn).toBeVisible()
  })

  test('clicking suggested prompt populates input', async ({ authedPage: page }) => {
    await page.getByText(/what orders were received/i).click()
    // After clicking a prompt, either the message is sent or input is populated
    // The app sends the question directly on click
    await page.waitForTimeout(1000)
    // Should see an answer or loading state
    await expect(page.getByText(/based on the lab data|loading|processing/i).or(page.locator('[class*="animate"]'))).toBeVisible()
  })

  test('new chat button is available', async ({ authedPage: page }) => {
    // The "New Chat" or "+" button should be visible
    await expect(
      page.getByRole('button', { name: /new chat/i })
        .or(page.getByTitle(/new chat/i))
        .or(page.locator('button').filter({ hasText: /new/i }))
    ).toBeVisible()
  })

  test('page layout has conversation area', async ({ authedPage: page }) => {
    // The ask page has the main conversation view area
    // It should show the suggested prompts area or a chat input at minimum
    await expect(page.getByPlaceholder(/ask|question|type/i)).toBeVisible()
  })
})
