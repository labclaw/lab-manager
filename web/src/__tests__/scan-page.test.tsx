import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { renderWithProviders } from '@/test/utils'
import { ScanPage } from '@/pages/ScanPage'

// Mock html5-qrcode — vi.mock is hoisted, so we use vi.hoisted()
const { mockStart, mockStop, mockGetState, MockHtml5Qrcode } = vi.hoisted(() => {
  const mockStart = vi.fn()
  const mockStop = vi.fn()
  const mockGetState = vi.fn().mockReturnValue(1)

  class MockHtml5Qrcode {
    constructor(_id: string, _config?: unknown) {
      // no-op
    }
    start = mockStart
    stop = mockStop
    getState = mockGetState
  }

  return { mockStart, mockStop, mockGetState, MockHtml5Qrcode }
})

vi.mock('html5-qrcode', () => ({
  Html5Qrcode: MockHtml5Qrcode,
  Html5QrcodeSupportedFormats: {
    QR_CODE: 0,
    CODE_128: 5,
    CODE_39: 6,
    EAN_13: 1,
    EAN_8: 2,
    UPC_A: 3,
    UPC_E: 4,
  },
}))

const onError = vi.fn()

describe('ScanPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockStart.mockResolvedValue(undefined)
    mockStop.mockResolvedValue(undefined)
  })

  it('renders page header with scan icon and title', () => {
    renderWithProviders(<ScanPage onError={onError} />, {
      initialEntries: ['/scan'],
    })

    expect(screen.getByText('Scan Barcode')).toBeInTheDocument()
    expect(
      screen.getByText('Scan a barcode or QR code to look up inventory'),
    ).toBeInTheDocument()
  })

  it('renders barcode scanner component', () => {
    renderWithProviders(<ScanPage onError={onError} />, {
      initialEntries: ['/scan'],
    })

    expect(screen.getByText('Start Scanner')).toBeInTheDocument()
  })

  it('shows search results after scanning a matching barcode', async () => {
    // Set up API handler for barcode lookup
    server.use(
      http.get('/api/v1/barcode/lookup', ({ request }) => {
        const url = new URL(request.url)
        const value = url.searchParams.get('value')
        if (value === 'S1234') {
          return HttpResponse.json({
            items: [
              {
                id: 1,
                product_id: 1,
                product_name: 'Sodium Chloride',
                product: {
                  id: 1,
                  name: 'Sodium Chloride',
                  catalog_number: 'S1234',
                  vendor: { id: 1, name: 'Sigma-Aldrich' },
                },
                lot_number: 'LOT-ABC',
                quantity_on_hand: 5,
                unit: 'kg',
                status: 'available',
                expiry_date: '2027-01-15',
              },
            ],
            total: 1,
            page: 1,
            page_size: 50,
            pages: 1,
            match_type: 'catalog_number_exact',
          })
        }
        return HttpResponse.json({
          items: [],
          total: 0,
          page: 1,
          page_size: 50,
          pages: 0,
          match_type: 'none',
        })
      }),
    )

    // Mock scanner to trigger scan immediately on start
    mockStart.mockImplementation(
      (
        _config: unknown,
        _prefs: unknown,
        onSuccess: (text: string) => void,
      ) => {
        setTimeout(() => onSuccess('S1234'), 10)
        return Promise.resolve()
      },
    )

    const user = userEvent.setup()
    renderWithProviders(<ScanPage onError={onError} />, {
      initialEntries: ['/scan'],
    })

    await user.click(screen.getByText('Start Scanner'))

    // Wait for search results
    await waitFor(() => {
      expect(screen.getByText('Sodium Chloride')).toBeInTheDocument()
    })

    // Check result details
    expect(screen.getByText('Exact catalog number match')).toBeInTheDocument()
    expect(screen.getByText('5 kg')).toBeInTheDocument()
    expect(screen.getByText('LOT-ABC')).toBeInTheDocument()
    expect(screen.getByText('View Details')).toBeInTheDocument()
    expect(screen.getByText('Log Consumption')).toBeInTheDocument()
    expect(screen.getByText('Scan Again')).toBeInTheDocument()
  })

  it('shows no match state when barcode is not found', async () => {
    server.use(
      http.get('/api/v1/barcode/lookup', () =>
        HttpResponse.json({
          items: [],
          total: 0,
          page: 1,
          page_size: 50,
          pages: 0,
          match_type: 'none',
        }),
      ),
    )

    mockStart.mockImplementation(
      (
        _config: unknown,
        _prefs: unknown,
        onSuccess: (text: string) => void,
      ) => {
        setTimeout(() => onSuccess('UNKNOWN-123'), 10)
        return Promise.resolve()
      },
    )

    const user = userEvent.setup()
    renderWithProviders(<ScanPage onError={onError} />, {
      initialEntries: ['/scan'],
    })

    await user.click(screen.getByText('Start Scanner'))

    await waitFor(() => {
      expect(screen.getByText('No Match Found')).toBeInTheDocument()
    })

    expect(screen.getByText('UNKNOWN-123')).toBeInTheDocument()
    expect(screen.getByText('Scan Again')).toBeInTheDocument()
    expect(screen.getByText('Add to Inventory')).toBeInTheDocument()
  })

  it('returns to scanner view when Scan Again is clicked', async () => {
    server.use(
      http.get('/api/v1/barcode/lookup', () =>
        HttpResponse.json({
          items: [],
          total: 0,
          page: 1,
          page_size: 50,
          pages: 0,
          match_type: 'none',
        }),
      ),
    )

    mockStart.mockImplementation(
      (
        _config: unknown,
        _prefs: unknown,
        onSuccess: (text: string) => void,
      ) => {
        setTimeout(() => onSuccess('TEST-999'), 10)
        return Promise.resolve()
      },
    )

    const user = userEvent.setup()
    renderWithProviders(<ScanPage onError={onError} />, {
      initialEntries: ['/scan'],
    })

    await user.click(screen.getByText('Start Scanner'))

    await waitFor(() => {
      expect(screen.getByText('No Match Found')).toBeInTheDocument()
    })

    // Reset mock so next start doesn't auto-scan
    mockStart.mockResolvedValue(undefined)

    await user.click(screen.getByText('Scan Again'))

    await waitFor(() => {
      expect(screen.getByText('Start Scanner')).toBeInTheDocument()
    })
  })

  it('shows partial match indicator', async () => {
    server.use(
      http.get('/api/v1/barcode/lookup', () =>
        HttpResponse.json({
          items: [
            {
              id: 2,
              product_id: 2,
              product_name: 'Ethanol 95%',
              product: {
                id: 2,
                name: 'Ethanol 95%',
                catalog_number: 'E5678',
                vendor: { id: 2, name: 'Fisher Scientific' },
              },
              lot_number: 'LOT-DEF',
              quantity_on_hand: 2,
              unit: 'L',
              status: 'low_stock',
            },
          ],
          total: 1,
          page: 1,
          page_size: 50,
          pages: 1,
          match_type: 'partial',
        }),
      ),
    )

    mockStart.mockImplementation(
      (
        _config: unknown,
        _prefs: unknown,
        onSuccess: (text: string) => void,
      ) => {
        setTimeout(() => onSuccess('E56'), 10)
        return Promise.resolve()
      },
    )

    const user = userEvent.setup()
    renderWithProviders(<ScanPage onError={onError} />, {
      initialEntries: ['/scan'],
    })

    await user.click(screen.getByText('Start Scanner'))

    await waitFor(() => {
      expect(screen.getByText('Partial match')).toBeInTheDocument()
    })
    expect(screen.getByText('Ethanol 95%')).toBeInTheDocument()
    expect(screen.getByText('low stock')).toBeInTheDocument()
  })

  it('calls onError when API request fails', async () => {
    server.use(
      http.get('/api/v1/barcode/lookup', () =>
        HttpResponse.json({ detail: 'Server error' }, { status: 500 }),
      ),
    )

    mockStart.mockImplementation(
      (
        _config: unknown,
        _prefs: unknown,
        onSuccess: (text: string) => void,
      ) => {
        setTimeout(() => onSuccess('ERR-1'), 10)
        return Promise.resolve()
      },
    )

    const user = userEvent.setup()
    renderWithProviders(<ScanPage onError={onError} />, {
      initialEntries: ['/scan'],
    })

    await user.click(screen.getByText('Start Scanner'))

    await waitFor(() => {
      expect(onError).toHaveBeenCalled()
    })
  })
})
