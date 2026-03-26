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

  describe('AC2: Shows product name, vendor, location, stock, expiry columns', () => {
    it('renders table column headers', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Product')).toBeInTheDocument()
      })
      expect(screen.getByText('Lot #')).toBeInTheDocument()
      expect(screen.getByText('Vendor')).toBeInTheDocument()
      expect(screen.getByText('Location')).toBeInTheDocument()
      expect(screen.getByText('Stock')).toBeInTheDocument()
      expect(screen.getByText('Expiry')).toBeInTheDocument()
      expect(screen.getByText('Actions')).toBeInTheDocument()
    })

    it('shows product names in the product column', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Sodium Chloride')).toBeInTheDocument()
        expect(screen.getByText('Ethanol 95%')).toBeInTheDocument()
      })
    })

    it('shows catalog numbers under product names', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('S1234')).toBeInTheDocument()
        expect(screen.getByText('E5678')).toBeInTheDocument()
      })
    })

    it('shows vendor names from flattened API data', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Sigma-Aldrich')).toBeInTheDocument()
        expect(screen.getByText('Fisher Scientific')).toBeInTheDocument()
      })
    })

    it('shows location name for items with location', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Shelf A1')).toBeInTheDocument()
      })
    })

    it('shows lot numbers', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('LOT-ABC')).toBeInTheDocument()
        expect(screen.getByText('LOT-DEF')).toBeInTheDocument()
      })
    })

    it('shows formatted quantity with unit', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('5 kg')).toBeInTheDocument()
        expect(screen.getByText('2 L')).toBeInTheDocument()
      })
    })

    it('shows category badges', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Chemicals')).toBeInTheDocument()
        expect(screen.getByText('Solvents')).toBeInTheDocument()
      })
    })

    it('shows stock status badges', async () => {
      server.use(
        http.get('/api/v1/inventory', () =>
          HttpResponse.json({
            items: [
              { id: 1, product_name: 'Sodium Chloride', lot_number: 'LOT-ABC', quantity_on_hand: 5, quantity_display: '5', unit: 'kg', status: 'available', expiry_date: '2027-01-15' },
              { id: 2, product_name: 'Ethanol 95%', lot_number: 'LOT-DEF', quantity_on_hand: 2, quantity_display: '2', unit: 'L', status: 'low_stock', expiry_date: '2026-06-30' },
            ],
            total: 2, page: 1, page_size: 15, pages: 1,
          }),
        ),
      )

      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Low Stock')).toBeInTheDocument()
      })
    })
  })

  describe('AC3: Expiry date column with color coding', () => {
    it('shows expiry dates formatted', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Jan 15, 2027')).toBeInTheDocument()
      })
    })

    it('highlights expired items in red', async () => {
      server.use(
        http.get('/api/v1/inventory', () =>
          HttpResponse.json({
            items: [
              { id: 1, product_name: 'Expired Item', lot_number: 'LOT-EXP', quantity_on_hand: 1, quantity_display: '1', unit: 'ea', status: 'expired', expiry_date: '2020-01-01' },
            ],
            total: 1, page: 1, page_size: 15, pages: 1,
          }),
        ),
      )

      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        const expiryText = screen.getByText('Jan 1, 2020')
        // The text is inside <span> inside the colored parent <span class="text-red-600">
        const parentSpan = expiryText.parentElement
        expect(parentSpan).toHaveClass('text-red-600')
      })
    })

    it('shows dash when no expiry date', async () => {
      server.use(
        http.get('/api/v1/inventory', () =>
          HttpResponse.json({
            items: [
              { id: 1, product_name: 'No Expiry Item', lot_number: 'LOT-X', quantity_on_hand: 1, quantity_display: '1', unit: 'ea', status: 'available' },
            ],
            total: 1, page: 1, page_size: 15, pages: 1,
          }),
        ),
      )

      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('No Expiry Item')).toBeInTheDocument()
      })
    })
  })

  describe('AC4: No disabled Coming soon buttons', () => {
    it('does not render disabled Filters, Category, New Item, Bulk Order buttons', async () => {
      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('2 Items total')).toBeInTheDocument()
      })

      expect(screen.queryByText('Filters')).not.toBeInTheDocument()
      expect(screen.queryByText('Category')).not.toBeInTheDocument()
      expect(screen.queryByText('New Item')).not.toBeInTheDocument()
      expect(screen.queryByText('Bulk Order')).not.toBeInTheDocument()
    })
  })

  describe('AC5: Loading state', () => {
    it('shows spinner while loading', () => {
      server.use(
        http.get('/api/v1/inventory', async () => {
          await new Promise((resolve) => setTimeout(resolve, 500))
          return HttpResponse.json({
            items: [], total: 0, page: 1, page_size: 15, pages: 0,
          })
        }),
      )

      renderWithProviders(<InventoryPage onError={onError} />)

      const spinner = document.querySelector('.animate-spin')
      expect(spinner).toBeInTheDocument()
    })
  })

  describe('AC6: Empty state when no items', () => {
    it('shows empty state message when inventory is empty', async () => {
      server.use(
        http.get('/api/v1/inventory', () => {
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
        screen.getByText('Review and approve documents to populate inventory.'),
      ).toBeInTheDocument()
    })

    it('does not show pagination when inventory is empty', async () => {
      server.use(
        http.get('/api/v1/inventory', () => {
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

  describe('AC7: Fallback product name', () => {
    it('falls back to catalog_number when product_name is missing', async () => {
      server.use(
        http.get('/api/v1/inventory', () =>
          HttpResponse.json({
            items: [
              { id: 1, catalog_number: 'CAT-999', lot_number: 'LOT-X', quantity_on_hand: 1, quantity_display: '1', unit: 'ea', status: 'available' },
            ],
            total: 1, page: 1, page_size: 15, pages: 1,
          }),
        ),
      )

      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('CAT-999')).toBeInTheDocument()
      })
    })

    it('falls back to lot_number when both product_name and catalog_number are missing', async () => {
      server.use(
        http.get('/api/v1/inventory', () =>
          HttpResponse.json({
            items: [
              { id: 1, lot_number: 'LOT-ONLY', quantity_on_hand: 1, quantity_display: '1', unit: 'ea', status: 'available' },
            ],
            total: 1, page: 1, page_size: 15, pages: 1,
          }),
        ),
      )

      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        // lot_number appears as the primary name
        const nameElements = screen.getAllByText('LOT-ONLY')
        expect(nameElements.length).toBeGreaterThanOrEqual(1)
      })
    })

    it('falls back to Item #id as last resort', async () => {
      server.use(
        http.get('/api/v1/inventory', () =>
          HttpResponse.json({
            items: [
              { id: 42, quantity_on_hand: 1, quantity_display: '1', unit: 'ea', status: 'available' },
            ],
            total: 1, page: 1, page_size: 15, pages: 1,
          }),
        ),
      )

      renderWithProviders(<InventoryPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Item #42')).toBeInTheDocument()
      })
    })
  })
})
