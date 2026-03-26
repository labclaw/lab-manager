import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { renderWithProviders } from '@/test/utils'
import { VendorsPage } from '@/pages/VendorsPage'

const onError = vi.fn()

describe('VendorsPage', () => {
  describe('AC1: Vendor list loads from GET /vendors with pagination', () => {
    it('renders vendor names from the API', async () => {
      renderWithProviders(<VendorsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Sigma-Aldrich')).toBeInTheDocument()
      })
      expect(screen.getByText('Fisher Scientific')).toBeInTheDocument()
    })

    it('displays total vendor count', async () => {
      renderWithProviders(<VendorsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('2 Vendors total')).toBeInTheDocument()
      })
    })

    it('shows pagination footer with vendor range', async () => {
      renderWithProviders(<VendorsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Showing 1-2 of 2 vendors')).toBeInTheDocument()
      })
    })
  })

  describe('AC2: Table columns display vendor details', () => {
    it('renders table column headers', async () => {
      renderWithProviders(<VendorsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Vendor')).toBeInTheDocument()
      })
      expect(screen.getByText('Email')).toBeInTheDocument()
      expect(screen.getByText('Phone')).toBeInTheDocument()
      expect(screen.getByText('Website')).toBeInTheDocument()
      expect(screen.getByText('Actions')).toBeInTheDocument()
    })

    it('shows vendor emails', async () => {
      renderWithProviders(<VendorsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('orders@sigma.com')).toBeInTheDocument()
        expect(screen.getByText('info@fisher.com')).toBeInTheDocument()
      })
    })
  })

  describe('AC3: Loading state', () => {
    it('shows spinner while loading', () => {
      server.use(
        http.get('/api/v1/vendors/', async () => {
          await new Promise((resolve) => setTimeout(resolve, 500))
          return HttpResponse.json({
            items: [], total: 0, page: 1, page_size: 15, pages: 0,
          })
        }),
      )

      renderWithProviders(<VendorsPage onError={onError} />)

      const spinner = document.querySelector('.animate-spin')
      expect(spinner).toBeInTheDocument()
    })
  })

  describe('AC4: Empty state when no vendors', () => {
    it('shows empty state message', async () => {
      server.use(
        http.get('/api/v1/vendors/', () =>
          HttpResponse.json({
            items: [], total: 0, page: 1, page_size: 15, pages: 0,
          }),
        ),
      )

      renderWithProviders(<VendorsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('No vendors found')).toBeInTheDocument()
      })
      expect(
        screen.getByText('Add your first vendor to get started.'),
      ).toBeInTheDocument()
    })

    it('does not show pagination when vendor list is empty', async () => {
      server.use(
        http.get('/api/v1/vendors/', () =>
          HttpResponse.json({
            items: [], total: 0, page: 1, page_size: 15, pages: 0,
          }),
        ),
      )

      renderWithProviders(<VendorsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('No vendors found')).toBeInTheDocument()
      })
      expect(screen.queryByText(/Showing/)).not.toBeInTheDocument()
    })
  })

  describe('AC5: New Vendor button opens modal', () => {
    it('renders New Vendor button', async () => {
      renderWithProviders(<VendorsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('New Vendor')).toBeInTheDocument()
      })
    })

    it('opens create modal on button click', async () => {
      const user = userEvent.setup()
      renderWithProviders(<VendorsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByText('Sigma-Aldrich')).toBeInTheDocument()
      })

      await user.click(screen.getByText('New Vendor'))

      await waitFor(() => {
        // Modal title for create mode
        expect(screen.getByRole('heading', { name: 'New Vendor' })).toBeInTheDocument()
      })
    })
  })

  describe('AC6: Search functionality', () => {
    it('renders search input', async () => {
      renderWithProviders(<VendorsPage onError={onError} />)

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search vendors...')).toBeInTheDocument()
      })
    })
  })

  describe('AC7: Error handling', () => {
    it('calls onError when API fails', async () => {
      server.use(
        http.get('/api/v1/vendors/', () =>
          HttpResponse.json({ detail: 'Server error' }, { status: 500 }),
        ),
      )

      renderWithProviders(<VendorsPage onError={onError} />)

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith('Server error')
      })
    })
  })
})
