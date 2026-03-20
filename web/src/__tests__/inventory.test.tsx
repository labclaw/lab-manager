import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { renderWithProviders } from '@/test/utils'
import { InventoryPage } from '@/pages/InventoryPage'

const onError = vi.fn()

describe('InventoryPage', () => {
  describe('AC1: Inventory list loads from GET /inventory with pagination', () => {
    it('renders inventory items from the API', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Sodium Chloride')).toBeInTheDocument()
      })
      expect(screen.getByText('Ethanol 95%')).toBeInTheDocument()
    })

    it('displays total item count', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('2 Items total')).toBeInTheDocument()
      })
    })

    it('shows pagination footer with item range', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Showing 1-2 of 2 items')).toBeInTheDocument()
      })
    })
  })

  describe('AC2: Shows product name, lot number, quantity, unit, status columns', () => {
    it('renders table column headers', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Item Name')).toBeInTheDocument()
      })
      expect(screen.getByText('Lot #')).toBeInTheDocument()
      expect(screen.getByText('Vendor')).toBeInTheDocument()
      expect(screen.getByText('Location')).toBeInTheDocument()
      expect(screen.getByText('Stock')).toBeInTheDocument()
      expect(screen.getByText('Actions')).toBeInTheDocument()
    })

    it('shows product names in the item name column', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Sodium Chloride')).toBeInTheDocument()
        expect(screen.getByText('Ethanol 95%')).toBeInTheDocument()
      })
    })

    it('shows lot numbers', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('LOT-ABC')).toBeInTheDocument()
        expect(screen.getByText('LOT-DEF')).toBeInTheDocument()
      })
    })

    it('shows quantity with unit', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('5 kg')).toBeInTheDocument()
        expect(screen.getByText('2 L')).toBeInTheDocument()
      })
    })

    it('shows stock status badges', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      // quantity 5 > 3 => In Stock, quantity 2 <= 3 => Low Stock
      await waitFor(() => {
        expect(screen.getByText('In Stock')).toBeInTheDocument()
        expect(screen.getByText('Low Stock')).toBeInTheDocument()
      })
    })
  })

  describe('AC3: Filter buttons are rendered', () => {
    it('renders filter and category buttons', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Filters')).toBeInTheDocument()
      })
      expect(screen.getByText('Category')).toBeInTheDocument()
    })
  })

  describe('AC4: Loading state', () => {
    it('shows spinner while loading', () => {
      // Delay the response to keep loading state visible
      server.use(
        http.get('/api/inventory', async () => {
          await new Promise((resolve) => setTimeout(resolve, 500))
          return HttpResponse.json({
            items: [], total: 0, page: 1, page_size: 15, pages: 0,
          })
        }),
      )

      renderWithProviders(<InventoryPage onError={onError} />)

      // The spinner is a div with animate-spin class
      const spinner = document.querySelector('.animate-spin')
      expect(spinner).toBeInTheDocument()
    })
  })

  describe('AC5: Empty state when no items', () => {
    it('shows empty state message when inventory is empty', async () => {
      server.use(
        http.get('/api/inventory', () => {
          return HttpResponse.json({
            items: [], total: 0, page: 1, page_size: 15, pages: 0,
          })
        }),
      )

      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Inventory is empty')).toBeInTheDocument()
      })
      expect(
        screen.getByText('Process documents through the review queue to populate inventory.'),
      ).toBeInTheDocument()
    })

    it('does not show pagination when inventory is empty', async () => {
      server.use(
        http.get('/api/inventory', () => {
          return HttpResponse.json({
            items: [], total: 0, page: 1, page_size: 15, pages: 0,
          })
        }),
      )

      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Inventory is empty')).toBeInTheDocument()
      })
      expect(screen.queryByText(/Showing/)).not.toBeInTheDocument()
    })
  })
})
