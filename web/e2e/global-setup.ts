import { test as setup } from '@playwright/test'

setup('global setup', async () => {
  // No-op: API mocking is done per-test via fixtures.
  // This file exists to satisfy the Playwright project config.
})
