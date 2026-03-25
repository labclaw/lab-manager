import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { renderWithProviders } from '@/test/utils'
import { Header } from '@/components/layout/Header'

const defaultProps = {
  title: 'Dashboard',
  onSearch: vi.fn(),
}

describe('Header', () => {
  beforeEach(() => {
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
})
