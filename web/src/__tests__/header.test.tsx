import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { renderWithProviders } from '@/test/utils'
import { Header } from '@/components/layout/Header'

const defaultProps = {
  title: 'Dashboard',
  darkMode: true,
  onToggleDarkMode: vi.fn(),
  onSearch: vi.fn(),
}

describe('Header', () => {
  beforeEach(() => {
    defaultProps.onToggleDarkMode.mockClear()
    defaultProps.onSearch.mockClear()
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

  describe('AC2: Enter key triggers search.query() via onSearch callback', () => {
    it('calls onSearch and search.query on Enter', async () => {
      vi.useRealTimers()
      const user = userEvent.setup()
      let queryCalled = false

      server.use(
        http.get('/api/search', ({ request }) => {
          const url = new URL(request.url)
          if (url.searchParams.get('q') === 'ethanol') {
            queryCalled = true
          }
          return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20, pages: 0 })
        }),
      )

      renderWithProviders(<Header {...defaultProps} />)
      const input = screen.getByRole('combobox')
      await user.type(input, 'ethanol')
      await user.keyboard('{Enter}')

      await waitFor(() => {
        expect(defaultProps.onSearch).toHaveBeenCalledWith('ethanol')
        expect(queryCalled).toBe(true)
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
        http.get('/api/search/suggest', () =>
          HttpResponse.json({
            suggestions: ['Sodium Chloride', 'Sodium Hydroxide'],
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

  describe('AC4: Dark mode toggle works', () => {
    it('calls onToggleDarkMode when dark mode button is clicked', async () => {
      vi.useRealTimers()
      const user = userEvent.setup()

      renderWithProviders(<Header {...defaultProps} />)
      const toggle = screen.getByLabelText(/switch to light mode/i)
      await user.click(toggle)

      expect(defaultProps.onToggleDarkMode).toHaveBeenCalledTimes(1)
    })

    it('shows correct aria-label for light mode state', () => {
      renderWithProviders(<Header {...defaultProps} darkMode={false} />)
      expect(screen.getByLabelText(/switch to dark mode/i)).toBeInTheDocument()
    })
  })

  describe('AC5: Search suggestions dropdown appears', () => {
    it('renders suggestions as a listbox with option roles', async () => {
      server.use(
        http.get('/api/search/suggest', () =>
          HttpResponse.json({
            suggestions: ['Ethanol 95%', 'Ethanol Absolute'],
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
        http.get('/api/search/suggest', () =>
          HttpResponse.json({
            suggestions: ['Test suggestion'],
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
})
