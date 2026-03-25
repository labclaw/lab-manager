import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { renderWithProviders } from '@/test/utils'
import { OrdersPage } from '@/pages/OrdersPage'

const onError = vi.fn()

// Mock data: order 1 = received (past tab), order 2 = pending (active tab)
// Active tab is default; it filters out received/cancelled

describe('OrdersPage', () => {
  describe('AC1: Orders list loads from GET /orders with pagination', () => {
    it('renders orders from the API on the active tab', async () => {
      renderWithProviders(<OrdersPage onError={onError} />)

      // Pending order (id=2) should appear on active tab
      await waitFor(() => {
        expect(screen.getByText('Order #PO-2026-002')).toBeInTheDocument()
      })
      expect(screen.getByText('Fisher Scientific')).toBeInTheDocument()
    })

    it('shows total count in header', async () => {
      renderWithProviders(<OrdersPage onError={onError} />)

      // Header text: "X active, Y completed across Z total orders."
      await waitFor(() => {
        expect(
          screen.getByText(/1 active, 1 completed across 2 total orders/),
        ).toBeInTheDocument()
      })
    })

    it('shows received orders on the past tab', async () => {
      const user = userEvent.setup()
      renderWithProviders(<OrdersPage onError={onError} />)

      // Wait for data to load
      await waitFor(() => {
        expect(screen.getByText('Order #PO-2026-002')).toBeInTheDocument()
      })

      // Switch to Past Orders tab
      await user.click(screen.getByText('Past Orders'))

      await waitFor(() => {
        expect(screen.getByText('Order #PO-2026-001')).toBeInTheDocument()
      })
      expect(screen.getByText('Sigma-Aldrich')).toBeInTheDocument()
    })
  })

  describe('AC2: Shows vendor, PO number, status, amount, item count', () => {
    it('shows vendor name for the active order', async () => {
      renderWithProviders(<OrdersPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText(/Fisher Scientific/)).toBeInTheDocument()
      })
    })

    it('shows PO number in the order card', async () => {
      renderWithProviders(<OrdersPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Order #PO-2026-002')).toBeInTheDocument()
      })
    })

    it('shows status badge on the featured order', async () => {
      renderWithProviders(<OrdersPage onError={onError} />)

      // formatEnum converts 'pending' -> 'Pending'
      await waitFor(() => {
        expect(screen.getByText('Pending')).toBeInTheDocument()
      })
    })

    it('shows total monthly spend', async () => {
      renderWithProviders(<OrdersPage onError={onError} />)

      // Total = 450 + 320 = 770
      await waitFor(() => {
        expect(screen.getByText('$770.00')).toBeInTheDocument()
      })
    })
  })

  describe('AC3: Status badges (pending=Pending Approval, etc.)', () => {
    it('shows Pending Approval badge for pending orders in secondary cards', async () => {
      // Need multiple active orders so pending one appears as secondary card
      // Featured picks shipped/ordered first; pending falls to secondary
      server.use(
        http.get('/api/v1/orders', () => {
          return HttpResponse.json({
            items: [
              { id: 10, vendor_name: 'VWR', po_number: 'PO-SHIP-001', status: 'shipped', total_amount: 200.00, item_count: 2 },
              { id: 11, vendor_name: 'Bio-Rad', po_number: 'PO-PEND-001', status: 'pending', total_amount: 150.00, item_count: 1 },
            ],
            total: 2, page: 1, page_size: 20, pages: 1,
          })
        }),
      )

      renderWithProviders(<OrdersPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Pending Approval')).toBeInTheDocument()
      })
    })

    it('shows received status on past tab', async () => {
      const user = userEvent.setup()
      renderWithProviders(<OrdersPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Order #PO-2026-002')).toBeInTheDocument()
      })

      await user.click(screen.getByText('Past Orders'))

      // formatEnum converts 'received' -> 'Received' (may appear in badge + tracker)
      await waitFor(() => {
        expect(screen.getAllByText('Received').length).toBeGreaterThanOrEqual(1)
      })
    })

    it('shows shipped status badge with progress tracker for shipped orders', async () => {
      server.use(
        http.get('/api/v1/orders', () => {
          return HttpResponse.json({
            items: [
              { id: 10, vendor_name: 'VWR', po_number: 'PO-SHIP-001', status: 'shipped', total_amount: 100.00, item_count: 1 },
            ],
            total: 1, page: 1, page_size: 20, pages: 1,
          })
        }),
      )

      renderWithProviders(<OrdersPage onError={onError} />)

      // formatEnum converts 'shipped' -> 'Shipped' (appears in badge + tracker)
      await waitFor(() => {
        expect(screen.getAllByText('Shipped').length).toBeGreaterThanOrEqual(1)
      })
      // Progress tracker steps should be visible
      expect(screen.getAllByText('Ordered').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText(/Out for Delivery/).length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('Received').length).toBeGreaterThanOrEqual(1)
    })
  })

  describe('AC4: Loading state', () => {
    it('shows spinner while loading', () => {
      server.use(
        http.get('/api/v1/orders', async () => {
          await new Promise((resolve) => setTimeout(resolve, 500))
          return HttpResponse.json({
            items: [], total: 0, page: 1, page_size: 20, pages: 0,
          })
        }),
      )

      renderWithProviders(<OrdersPage onError={onError} />)

      const spinner = document.querySelector('.animate-spin')
      expect(spinner).toBeInTheDocument()
    })
  })

  describe('AC5: Empty state when no orders', () => {
    it('shows empty state message when no active orders', async () => {
      server.use(
        http.get('/api/v1/orders', () => {
          return HttpResponse.json({
            items: [], total: 0, page: 1, page_size: 20, pages: 0,
          })
        }),
      )

      renderWithProviders(<OrdersPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('No orders found')).toBeInTheDocument()
      })
      expect(screen.getByText('No active orders right now.')).toBeInTheDocument()
    })

    it('shows appropriate message on empty past orders tab', async () => {
      const user = userEvent.setup()

      server.use(
        http.get('/api/v1/orders', () => {
          return HttpResponse.json({
            items: [], total: 0, page: 1, page_size: 20, pages: 0,
          })
        }),
      )

      renderWithProviders(<OrdersPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('No orders found')).toBeInTheDocument()
      })

      await user.click(screen.getByText('Past Orders'))

      await waitFor(() => {
        expect(screen.getByText('No past orders yet.')).toBeInTheDocument()
      })
    })

    it('shows appropriate message on empty drafts tab', async () => {
      const user = userEvent.setup()

      server.use(
        http.get('/api/v1/orders', () => {
          return HttpResponse.json({
            items: [], total: 0, page: 1, page_size: 20, pages: 0,
          })
        }),
      )

      renderWithProviders(<OrdersPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('No orders found')).toBeInTheDocument()
      })

      await user.click(screen.getByText('Drafts'))

      await waitFor(() => {
        expect(screen.getByText('No drafts saved.')).toBeInTheDocument()
      })
    })
  })

  describe('Tabs navigation', () => {
    it('renders all three tabs', async () => {
      renderWithProviders(<OrdersPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Active Orders')).toBeInTheDocument()
      })
      expect(screen.getByText('Past Orders')).toBeInTheDocument()
      expect(screen.getByText('Drafts')).toBeInTheDocument()
    })
  })
})
