import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { renderWithProviders } from '@/test/utils'
import { OrdersPage } from '@/pages/OrdersPage'

const onError = vi.fn()

describe('OrdersPage', () => {
  describe('AC1: Orders list loads from GET /orders with server-side status filtering', () => {
    it('renders active orders (default tab sends status_group=active)', async () => {
      renderWithProviders(<OrdersPage onError={onError} />)

      // Only pending order (id=2) should appear since active tab filters out received
      await waitFor(() => {
        expect(screen.getByText('Order #PO-2026-002')).toBeInTheDocument()
      })
      expect(screen.getByText('Fisher Scientific')).toBeInTheDocument()
      // received order should NOT appear on active tab
      expect(screen.queryByText('Order #PO-2026-001')).not.toBeInTheDocument()
    })

    it('passes status_group to API', async () => {
      let capturedUrl = ''
      server.use(
        http.get('/api/v1/orders', ({ request }) => {
          capturedUrl = request.url
          const url = new URL(request.url)
          const statusGroup = url.searchParams.get('status_group')
          if (statusGroup === 'active') {
            return HttpResponse.json({
              items: [{ id: 2, vendor_name: 'Fisher Scientific', po_number: 'PO-2026-002', status: 'pending', total_amount: 320.00, item_count: 2 }],
              total: 1, page: 1, page_size: 20, pages: 1,
            })
          }
          return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20, pages: 0 })
        }),
      )

      renderWithProviders(<OrdersPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Order #PO-2026-002')).toBeInTheDocument()
      })
      expect(capturedUrl).toContain('status_group=active')
    })

    it('shows received orders on the past tab with status_group=past', async () => {
      const user = userEvent.setup()
      renderWithProviders(<OrdersPage onError={onError} />)

      // Wait for active tab to load
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

  describe('AC2: Shows vendor, PO number, status, amount', () => {
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

    it('shows total spend (not monthly)', async () => {
      renderWithProviders(<OrdersPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Total Spend')).toBeInTheDocument()
      })
      // Only active orders visible: pending order = $320
      await waitFor(() => {
        expect(screen.getByText('$320.00')).toBeInTheDocument()
      })
    })
  })

  describe('AC3: No dead buttons or fake elements', () => {
    it('does not show disabled New Requisition button', async () => {
      renderWithProviders(<OrdersPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Order #PO-2026-002')).toBeInTheDocument()
      })

      expect(screen.queryByText('New Requisition')).not.toBeInTheDocument()
    })

    it('does not show View Invoice span', async () => {
      renderWithProviders(<OrdersPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Order #PO-2026-002')).toBeInTheDocument()
      })

      expect(screen.queryByText('View Invoice')).not.toBeInTheDocument()
    })

    it('does not show Track button', async () => {
      server.use(
        http.get('/api/v1/orders', ({ request }) => {
          const url = new URL(request.url)
          const statusGroup = url.searchParams.get('status_group')
          if (statusGroup === 'active') {
            return HttpResponse.json({
              items: [
                { id: 10, vendor_name: 'VWR', po_number: 'PO-SHIP-001', status: 'shipped', total_amount: 200.00, item_count: 2 },
                { id: 11, vendor_name: 'Bio-Rad', po_number: 'PO-PEND-001', status: 'pending', total_amount: 150.00, item_count: 1 },
                { id: 12, vendor_name: 'Fisher', po_number: 'PO-ORD-001', status: 'ordered', total_amount: 100.00, item_count: 1 },
              ],
              total: 3, page: 1, page_size: 20, pages: 1,
            })
          }
          return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20, pages: 0 })
        }),
      )

      renderWithProviders(<OrdersPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Order #PO-SHIP-001')).toBeInTheDocument()
      })

      expect(screen.queryByText('Track')).not.toBeInTheDocument()
      expect(screen.queryByText('Invoice')).not.toBeInTheDocument()
    })

    it('does not show hardcoded 25% progress bar', async () => {
      server.use(
        http.get('/api/v1/orders', ({ request }) => {
          const url = new URL(request.url)
          const statusGroup = url.searchParams.get('status_group')
          if (statusGroup === 'active') {
            return HttpResponse.json({
              items: [
                { id: 10, vendor_name: 'VWR', po_number: 'PO-SHIP-001', status: 'shipped', total_amount: 200.00, item_count: 2 },
                { id: 11, vendor_name: 'Bio-Rad', po_number: 'PO-ORD-001', status: 'ordered', total_amount: 150.00, item_count: 1 },
              ],
              total: 2, page: 1, page_size: 20, pages: 1,
            })
          }
          return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20, pages: 0 })
        }),
      )

      renderWithProviders(<OrdersPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Order #PO-SHIP-001')).toBeInTheDocument()
      })

      expect(screen.queryByText('25% Progress')).not.toBeInTheDocument()
    })
  })

  describe('AC4: View Details expands inline', () => {
    it('shows View Details button that expands order info', async () => {
      const user = userEvent.setup()
      renderWithProviders(<OrdersPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Order #PO-2026-002')).toBeInTheDocument()
      })

      // Click View Details
      await user.click(screen.getByText('View Details'))

      // Should show expanded details
      await waitFor(() => {
        expect(screen.getByTestId('order-details')).toBeInTheDocument()
      })
      expect(screen.getByText('PO Number')).toBeInTheDocument()
      expect(screen.getByText('Total Amount')).toBeInTheDocument()
    })

    it('collapses details on second click', async () => {
      const user = userEvent.setup()
      renderWithProviders(<OrdersPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Order #PO-2026-002')).toBeInTheDocument()
      })

      await user.click(screen.getByText('View Details'))
      await waitFor(() => {
        expect(screen.getByTestId('order-details')).toBeInTheDocument()
      })

      await user.click(screen.getByText('View Details'))
      await waitFor(() => {
        expect(screen.queryByTestId('order-details')).not.toBeInTheDocument()
      })
    })
  })

  describe('AC5: Status badges use actual status', () => {
    it('shows actual status badge on secondary cards (not hardcoded labels)', async () => {
      server.use(
        http.get('/api/v1/orders', ({ request }) => {
          const url = new URL(request.url)
          const statusGroup = url.searchParams.get('status_group')
          if (statusGroup === 'active') {
            return HttpResponse.json({
              items: [
                { id: 10, vendor_name: 'VWR', po_number: 'PO-SHIP-001', status: 'shipped', total_amount: 200.00, item_count: 2 },
                { id: 11, vendor_name: 'Bio-Rad', po_number: 'PO-PEND-001', status: 'pending', total_amount: 150.00, item_count: 1 },
              ],
              total: 2, page: 1, page_size: 20, pages: 1,
            })
          }
          return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20, pages: 0 })
        }),
      )

      renderWithProviders(<OrdersPage onError={onError} />)

      // Secondary card should show actual status 'Pending' (from formatEnum)
      await waitFor(() => {
        expect(screen.getAllByText('Pending').length).toBeGreaterThanOrEqual(1)
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
        http.get('/api/v1/orders', ({ request }) => {
          const url = new URL(request.url)
          const statusGroup = url.searchParams.get('status_group')
          if (statusGroup === 'active') {
            return HttpResponse.json({
              items: [
                { id: 10, vendor_name: 'VWR', po_number: 'PO-SHIP-001', status: 'shipped', total_amount: 100.00, item_count: 1 },
              ],
              total: 1, page: 1, page_size: 20, pages: 1,
            })
          }
          return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20, pages: 0 })
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

  describe('AC6: Loading state', () => {
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

  describe('AC7: Empty state when no orders', () => {
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
