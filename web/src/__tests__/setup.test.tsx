import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { renderWithProviders } from '@/test/utils'
import { SetupPage } from '@/pages/SetupPage'

describe('SetupPage', () => {
  const onComplete = vi.fn()

  beforeEach(() => {
    onComplete.mockClear()
  })

  describe('AC1: Shows admin name, email, password fields', () => {
    it('renders a name input field', () => {
      renderWithProviders(<SetupPage onComplete={onComplete} />)
      expect(screen.getByLabelText(/your name/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/your name/i)).toHaveAttribute('type', 'text')
    })

    it('renders an email input field', () => {
      renderWithProviders(<SetupPage onComplete={onComplete} />)
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/email/i)).toHaveAttribute('type', 'email')
    })

    it('renders a password input field', () => {
      renderWithProviders(<SetupPage onComplete={onComplete} />)
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/password/i)).toHaveAttribute('type', 'password')
    })

    it('renders a submit button', () => {
      renderWithProviders(<SetupPage onComplete={onComplete} />)
      expect(screen.getByRole('button', { name: /create admin account/i })).toBeInTheDocument()
    })
  })

  describe('AC2: Submit calls POST /setup/complete', () => {
    it('sends admin_name, admin_email, admin_password to setup endpoint', async () => {
      const user = userEvent.setup()
      let capturedBody: Record<string, string> | null = null

      server.use(
        http.post('/api/setup/complete', async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, string>
          return HttpResponse.json({ status: 'ok' })
        }),
      )

      renderWithProviders(<SetupPage onComplete={onComplete} />)
      await user.type(screen.getByLabelText(/your name/i), 'Dr. Admin')
      await user.type(screen.getByLabelText(/email/i), 'admin@lab.com')
      await user.type(screen.getByLabelText(/password/i), 'securepass')
      await user.click(screen.getByRole('button', { name: /create admin account/i }))

      await waitFor(() => {
        expect(capturedBody).toEqual({
          admin_name: 'Dr. Admin',
          admin_email: 'admin@lab.com',
          admin_password: 'securepass',
        })
      })
    })
  })

  describe('AC3: Validation (required fields)', () => {
    it('marks all fields as required', () => {
      renderWithProviders(<SetupPage onComplete={onComplete} />)
      expect(screen.getByLabelText(/your name/i)).toBeRequired()
      expect(screen.getByLabelText(/email/i)).toBeRequired()
      expect(screen.getByLabelText(/password/i)).toBeRequired()
    })
  })

  describe('AC4: Success callback fires onComplete', () => {
    it('calls onComplete after successful setup', async () => {
      const user = userEvent.setup()

      server.use(
        http.post('/api/setup/complete', () =>
          HttpResponse.json({ status: 'ok' }),
        ),
      )

      renderWithProviders(<SetupPage onComplete={onComplete} />)
      await user.type(screen.getByLabelText(/your name/i), 'Dr. Admin')
      await user.type(screen.getByLabelText(/email/i), 'admin@lab.com')
      await user.type(screen.getByLabelText(/password/i), 'securepass')
      await user.click(screen.getByRole('button', { name: /create admin account/i }))

      await waitFor(() => {
        expect(onComplete).toHaveBeenCalledTimes(1)
      })
    })

    it('shows error and does not call onComplete on failure', async () => {
      const user = userEvent.setup()

      server.use(
        http.post('/api/setup/complete', () =>
          HttpResponse.json({ detail: 'Email already registered' }, { status: 400 }),
        ),
      )

      renderWithProviders(<SetupPage onComplete={onComplete} />)
      await user.type(screen.getByLabelText(/your name/i), 'Dr. Admin')
      await user.type(screen.getByLabelText(/email/i), 'admin@lab.com')
      await user.type(screen.getByLabelText(/password/i), 'securepass')
      await user.click(screen.getByRole('button', { name: /create admin account/i }))

      await waitFor(() => {
        expect(screen.getByText(/email already registered/i)).toBeInTheDocument()
      })
      expect(onComplete).not.toHaveBeenCalled()
    })
  })
})
