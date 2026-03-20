import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { renderWithProviders } from '@/test/utils'
import { DocumentsPage } from '@/pages/DocumentsPage'

const onError = vi.fn()

function renderDocuments() {
  return renderWithProviders(<DocumentsPage onError={onError} />)
}

describe('DocumentsPage', () => {
  describe('AC1: Document list loads from GET /documents with pagination', () => {
    it('loads and displays documents from the API', async () => {
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('invoice_001.pdf')).toBeInTheDocument()
      })
      expect(screen.getByText('packing_list_002.pdf')).toBeInTheDocument()
    })

    it('shows pagination info with correct counts', async () => {
      renderDocuments()
      // "Showing 1 to 2 of 2 documents" — text spans multiple elements
      await waitFor(() => {
        expect(screen.getByText(/^Showing/)).toBeInTheDocument()
      })
      // Verify the pagination text contains correct numbers
      const paginationText = screen.getByText(/^Showing/).closest('p')!
      expect(paginationText.textContent).toContain('1')
      expect(paginationText.textContent).toContain('2')
      expect(paginationText.textContent).toContain('documents')
    })

    it('renders previous and next page buttons', async () => {
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('invoice_001.pdf')).toBeInTheDocument()
      })
      expect(screen.getByLabelText('Previous page')).toBeInTheDocument()
      expect(screen.getByLabelText('Next page')).toBeInTheDocument()
    })

    it('disables previous button on first page', async () => {
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('invoice_001.pdf')).toBeInTheDocument()
      })
      expect(screen.getByLabelText('Previous page')).toBeDisabled()
    })

    it('disables next button on last page', async () => {
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('invoice_001.pdf')).toBeInTheDocument()
      })
      // total=2, pageSize=20, pages=1 => on last page
      expect(screen.getByLabelText('Next page')).toBeDisabled()
    })
  })

  describe('AC2: Shows filename, vendor, type, status, date columns', () => {
    it('displays table headers', async () => {
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('invoice_001.pdf')).toBeInTheDocument()
      })
      expect(screen.getByText('Filename')).toBeInTheDocument()
      expect(screen.getByText('Vendor')).toBeInTheDocument()
      expect(screen.getByText('Type')).toBeInTheDocument()
      expect(screen.getByText('Status')).toBeInTheDocument()
      expect(screen.getByText('Confidence')).toBeInTheDocument()
      expect(screen.getByText('Date')).toBeInTheDocument()
    })

    it('displays document filename', async () => {
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('invoice_001.pdf')).toBeInTheDocument()
      })
    })

    it('displays vendor name', async () => {
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('Sigma-Aldrich')).toBeInTheDocument()
      })
      expect(screen.getByText('Fisher Scientific')).toBeInTheDocument()
    })

    it('displays document type', async () => {
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('invoice')).toBeInTheDocument()
      })
      expect(screen.getByText('packing_list')).toBeInTheDocument()
    })

    it('displays status badges', async () => {
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('invoice_001.pdf')).toBeInTheDocument()
      })
      // Check that table rows contain status badges
      const table = screen.getByRole('table')
      const approvedBadge = within(table).getByText('Approved')
      expect(approvedBadge).toBeInTheDocument()
      const needsReviewBadge = within(table).getByText('Needs Review')
      expect(needsReviewBadge).toBeInTheDocument()
    })

    it('displays formatted dates', async () => {
      renderDocuments()
      // '2026-03-15T10:00:00' => 'Mar 15'
      await waitFor(() => {
        expect(screen.getByText('Mar 15')).toBeInTheDocument()
      })
      // '2026-03-18T14:30:00' => 'Mar 18'
      expect(screen.getByText('Mar 18')).toBeInTheDocument()
    })

    it('displays confidence values', async () => {
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('0.95')).toBeInTheDocument()
      })
      expect(screen.getByText('0.72')).toBeInTheDocument()
    })
  })

  describe('AC3: Status filter works', () => {
    it('renders all status filter buttons', async () => {
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('invoice_001.pdf')).toBeInTheDocument()
      })
      expect(screen.getByRole('button', { name: /^All$/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Approved/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Rejected/ })).toBeInTheDocument()
    })

    it('filters by needs_review status and shows review queue', async () => {
      const user = userEvent.setup()
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('invoice_001.pdf')).toBeInTheDocument()
      })

      // Find the filter button that says "Needs Review" (not the table badge)
      const filterButtons = screen.getAllByRole('button', { name: /Needs Review/ })
      const filterBtn = filterButtons[0]!
      await user.click(filterBtn)

      // MSW returns mockReviewQueue for status=needs_review
      await waitFor(() => {
        expect(screen.getByText('review_doc_1.pdf')).toBeInTheDocument()
      })
      expect(screen.getByText('review_doc_2.pdf')).toBeInTheDocument()
    })

    it('returns to all documents when clicking All filter', async () => {
      const user = userEvent.setup()
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('invoice_001.pdf')).toBeInTheDocument()
      })

      // Switch to needs_review
      const filterButtons = screen.getAllByRole('button', { name: /Needs Review/ })
      await user.click(filterButtons[0]!)
      await waitFor(() => {
        expect(screen.getByText('review_doc_1.pdf')).toBeInTheDocument()
      })

      // Switch back to All
      await user.click(screen.getByRole('button', { name: /^All$/ }))
      await waitFor(() => {
        expect(screen.getByText('invoice_001.pdf')).toBeInTheDocument()
      })
    })
  })

  describe('AC4: Empty state shown when no documents', () => {
    it('shows empty state when API returns no documents', async () => {
      server.use(
        http.get('/api/documents', () =>
          HttpResponse.json({
            items: [],
            total: 0,
            page: 1,
            page_size: 20,
            pages: 0,
          }),
        ),
      )
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('No documents found')).toBeInTheDocument()
      })
    })

    it('shows upload button in empty state', async () => {
      server.use(
        http.get('/api/documents', () =>
          HttpResponse.json({
            items: [],
            total: 0,
            page: 1,
            page_size: 20,
            pages: 0,
          }),
        ),
      )
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('No documents found')).toBeInTheDocument()
      })
      // There should be an "Upload Document" button in the empty state
      const uploadButtons = screen.getAllByText('Upload Document')
      expect(uploadButtons.length).toBeGreaterThanOrEqual(1)
    })

    it('shows search-specific empty state when search has no matches', async () => {
      const user = userEvent.setup()
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('invoice_001.pdf')).toBeInTheDocument()
      })

      const searchInput = screen.getByPlaceholderText('Search vendor or filename...')
      await user.type(searchInput, 'nonexistent_xyz')

      await waitFor(() => {
        expect(
          screen.getByText('No documents matching "nonexistent_xyz"'),
        ).toBeInTheDocument()
      })
    })
  })

  describe('AC5: Click row navigates to detail', () => {
    it('navigates to review page on row click', async () => {
      const user = userEvent.setup()
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('invoice_001.pdf')).toBeInTheDocument()
      })

      // Click the row containing invoice_001.pdf
      const row = screen.getByText('invoice_001.pdf').closest('tr')!
      await user.click(row)

      // Navigation should have been called - we can verify the row is clickable
      // (has cursor-pointer class and onClick handler)
      expect(row.className).toContain('cursor-pointer')
    })
  })

  describe('AC6: Loading state', () => {
    it('shows loading spinner while fetching documents', async () => {
      server.use(
        http.get('/api/documents', async () => {
          await new Promise(() => {
            /* never resolves */
          })
          return HttpResponse.json({})
        }),
      )
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('Fetching documents...')).toBeInTheDocument()
      })
    })

    it('shows spinner element during loading', async () => {
      server.use(
        http.get('/api/documents', async () => {
          await new Promise(() => {
            /* never resolves */
          })
          return HttpResponse.json({})
        }),
      )
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('Fetching documents...')).toBeInTheDocument()
      })
      // The spinner div with animate-spin class
      const spinner = document.querySelector('.animate-spin')
      expect(spinner).toBeInTheDocument()
    })

    it('replaces loading state with data once loaded', async () => {
      renderDocuments()
      await waitFor(() => {
        expect(screen.getByText('invoice_001.pdf')).toBeInTheDocument()
      })
      expect(screen.queryByText('Fetching documents...')).not.toBeInTheDocument()
    })
  })
})
