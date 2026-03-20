import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { renderWithProviders } from '@/test/utils'
import { LoginPage } from '@/pages/LoginPage'

// Prevent window.location.reload from throwing in jsdom
beforeEach(() => {
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { ...window.location, reload: vi.fn() },
  })
})

describe('LoginPage', () => {
  describe('AC1: Shows email and password fields', () => {
    it('renders an email input field', () => {
      renderWithProviders(<LoginPage />)
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/email/i)).toHaveAttribute('type', 'email')
    })

    it('renders a password input field', () => {
      renderWithProviders(<LoginPage />)
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/password/i)).toHaveAttribute('type', 'password')
    })

    it('renders a submit button', () => {
      renderWithProviders(<LoginPage />)
      expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
    })
  })

  describe('AC2: Submit calls POST /auth/login', () => {
    it('sends email and password to login endpoint', async () => {
      const user = userEvent.setup()
      let capturedBody: Record<string, string> | null = null

      server.use(
        http.post('/api/auth/login', async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, string>
          return HttpResponse.json({ status: 'ok', user: { id: 1, name: 'Test' } })
        }),
      )

      renderWithProviders(<LoginPage />)
      await user.type(screen.getByLabelText(/email/i), 'user@lab.com')
      await user.type(screen.getByLabelText(/password/i), 'secret123')
      await user.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => {
        expect(capturedBody).toEqual({ email: 'user@lab.com', password: 'secret123' })
      })
    })
  })

  describe('AC3: Error message on failed login', () => {
    it('displays error when login fails', async () => {
      const user = userEvent.setup()

      server.use(
        http.post('/api/auth/login', () =>
          HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 }),
        ),
      )

      renderWithProviders(<LoginPage />)
      await user.type(screen.getByLabelText(/email/i), 'bad@lab.com')
      await user.type(screen.getByLabelText(/password/i), 'wrong')
      await user.click(screen.getByRole('button', { name: /sign in/i }))

      await waitFor(() => {
        expect(screen.getByText(/unauthorized/i)).toBeInTheDocument()
      })
    })
  })

  describe('AC4: Loading state during submission', () => {
    it('shows loading indicator while request is in flight', async () => {
      const user = userEvent.setup()

      // Use a deferred response to control timing
      let resolveLogin!: () => void
      const loginPromise = new Promise<void>((resolve) => {
        resolveLogin = resolve
      })

      server.use(
        http.post('/api/auth/login', async () => {
          await loginPromise
          return HttpResponse.json({ status: 'ok', user: { id: 1, name: 'Test' } })
        }),
      )

      renderWithProviders(<LoginPage />)
      await user.type(screen.getByLabelText(/email/i), 'user@lab.com')
      await user.type(screen.getByLabelText(/password/i), 'secret123')
      await user.click(screen.getByRole('button', { name: /sign in/i }))

      // While loading, button text changes
      expect(screen.getByText(/signing in/i)).toBeInTheDocument()
      expect(screen.getByRole('button')).toBeDisabled()

      // Resolve and verify loading state is gone
      resolveLogin()
      await waitFor(() => {
        expect(screen.queryByText(/signing in/i)).not.toBeInTheDocument()
      })
    })
  })
})
