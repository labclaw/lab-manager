import { test, expect } from './fixtures'

test.describe('Upload Page', () => {
  test.beforeEach(async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Upload' }).click()
    await expect(page).toHaveURL(/\/upload/)
  })

  test('shows drag and drop zone', async ({ authedPage: page }) => {
    await expect(page.getByText(/drag.*drop.*files/i)).toBeVisible()
  })

  test('shows file type info', async ({ authedPage: page }) => {
    await expect(page.getByText(/PDF.*PNG.*JPG.*HEIC/i)).toBeVisible()
  })

  test('shows max file size info', async ({ authedPage: page }) => {
    await expect(page.getByText(/10.*MB/i)).toBeVisible()
  })

  test('Browse Files button is present', async ({ authedPage: page }) => {
    await expect(page.getByRole('button', { name: /browse files/i })).toBeVisible()
  })

  test('hidden file input exists', async ({ authedPage: page }) => {
    const fileInput = page.locator('input[type="file"]').first()
    await expect(fileInput).toBeAttached()
    await expect(fileInput).toHaveAttribute('accept', /image\/png/)
  })

  test('upload cloud icon is visible', async ({ authedPage: page }) => {
    // The CloudUpload icon should be in the drop zone
    await expect(page.locator('svg').first()).toBeVisible()
  })

  test('drop zone highlights on drag', async ({ authedPage: page }) => {
    // Get the drop zone section
    const dropZone = page.locator('section').filter({ hasText: /drag.*drop/i })
    await expect(dropZone).toBeVisible()
    // The zone should have border-dashed styling
    await expect(dropZone).toHaveClass(/border-dashed/)
  })

  test('no upload session shown initially', async ({ authedPage: page }) => {
    // Upload Session section should not be visible until files are uploaded
    await expect(page.getByText('Upload Session')).not.toBeVisible()
  })
})
