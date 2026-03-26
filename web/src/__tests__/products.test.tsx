import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { renderWithProviders } from '@/test/utils'
import { ProductsPage } from '@/pages/ProductsPage'

const onError = vi.fn()

describe('ProductsPage', () => {
  describe('AC1: Product list loads from GET /products with pagination', () => {
    it('renders product names from the API', async () => {
      renderWithProviders(<ProductsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Sodium Chloride')).toBeInTheDocument()
      })
      expect(screen.getByText('Ethanol 95%')).toBeInTheDocument()
    })

    it('displays total product count', async () => {
      renderWithProviders(<ProductsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('2 Products total')).toBeInTheDocument()
      })
    })

    it('shows pagination footer with product range', async () => {
      renderWithProviders(<ProductsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Showing 1-2 of 2 products')).toBeInTheDocument()
      })
    })
  })

  describe('AC2: Table columns display product details', () => {
    it('renders table column headers', async () => {
      renderWithProviders(<ProductsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Product')).toBeInTheDocument()
      })
      expect(screen.getByText('Catalog #')).toBeInTheDocument()
      expect(screen.getByText('Vendor')).toBeInTheDocument()
      expect(screen.getByText('Category')).toBeInTheDocument()
      expect(screen.getByText('Storage')).toBeInTheDocument()
      expect(screen.getByText('Actions')).toBeInTheDocument()
    })

    it('shows catalog numbers', async () => {
      renderWithProviders(<ProductsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('S1234')).toBeInTheDocument()
        expect(screen.getByText('E5678')).toBeInTheDocument()
      })
    })

    it('shows vendor names', async () => {
      renderWithProviders(<ProductsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Sigma-Aldrich')).toBeInTheDocument()
        expect(screen.getByText('Fisher Scientific')).toBeInTheDocument()
      })
    })

    it('shows CAS numbers', async () => {
      renderWithProviders(<ProductsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('CAS: 7647-14-5')).toBeInTheDocument()
        expect(screen.getByText('CAS: 64-17-5')).toBeInTheDocument()
      })
    })

    it('shows categories', async () => {
      renderWithProviders(<ProductsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Chemicals')).toBeInTheDocument()
        expect(screen.getByText('Solvents')).toBeInTheDocument()
      })
    })
  })

  describe('AC3: Loading state', () => {
    it('shows spinner while loading', () => {
      server.use(
        http.get('/api/v1/products/', async () => {
          await new Promise((resolve) => setTimeout(resolve, 500))
          return HttpResponse.json({
            items: [], total: 0, page: 1, page_size: 15, pages: 0,
          })
        }),
      )

      renderWithProviders(<ProductsPage onError={onError} />)

      const spinner = document.querySelector('.animate-spin')
      expect(spinner).toBeInTheDocument()
    })
  })

  describe('AC4: Empty state when no products', () => {
    it('shows empty state message', async () => {
      server.use(
        http.get('/api/v1/products/', () =>
          HttpResponse.json({
            items: [], total: 0, page: 1, page_size: 15, pages: 0,
          }),
        ),
      )

      renderWithProviders(<ProductsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('No products found')).toBeInTheDocument()
      })
      expect(
        screen.getByText('Add your first product to get started.'),
      ).toBeInTheDocument()
    })

    it('does not show pagination when product list is empty', async () => {
      server.use(
        http.get('/api/v1/products/', () =>
          HttpResponse.json({
            items: [], total: 0, page: 1, page_size: 15, pages: 0,
          }),
        ),
      )

      renderWithProviders(<ProductsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('No products found')).toBeInTheDocument()
      })
      expect(screen.queryByText(/Showing/)).not.toBeInTheDocument()
    })
  })

  describe('AC5: New Product button opens modal', () => {
    it('renders New Product button', async () => {
      renderWithProviders(<ProductsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('New Product')).toBeInTheDocument()
      })
    })

    it('opens create modal on button click', async () => {
      const user = userEvent.setup()
      renderWithProviders(<ProductsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Sodium Chloride')).toBeInTheDocument()
      })

      await user.click(screen.getByText('New Product'))

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'New Product' })).toBeInTheDocument()
      })
    })
  })

  describe('AC6: Search functionality', () => {
    it('renders search input', async () => {
      renderWithProviders(<ProductsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search products...')).toBeInTheDocument()
      })
    })
  })

  describe('AC7: Error handling', () => {
    it('calls onError when API fails', async () => {
      server.use(
        http.get('/api/v1/products/', () =>
          HttpResponse.json({ detail: 'Server error' }, { status: 500 }),
        ),
      )

      renderWithProviders(<ProductsPage onError={onError} />)

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith('Server error')
      })
    })
  })
})
