import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { renderWithProviders } from '@/test/utils'
import { Header } from '@/components/layout/Header'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

const defaultProps = {
  title: 'Dashboard',
  onSearch: vi.fn(),
}

describe('Header', () => {
  beforeEach(() => {
    defaultProps.onSearch.mockClear()
    mockNavigate.mockClear()
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('AC1: Search input exists and accepts text', () => {
    it('renders a search input with combobox role', () => {
      renderWithProviders(<Header {...defaultProps} />)
      const input = screen.getByRole('combobox')
      expect(input).toBeInTheDocument()
      expect(input).toHaveAttribute('placeholder', expect.stringContaining('Search'))
    })

    it('accepts typed text', async () => {
      vi.useRealTimers()
      const user = userEvent.setup()
      renderWithProviders(<Header {...defaultProps} />)
      const input = screen.getByRole('combobox')
      await user.type(input, 'sodium')
      expect(input).toHaveValue('sodium')
    })
  })

  describe('AC2: Enter key triggers onSearch callback', () => {
    it('calls onSearch on Enter', async () => {
      vi.useRealTimers()
      const user = userEvent.setup()

      renderWithProviders(<Header {...defaultProps} />)
      const input = screen.getByRole('combobox')
      await user.type(input, 'ethanol')
      await user.keyboard('{Enter}')

      await waitFor(() => {
        expect(defaultProps.onSearch).toHaveBeenCalledWith('ethanol')
      })
    })

    it('does not trigger search on Enter with empty query', async () => {
      vi.useRealTimers()
      const user = userEvent.setup()

      renderWithProviders(<Header {...defaultProps} />)
      const input = screen.getByRole('combobox')
      await user.click(input)
      await user.keyboard('{Enter}')

      expect(defaultProps.onSearch).not.toHaveBeenCalled()
    })
  })

  describe('AC3: Typing shows suggestions from search.suggest() (debounced)', () => {
    it('shows suggestions after debounce delay', async () => {
      server.use(
        http.get('/api/v1/search/suggest', () =>
          HttpResponse.json({
            suggestions: [
              { type: 'product', text: 'Sodium Chloride', id: 1 },
              { type: 'product', text: 'Sodium Hydroxide', id: 2 },
            ],
          }),
        ),
      )

      renderWithProviders(<Header {...defaultProps} />)
      const input = screen.getByRole('combobox')

      // Type at least 2 chars to trigger suggest
      await userEvent.type(input, 'so', { delay: 10 })

      // Advance past the 300ms debounce
      await vi.advanceTimersByTimeAsync(350)

      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument()
        expect(screen.getByText('Sodium Chloride')).toBeInTheDocument()
        expect(screen.getByText('Sodium Hydroxide')).toBeInTheDocument()
      })
    })

    it('does not show suggestions for single character input', async () => {
      renderWithProviders(<Header {...defaultProps} />)
      const input = screen.getByRole('combobox')

      await userEvent.type(input, 'a', { delay: 10 })
      await vi.advanceTimersByTimeAsync(350)

      expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    })
  })

  describe('AC5: Search suggestions dropdown appears', () => {
    it('renders suggestions as a listbox with option roles', async () => {
      server.use(
        http.get('/api/v1/search/suggest', () =>
          HttpResponse.json({
            suggestions: [
              { type: 'product', text: 'Ethanol 95%', id: 1 },
              { type: 'product', text: 'Ethanol Absolute', id: 2 },
            ],
          }),
        ),
      )

      renderWithProviders(<Header {...defaultProps} />)
      const input = screen.getByRole('combobox')

      await userEvent.type(input, 'eth', { delay: 10 })
      await vi.advanceTimersByTimeAsync(350)

      await waitFor(() => {
        const listbox = screen.getByRole('listbox')
        expect(listbox).toBeInTheDocument()
        const options = screen.getAllByRole('option')
        expect(options).toHaveLength(2)
        expect(options[0]).toHaveTextContent('Ethanol 95%')
        expect(options[1]).toHaveTextContent('Ethanol Absolute')
      })
    })

    it('sets aria-expanded to true when suggestions are visible', async () => {
      server.use(
        http.get('/api/v1/search/suggest', () =>
          HttpResponse.json({
            suggestions: [{ type: 'product', text: 'Test suggestion', id: 1 }],
          }),
        ),
      )

      renderWithProviders(<Header {...defaultProps} />)
      const input = screen.getByRole('combobox')

      // Initially not expanded
      expect(input).toHaveAttribute('aria-expanded', 'false')

      await userEvent.type(input, 'te', { delay: 10 })
      await vi.advanceTimersByTimeAsync(350)

      await waitFor(() => {
        expect(input).toHaveAttribute('aria-expanded', 'true')
      })
    })
  })

  describe('AC6: Selecting a suggestion navigates to the correct page', () => {
    it('navigates to /products when a product suggestion is clicked', async () => {
      server.use(
        http.get('/api/v1/search/suggest', () =>
          HttpResponse.json({
            suggestions: [
              { type: 'product', text: 'Sodium Chloride', id: 1 },
            ],
          }),
        ),
      )

      renderWithProviders(<Header {...defaultProps} />)
      const input = screen.getByRole('combobox')

      await userEvent.type(input, 'so', { delay: 10 })
      await vi.advanceTimersByTimeAsync(350)

      await waitFor(() => {
        expect(screen.getByText('Sodium Chloride')).toBeInTheDocument()
      })

      // mouseDown triggers navigation before blur hides dropdown
      await userEvent.click(screen.getByText('Sodium Chloride'))

      expect(mockNavigate).toHaveBeenCalledWith('/products?search=Sodium%20Chloride')
    })

    it('navigates to /vendors when a vendor suggestion is clicked', async () => {
      server.use(
        http.get('/api/v1/search/suggest', () =>
          HttpResponse.json({
            suggestions: [
              { type: 'vendor', text: 'Sigma-Aldrich', id: 1 },
            ],
          }),
        ),
      )

      renderWithProviders(<Header {...defaultProps} />)
      const input = screen.getByRole('combobox')

      await userEvent.type(input, 'si', { delay: 10 })
      await vi.advanceTimersByTimeAsync(350)

      await waitFor(() => {
        expect(screen.getByText('Sigma-Aldrich')).toBeInTheDocument()
      })

      await userEvent.click(screen.getByText('Sigma-Aldrich'))

      expect(mockNavigate).toHaveBeenCalledWith('/vendors?search=Sigma-Aldrich')
    })

    it('shows type badge on each suggestion', async () => {
      server.use(
        http.get('/api/v1/search/suggest', () =>
          HttpResponse.json({
            suggestions: [
              { type: 'product', text: 'Test Item', id: 1 },
            ],
          }),
        ),
      )

      renderWithProviders(<Header {...defaultProps} />)
      const input = screen.getByRole('combobox')

      await userEvent.type(input, 'te', { delay: 10 })
      await vi.advanceTimersByTimeAsync(350)

      await waitFor(() => {
        const option = screen.getByRole('option')
        expect(option).toHaveTextContent('product')
        expect(option).toHaveTextContent('Test Item')
      })
    })
  })

  describe('AC7: Notification bell shows unread badge and dropdown', () => {
    it('shows unread count badge when alertCount > 0', () => {
      renderWithProviders(<Header {...defaultProps} alertCount={5} />)
      expect(screen.getByText('5')).toBeInTheDocument()
    })

    it('does not show badge when alertCount is 0', () => {
      renderWithProviders(<Header {...defaultProps} alertCount={0} />)
      const bellButton = screen.getByLabelText('Notifications')
      // No badge child with a number
      expect(bellButton.querySelector('span')).toBeNull()
    })

    it('caps badge at 99+', () => {
      renderWithProviders(<Header {...defaultProps} alertCount={150} />)
      expect(screen.getByText('99+')).toBeInTheDocument()
    })

    it('opens notification dropdown on bell click', async () => {
      vi.useRealTimers()
      const user = userEvent.setup()
      server.use(
        http.get('/api/v1/alerts/', () =>
          HttpResponse.json({
            items: [
              { id: 1, type: 'low_stock', severity: 'warning', message: 'Low stock alert', acknowledged: false, created_at: '2026-03-19T10:00:00' },
            ],
            total: 1,
          }),
        ),
      )

      renderWithProviders(<Header {...defaultProps} alertCount={1} />)
      const bellButton = screen.getByLabelText('Notifications')
      await user.click(bellButton)

      await waitFor(() => {
        expect(screen.getByText('Notifications')).toBeInTheDocument()
        expect(screen.getByText('View all')).toBeInTheDocument()
      })
    })

    it('shows "No new notifications" when alert list is empty', async () => {
      vi.useRealTimers()
      const user = userEvent.setup()
      server.use(
        http.get('/api/v1/alerts/', () =>
          HttpResponse.json({ items: [], total: 0 }),
        ),
      )

      renderWithProviders(<Header {...defaultProps} alertCount={0} />)
      const bellButton = screen.getByLabelText('Notifications')
      await user.click(bellButton)

      await waitFor(() => {
        expect(screen.getByText('No new notifications')).toBeInTheDocument()
      })
    })

    it('"View all" navigates to /alerts', async () => {
      vi.useRealTimers()
      const user = userEvent.setup()
      server.use(
        http.get('/api/v1/alerts/', () =>
          HttpResponse.json({ items: [], total: 0 }),
        ),
      )

      renderWithProviders(<Header {...defaultProps} alertCount={0} />)
      await user.click(screen.getByLabelText('Notifications'))

      await waitFor(() => {
        expect(screen.getByText('View all')).toBeInTheDocument()
      })

      await user.click(screen.getByText('View all'))
      expect(mockNavigate).toHaveBeenCalledWith('/alerts')
    })
  })

  describe('AC8: User name display', () => {
    it('shows provided userName instead of hardcoded Admin', () => {
      renderWithProviders(<Header {...defaultProps} userName="Dr. Aris Thorne" />)
      expect(screen.getByText('Dr. Aris Thorne')).toBeInTheDocument()
      expect(screen.queryByText('Admin')).not.toBeInTheDocument()
    })

    it('defaults to "User" when userName is not provided', () => {
      renderWithProviders(<Header {...defaultProps} />)
      expect(screen.getByText('User')).toBeInTheDocument()
    })
  })
})
