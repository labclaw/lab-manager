import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { renderWithProviders } from '@/test/utils'
import { ReviewPage } from '@/pages/ReviewPage'

const onError = vi.fn()

function renderReview() {
  return renderWithProviders(<ReviewPage onError={onError} />, {
    initialEntries: ['/review'],
  })
}

describe('ReviewPage', () => {
  describe('AC1: Queue shows all documents with status=needs_review', () => {
    it('renders review queue items from API', async () => {
      renderReview()

      // Filename appears in both queue list and detail panel, so use getAllByText
      await waitFor(() => {
        expect(screen.getAllByText('review_doc_1.pdf').length).toBeGreaterThanOrEqual(1)
      })
      expect(screen.getAllByText('review_doc_2.pdf').length).toBeGreaterThanOrEqual(1)
    })

    it('shows the queue count in header', async () => {
      renderReview()

      await waitFor(() => {
        expect(
          screen.getByText('2 documents awaiting verification'),
        ).toBeInTheDocument()
      })
    })

    it('shows vendor names for each document', async () => {
      renderReview()

      await waitFor(() => {
        // Sigma-Aldrich appears as queue text; Fisher Scientific as queue text
        expect(screen.getByText('Sigma-Aldrich')).toBeInTheDocument()
      })
      expect(screen.getByText('Fisher Scientific')).toBeInTheDocument()
    })
  })

  describe('AC2: Selecting a document shows extracted data', () => {
    it('auto-selects the first item and shows its detail', async () => {
      renderReview()

      // Items are sorted by confidence ascending: id=10 (0.65) first, then id=11 (0.88)
      await waitFor(() => {
        expect(screen.getByText('Review Queue')).toBeInTheDocument()
      })

      // The detail panel should show the vendor in a readonly input
      await waitFor(() => {
        const vendorInput = screen.getByDisplayValue('Sigma-Aldrich')
        expect(vendorInput).toBeInTheDocument()
      })
    })

    it('clicking a different document updates the detail panel', async () => {
      const user = userEvent.setup()
      renderReview()

      // Wait for queue to load
      await waitFor(() => {
        expect(screen.getAllByText('review_doc_2.pdf').length).toBeGreaterThanOrEqual(1)
      })

      // Click the second document in the queue list (Fisher Scientific, id=11)
      // The queue list items have h3 elements with filenames
      const doc2Headings = screen.getAllByText('review_doc_2.pdf')
      await user.click(doc2Headings[0])

      // Wait for the detail to load for the selected document
      await waitFor(() => {
        expect(
          screen.getByDisplayValue('Fisher Scientific'),
        ).toBeInTheDocument()
      })
    })
  })

  describe('AC4: Confidence indicators show per-field extraction confidence', () => {
    it('displays confidence badge for each document in the queue', async () => {
      renderReview()

      await waitFor(() => {
        expect(screen.getByText('65% Conf.')).toBeInTheDocument()
      })
      expect(screen.getByText('88% Conf.')).toBeInTheDocument()
    })

    it('shows confidence level label in the detail preview', async () => {
      renderReview()

      // id=10 has confidence 0.65 => "Medium" (>= 0.6, < 0.8)
      await waitFor(() => {
        expect(screen.getByText(/Medium/)).toBeInTheDocument()
        expect(screen.getByText(/extraction confidence/)).toBeInTheDocument()
      })
    })
  })

  describe('AC5: Approve button calls POST /documents/{id}/review with action=approve', () => {
    it('calls review endpoint with action=approve when Approve is clicked', async () => {
      const user = userEvent.setup()
      let capturedBody: Record<string, unknown> | null = null
      let capturedUrl = ''

      server.use(
        http.post('/api/documents/:id/review', async ({ request, params }) => {
          capturedUrl = `/api/documents/${params.id}/review`
          capturedBody = (await request.json()) as Record<string, unknown>
          return HttpResponse.json({ status: 'ok' })
        }),
      )

      renderReview()

      await waitFor(() => {
        expect(screen.getAllByText('review_doc_1.pdf').length).toBeGreaterThanOrEqual(1)
      })

      // Match "check_circle Approve" but not "edit_document Edit & Approve"
      const approveBtns = screen.getAllByRole('button', { name: /Approve/i })
      // First match is the plain Approve button, second is Edit & Approve
      const approveBtn = approveBtns[0]
      await user.click(approveBtn)

      await waitFor(() => {
        expect(capturedBody).not.toBeNull()
      })

      // Sorted by confidence ascending: id=10 is first (auto-selected)
      expect(capturedUrl).toBe('/api/documents/10/review')
      expect(capturedBody).toEqual(
        expect.objectContaining({
          action: 'approve',
          reviewed_by: 'admin',
        }),
      )
    })
  })

  describe('AC6: Reject button requires notes, calls review with action=reject', () => {
    it('opens rejection dialog when Reject is clicked', async () => {
      const user = userEvent.setup()
      renderReview()

      await waitFor(() => {
        expect(screen.getAllByText('review_doc_1.pdf').length).toBeGreaterThanOrEqual(1)
      })

      const rejectBtn = screen.getByRole('button', { name: /Reject/i })
      await user.click(rejectBtn)

      await waitFor(() => {
        expect(screen.getByText('Reject Document')).toBeInTheDocument()
      })
      expect(
        screen.getByPlaceholderText('Describe the issue...'),
      ).toBeInTheDocument()
    })

    it('calls review endpoint with action=reject and notes', async () => {
      const user = userEvent.setup()
      let capturedBody: Record<string, unknown> | null = null

      server.use(
        http.post('/api/documents/:id/review', async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>
          return HttpResponse.json({ status: 'ok' })
        }),
      )

      renderReview()

      await waitFor(() => {
        expect(screen.getAllByText('review_doc_1.pdf').length).toBeGreaterThanOrEqual(1)
      })

      // Open reject dialog
      await user.click(screen.getByRole('button', { name: /Reject/i }))

      await waitFor(() => {
        expect(screen.getByText('Reject Document')).toBeInTheDocument()
      })

      // Type reason
      const textarea = screen.getByPlaceholderText('Describe the issue...')
      await user.type(textarea, 'Wrong vendor detected')

      // Confirm rejection
      await user.click(
        screen.getByRole('button', { name: /Confirm Rejection/i }),
      )

      await waitFor(() => {
        expect(capturedBody).not.toBeNull()
      })

      expect(capturedBody).toEqual(
        expect.objectContaining({
          action: 'reject',
          reviewed_by: 'admin',
          review_notes: 'Wrong vendor detected',
        }),
      )
    })

    it('submits default notes when no reason is typed', async () => {
      const user = userEvent.setup()
      let capturedBody: Record<string, unknown> | null = null

      server.use(
        http.post('/api/documents/:id/review', async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>
          return HttpResponse.json({ status: 'ok' })
        }),
      )

      renderReview()

      await waitFor(() => {
        expect(screen.getAllByText('review_doc_1.pdf').length).toBeGreaterThanOrEqual(1)
      })

      await user.click(screen.getByRole('button', { name: /Reject/i }))

      await waitFor(() => {
        expect(screen.getByText('Reject Document')).toBeInTheDocument()
      })

      // Confirm without typing reason
      await user.click(
        screen.getByRole('button', { name: /Confirm Rejection/i }),
      )

      await waitFor(() => {
        expect(capturedBody).not.toBeNull()
      })

      expect(capturedBody).toEqual(
        expect.objectContaining({
          action: 'reject',
          review_notes: 'No reason provided',
        }),
      )
    })

    it('cancel button closes the rejection dialog', async () => {
      const user = userEvent.setup()
      renderReview()

      await waitFor(() => {
        expect(screen.getAllByText('review_doc_1.pdf').length).toBeGreaterThanOrEqual(1)
      })

      await user.click(screen.getByRole('button', { name: /Reject/i }))

      await waitFor(() => {
        expect(screen.getByText('Reject Document')).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /Cancel/i }))

      await waitFor(() => {
        expect(screen.queryByText('Reject Document')).not.toBeInTheDocument()
      })
    })
  })

  describe('AC9: Empty queue shows "No documents waiting" state', () => {
    it('shows empty state when no documents need review', async () => {
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

      renderReview()

      await waitFor(() => {
        expect(
          screen.getByText('No documents waiting for review'),
        ).toBeInTheDocument()
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

      renderReview()

      await waitFor(() => {
        expect(
          screen.getByRole('button', { name: /Upload Document/i }),
        ).toBeInTheDocument()
      })
    })
  })
})
