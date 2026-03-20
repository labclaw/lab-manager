import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { renderWithProviders } from '@/test/utils'
import { UploadPage } from '@/pages/UploadPage'

function renderUpload() {
  return renderWithProviders(<UploadPage />, {
    initialEntries: ['/upload'],
  })
}

function createMockFile(name: string, size: number, type: string): File {
  const content = new ArrayBuffer(size)
  return new File([content], name, { type })
}

describe('UploadPage', () => {
  describe('AC1: File input accepts files', () => {
    it('renders the file input element', () => {
      renderUpload()

      const fileInput = screen.getByLabelText('Choose files to upload')
      expect(fileInput).toBeInTheDocument()
      expect(fileInput).toHaveAttribute(
        'accept',
        'image/png,image/jpeg,image/heic,image/tiff,application/pdf',
      )
    })

    it('renders Browse Files button', () => {
      renderUpload()

      expect(
        screen.getByRole('button', { name: /Browse Files/i }),
      ).toBeInTheDocument()
    })

    it('renders drag and drop zone text', () => {
      renderUpload()

      expect(screen.getByText(/Drag & drop files here/i)).toBeInTheDocument()
    })

    it('accepts a file through the file input', async () => {
      const user = userEvent.setup()
      renderUpload()

      const file = createMockFile('test_invoice.pdf', 1024, 'application/pdf')
      const fileInput = screen.getByLabelText('Choose files to upload')

      await user.upload(fileInput, file)

      await waitFor(() => {
        expect(screen.getByText('test_invoice.pdf')).toBeInTheDocument()
      })
    })
  })

  describe('AC2: Upload button triggers POST /documents/upload', () => {
    it('sends file to upload endpoint when file is selected', async () => {
      const user = userEvent.setup()
      let uploadCalled = false

      server.use(
        http.post('/api/v1/documents/upload', () => {
          uploadCalled = true
          return HttpResponse.json({
            id: 99,
            filename: 'test_invoice.pdf',
            vendor_name: 'TestVendor',
            document_type: 'invoice',
            status: 'pending',
          })
        }),
      )

      renderUpload()

      const file = createMockFile('test_invoice.pdf', 1024, 'application/pdf')
      const fileInput = screen.getByLabelText('Choose files to upload')

      await user.upload(fileInput, file)

      await waitFor(() => {
        expect(uploadCalled).toBe(true)
      })
    })

    it('shows completed status after successful upload', async () => {
      const user = userEvent.setup()

      server.use(
        http.post('/api/v1/documents/upload', () => {
          return HttpResponse.json({
            id: 99,
            file_name: 'test_invoice.pdf',
            vendor_name: 'TestVendor',
            document_type: 'invoice',
            status: 'needs_review',
            extraction_confidence: 0.85,
          })
        }),
      )

      renderUpload()

      const file = createMockFile('test_invoice.pdf', 1024, 'application/pdf')
      const fileInput = screen.getByLabelText('Choose files to upload')

      await user.upload(fileInput, file)

      await waitFor(() => {
        expect(screen.getByText('Complete')).toBeInTheDocument()
      })
    })
  })

  describe('AC3: Upload progress/status shown', () => {
    it('shows upload session section after file is added', async () => {
      const user = userEvent.setup()
      renderUpload()

      const file = createMockFile('test_doc.pdf', 2048, 'application/pdf')
      const fileInput = screen.getByLabelText('Choose files to upload')

      await user.upload(fileInput, file)

      await waitFor(() => {
        expect(screen.getByText('Upload Session')).toBeInTheDocument()
      })
    })

    it('shows file count badge', async () => {
      const user = userEvent.setup()
      renderUpload()

      const file = createMockFile('test_doc.pdf', 2048, 'application/pdf')
      const fileInput = screen.getByLabelText('Choose files to upload')

      await user.upload(fileInput, file)

      await waitFor(() => {
        expect(screen.getByText('1 Files')).toBeInTheDocument()
      })
    })

    it('shows file name in the upload list', async () => {
      const user = userEvent.setup()
      renderUpload()

      const file = createMockFile('my_packing_list.pdf', 5000, 'application/pdf')
      const fileInput = screen.getByLabelText('Choose files to upload')

      await user.upload(fileInput, file)

      await waitFor(() => {
        expect(screen.getByText('my_packing_list.pdf')).toBeInTheDocument()
      })
    })

    it('shows progress bar during upload', async () => {
      const user = userEvent.setup()

      // Delay the response to keep the upload in progress state
      server.use(
        http.post('/api/v1/documents/upload', async () => {
          await new Promise((r) => setTimeout(r, 5000))
          return HttpResponse.json({ id: 99, filename: 'test.pdf', status: 'pending' })
        }),
      )

      renderUpload()

      const file = createMockFile('test.pdf', 2048, 'application/pdf')
      const fileInput = screen.getByLabelText('Choose files to upload')

      await user.upload(fileInput, file)

      // The progress bar should appear while uploading
      await waitFor(() => {
        const progressBar = screen.queryByRole('progressbar')
        const uploadingTexts = screen.queryAllByText('Uploading...')
        // Either progressbar or uploading text or processing text should be present
        expect(
          progressBar || uploadingTexts.length > 0 || screen.queryByText(/Processing AI/i),
        ).toBeTruthy()
      })
    })

    it('shows completed files count in the bottom bar', async () => {
      const user = userEvent.setup()

      server.use(
        http.post('/api/v1/documents/upload', () => {
          return HttpResponse.json({
            id: 99,
            file_name: 'invoice.pdf',
            vendor_name: 'TestVendor',
            document_type: 'invoice',
            status: 'needs_review',
            extraction_confidence: 0.85,
          })
        }),
      )

      renderUpload()

      const file = createMockFile('invoice.pdf', 1024, 'application/pdf')
      const fileInput = screen.getByLabelText('Choose files to upload')

      await user.upload(fileInput, file)

      await waitFor(() => {
        expect(screen.getByText(/1 of 1 files processed/i)).toBeInTheDocument()
      })
    })
  })

  describe('AC4: Error states displayed', () => {
    it('shows failed status when upload fails', async () => {
      const user = userEvent.setup()

      server.use(
        http.post('/api/v1/documents/upload', () => {
          return HttpResponse.json(
            { detail: 'Server error' },
            { status: 500 },
          )
        }),
      )

      renderUpload()

      const file = createMockFile('bad_file.pdf', 1024, 'application/pdf')
      const fileInput = screen.getByLabelText('Choose files to upload')

      await user.upload(fileInput, file)

      await waitFor(() => {
        expect(screen.getByText('Failed')).toBeInTheDocument()
      })
    })

    it('shows error message from server', async () => {
      const user = userEvent.setup()

      server.use(
        http.post('/api/v1/documents/upload', () => {
          return HttpResponse.json(
            { detail: 'Unsupported file format' },
            { status: 400 },
          )
        }),
      )

      renderUpload()

      const file = createMockFile('bad_file.pdf', 1024, 'application/pdf')
      const fileInput = screen.getByLabelText('Choose files to upload')

      await user.upload(fileInput, file)

      await waitFor(() => {
        expect(
          screen.getByText('Unsupported file format'),
        ).toBeInTheDocument()
      })
    })

    it('silently ignores files with unsupported MIME types', async () => {
      const user = userEvent.setup()
      renderUpload()

      const file = createMockFile('readme.txt', 100, 'text/plain')
      const fileInput = screen.getByLabelText('Choose files to upload')

      await user.upload(fileInput, file)

      // Should not show upload session since file type is rejected
      await vi.advanceTimersByTimeAsync?.(100).catch(() => {})
      expect(screen.queryByText('Upload Session')).not.toBeInTheDocument()
    })
  })
})
