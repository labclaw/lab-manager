import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { renderWithProviders } from '@/test/utils'
import { DashboardPage } from '@/pages/DashboardPage'

const onError = vi.fn()

function renderDashboard() {
  return renderWithProviders(<DashboardPage onError={onError} />)
}

describe('DashboardPage', () => {
  describe('AC1: Dashboard loads stats from GET /analytics/dashboard', () => {
    it('fetches and renders dashboard stats', async () => {
      renderDashboard()
      await waitFor(() => {
        expect(screen.getByText('42')).toBeInTheDocument()
      })
    })
  })

  describe('AC2: Shows total documents, orders, inventory, vendors counts', () => {
    it('displays total documents count', async () => {
      renderDashboard()
      await waitFor(() => {
        expect(screen.getByText('42')).toBeInTheDocument()
      })
      expect(screen.getByText('Total Documents')).toBeInTheDocument()
    })

    it('displays approved documents count', async () => {
      renderDashboard()
      await waitFor(() => {
        expect(screen.getByText('30')).toBeInTheDocument()
      })
      expect(screen.getByText('Approved')).toBeInTheDocument()
    })

    it('displays needs review count', async () => {
      renderDashboard()
      await waitFor(() => {
        expect(screen.getByText('5')).toBeInTheDocument()
      })
      expect(screen.getByText('Needs Review')).toBeInTheDocument()
    })

    it('displays orders created count', async () => {
      renderDashboard()
      await waitFor(() => {
        expect(screen.getByText('18')).toBeInTheDocument()
      })
      expect(screen.getByText('Orders Created')).toBeInTheDocument()
    })

    it('displays vendors count', async () => {
      renderDashboard()
      await waitFor(() => {
        expect(screen.getByText('8')).toBeInTheDocument()
      })
      expect(screen.getByText('Vendors')).toBeInTheDocument()
    })

    it('displays inventory line items reconciled', async () => {
      renderDashboard()
      await waitFor(() => {
        expect(screen.getByText('120 line items reconciled')).toBeInTheDocument()
      })
    })

    it('displays approval percentage', async () => {
      renderDashboard()
      // 30/42 = 71%
      await waitFor(() => {
        expect(screen.getByText('71% automation accuracy')).toBeInTheDocument()
      })
    })
  })

  describe('AC3: Shows low stock alerts from GET /inventory/low-stock', () => {
    it('displays critical inventory alert with low stock count', async () => {
      renderDashboard()
      await waitFor(() => {
        expect(screen.getByText('Critical Inventory Level')).toBeInTheDocument()
      })
      // mockLowStock has 1 item — text is split across JSX nodes
      await waitFor(() => {
        expect(
          screen.getByText(/1 item is below minimum stock thresholds/),
        ).toBeInTheDocument()
      })
    })

    it('pluralizes when multiple items are low stock', async () => {
      server.use(
        http.get('/api/v1/inventory/low-stock', () =>
          HttpResponse.json({
            items: [
              { id: 3, product_name: 'A', quantity: 1 },
              { id: 4, product_name: 'B', quantity: 0 },
            ],
            total: 2,
            page: 1,
            page_size: 20,
            pages: 1,
          }),
        ),
      )
      renderDashboard()
      await waitFor(() => {
        expect(
          screen.getByText(/2 items are below minimum stock thresholds/),
        ).toBeInTheDocument()
      })
    })
  })

  describe('AC4: Shows expiring items from GET /inventory/expiring', () => {
    it('displays expiring reagents alert with count', async () => {
      renderDashboard()
      await waitFor(() => {
        expect(screen.getByText('Expiring Reagents')).toBeInTheDocument()
      })
      // mockExpiring has 1 item — text is split across JSX nodes
      await waitFor(() => {
        expect(
          screen.getByText(/1 vital item will expire within 30 days/),
        ).toBeInTheDocument()
      })
    })

    it('pluralizes when multiple items are expiring', async () => {
      server.use(
        http.get('/api/v1/inventory/expiring', () =>
          HttpResponse.json({
            items: [
              { id: 2, product_name: 'A', expiry_date: '2026-03-22' },
              { id: 5, product_name: 'B', expiry_date: '2026-03-25' },
              { id: 6, product_name: 'C', expiry_date: '2026-03-28' },
            ],
            total: 3,
            page: 1,
            page_size: 20,
            pages: 1,
          }),
        ),
      )
      renderDashboard()
      await waitFor(() => {
        expect(
          screen.getByText(/3 vital items will expire within 30 days/),
        ).toBeInTheDocument()
      })
    })
  })

  describe('AC5: Shows recent vendors list', () => {
    it('displays vendor names in Top Lab Vendors chart', async () => {
      renderDashboard()
      // mockVendors: Fisher Scientific (12 orders), Sigma-Aldrich (8 orders)
      await waitFor(() => {
        expect(screen.getByText('Fisher Scientific')).toBeInTheDocument()
      })
      expect(screen.getByText('Sigma-Aldrich')).toBeInTheDocument()
      expect(screen.getByText('Top Lab Vendors')).toBeInTheDocument()
    })

    it('shows vendor order counts with percentages', async () => {
      renderDashboard()
      // total orders = 8 + 12 = 20; Fisher = 12/20 = 60%, Sigma = 8/20 = 40%
      await waitFor(() => {
        expect(screen.getByText('12 orders (60%)')).toBeInTheDocument()
      })
      expect(screen.getByText('8 orders (40%)')).toBeInTheDocument()
    })

    it('shows "No vendor data yet" when vendor list is empty', async () => {
      server.use(
        http.get('/api/v1/vendors', () =>
          HttpResponse.json({
            items: [],
            total: 0,
            page: 1,
            page_size: 20,
            pages: 0,
          }),
        ),
      )
      renderDashboard()
      await waitFor(() => {
        expect(screen.getByText('No vendor data yet')).toBeInTheDocument()
      })
    })
  })

  describe('AC8: Loading state shows spinner', () => {
    it('shows loading indicator while data loads', () => {
      // Override to delay response
      server.use(
        http.get('/api/v1/analytics/dashboard', async () => {
          await new Promise(() => {
            /* never resolves */
          })
          return HttpResponse.json({})
        }),
      )
      renderDashboard()
      // While stats are loading, show loading text
      expect(screen.getByText('Loading dashboard...')).toBeInTheDocument()
    })

    it('shows dashboard content after data loads', async () => {
      renderDashboard()
      // After data loads, quick actions appear
      expect(await screen.findByText('Upload Document')).toBeInTheDocument()
      expect(screen.getByText('New Order')).toBeInTheDocument()
    })
  })
})
