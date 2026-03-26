import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { renderWithProviders } from '@/test/utils'
import { AlertsPage } from '@/pages/AlertsPage'

const onError = vi.fn()

function renderAlerts() {
  return renderWithProviders(<AlertsPage onError={onError} />, {
    initialEntries: ['/alerts'],
  })
}

describe('AlertsPage', () => {
  describe('AC1: Displays alerts from API', () => {
    it('renders alert messages from API', async () => {
      renderAlerts()

      await waitFor(() => {
        expect(screen.getByText('Sodium Chloride below reorder level')).toBeInTheDocument()
      })
      expect(screen.getByText('Ethanol 95% expires in 3 days')).toBeInTheDocument()
    })

    it('renders severity badges', async () => {
      renderAlerts()

      await waitFor(() => {
        expect(screen.getByText('Warning')).toBeInTheDocument()
      })
      expect(screen.getByText('Critical')).toBeInTheDocument()
    })

    it('renders type badges', async () => {
      renderAlerts()

      await waitFor(() => {
        // Type badges appear in both alert cards and the dropdown; use getAllByText
        expect(screen.getAllByText('Low Stock').length).toBeGreaterThanOrEqual(1)
      })
      expect(screen.getAllByText('Expiring Soon').length).toBeGreaterThanOrEqual(1)
    })

    it('shows unacknowledged count from summary', async () => {
      renderAlerts()

      await waitFor(() => {
        expect(screen.getByText('10 unacknowledged')).toBeInTheDocument()
      })
    })
  })

  describe('AC2: Acknowledge and resolve actions', () => {
    it('shows Acknowledge button for unacknowledged alerts', async () => {
      renderAlerts()

      await waitFor(() => {
        const ackBtns = screen.getAllByRole('button', { name: /Acknowledge/i })
        expect(ackBtns.length).toBeGreaterThanOrEqual(1)
      })
    })

    it('shows Resolve button for unresolved alerts', async () => {
      renderAlerts()

      await waitFor(() => {
        const resolveBtns = screen.getAllByRole('button', { name: /Resolve/i })
        expect(resolveBtns.length).toBeGreaterThanOrEqual(1)
      })
    })

    it('calls acknowledge endpoint when Acknowledge is clicked', async () => {
      const user = userEvent.setup()
      let called = false

      server.use(
        http.post('/api/v1/alerts/:id/acknowledge', () => {
          called = true
          return HttpResponse.json({ id: 1, is_acknowledged: true, is_resolved: false })
        }),
      )

      renderAlerts()

      // Wait for alert action buttons to render
      await waitFor(() => {
        expect(screen.getAllByTitle('Acknowledge').length).toBeGreaterThanOrEqual(1)
      })

      const ackBtns = screen.getAllByTitle('Acknowledge')
      await user.click(ackBtns[0])

      await waitFor(() => {
        expect(called).toBe(true)
      })
    })

    it('calls resolve endpoint when Resolve is clicked', async () => {
      const user = userEvent.setup()
      let called = false

      server.use(
        http.post('/api/v1/alerts/:id/resolve', () => {
          called = true
          return HttpResponse.json({ id: 1, is_acknowledged: true, is_resolved: true })
        }),
      )

      renderAlerts()

      // Wait for alert action buttons to render
      await waitFor(() => {
        expect(screen.getAllByTitle('Resolve').length).toBeGreaterThanOrEqual(1)
      })

      const resolveBtns = screen.getAllByTitle('Resolve')
      await user.click(resolveBtns[0])

      await waitFor(() => {
        expect(called).toBe(true)
      })
    })
  })

  describe('AC3: Status filters', () => {
    it('renders status filter buttons', async () => {
      renderAlerts()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^Active$/i })).toBeInTheDocument()
      })
      expect(screen.getByRole('button', { name: /^Acknowledged$/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /^Resolved$/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /^All$/i })).toBeInTheDocument()
    })

    it('renders type filter dropdown', async () => {
      renderAlerts()

      await waitFor(() => {
        const select = screen.getByRole('combobox')
        expect(select).toBeInTheDocument()
      })
    })
  })

  describe('AC4: Empty state', () => {
    it('shows empty state when no alerts', async () => {
      server.use(
        http.get('/api/v1/alerts', () =>
          HttpResponse.json({ items: [], total: 0, page: 1, page_size: 50, pages: 0 }),
        ),
      )

      renderAlerts()

      await waitFor(() => {
        expect(screen.getByText('No alerts')).toBeInTheDocument()
      })
    })

    it('shows contextual message for active filter in empty state', async () => {
      server.use(
        http.get('/api/v1/alerts', () =>
          HttpResponse.json({ items: [], total: 0, page: 1, page_size: 50, pages: 0 }),
        ),
      )

      renderAlerts()

      await waitFor(() => {
        expect(screen.getByText('No active alerts found.')).toBeInTheDocument()
      })
    })
  })
})
