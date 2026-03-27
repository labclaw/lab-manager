import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { BarcodeScanner } from '@/components/BarcodeScanner'

// Mock html5-qrcode module — vi.mock is hoisted, so we use vi.hoisted()
const { mockStart, mockStop, mockGetState, MockHtml5Qrcode } = vi.hoisted(() => {
  const mockStart = vi.fn()
  const mockStop = vi.fn()
  const mockGetState = vi.fn().mockReturnValue(1) // NOT_STARTED

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

describe('BarcodeScanner', () => {
  const onScan = vi.fn()
  const onError = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    mockStart.mockResolvedValue(undefined)
    mockStop.mockResolvedValue(undefined)
  })

  it('renders start button initially', () => {
    renderWithProviders(<BarcodeScanner onScan={onScan} />)
    expect(screen.getByText('Start Scanner')).toBeInTheDocument()
  })

  it('renders placeholder text before scanning', () => {
    renderWithProviders(<BarcodeScanner onScan={onScan} />)
    expect(screen.getByText('Tap Start to begin scanning')).toBeInTheDocument()
  })

  it('starts scanner on button click and shows stop button', async () => {
    const user = userEvent.setup()
    renderWithProviders(<BarcodeScanner onScan={onScan} />)

    await user.click(screen.getByText('Start Scanner'))

    await waitFor(() => {
      expect(mockStart).toHaveBeenCalledTimes(1)
    })

    expect(screen.getByText('Stop Scanner')).toBeInTheDocument()
  })

  it('passes decoded value to onScan callback', async () => {
    // Capture the success callback passed to start()
    mockStart.mockImplementation(
      (_config: unknown, _prefs: unknown, onSuccess: (text: string) => void) => {
        // Simulate a barcode decode
        setTimeout(() => onSuccess('S1234'), 10)
        return Promise.resolve()
      },
    )

    const user = userEvent.setup()
    renderWithProviders(<BarcodeScanner onScan={onScan} />)

    await user.click(screen.getByText('Start Scanner'))

    await waitFor(() => {
      expect(onScan).toHaveBeenCalledWith('S1234')
    })
  })

  it('shows decoded value overlay after scan', async () => {
    mockStart.mockImplementation(
      (_config: unknown, _prefs: unknown, onSuccess: (text: string) => void) => {
        setTimeout(() => onSuccess('E5678'), 10)
        return Promise.resolve()
      },
    )

    const user = userEvent.setup()
    renderWithProviders(<BarcodeScanner onScan={onScan} />)

    await user.click(screen.getByText('Start Scanner'))

    await waitFor(() => {
      expect(screen.getByText('Scanned: E5678')).toBeInTheDocument()
    })
  })

  it('handles camera permission denied gracefully', async () => {
    mockStart.mockRejectedValue(new Error('NotAllowedError: Permission denied'))

    const user = userEvent.setup()
    renderWithProviders(<BarcodeScanner onScan={onScan} onError={onError} />)

    await user.click(screen.getByText('Start Scanner'))

    await waitFor(() => {
      expect(
        screen.getByText(
          'Camera permission denied. Please allow camera access in your browser settings.',
        ),
      ).toBeInTheDocument()
    })

    expect(onError).toHaveBeenCalledWith(
      'Camera permission denied. Please allow camera access in your browser settings.',
    )
  })

  it('handles generic camera error', async () => {
    mockStart.mockRejectedValue(new Error('Device not found'))

    const user = userEvent.setup()
    renderWithProviders(<BarcodeScanner onScan={onScan} onError={onError} />)

    await user.click(screen.getByText('Start Scanner'))

    await waitFor(() => {
      expect(screen.getByText('Camera error: Device not found')).toBeInTheDocument()
    })
  })

  it('stops scanner when stop button is clicked', async () => {
    mockGetState.mockReturnValue(2) // SCANNING

    const user = userEvent.setup()
    renderWithProviders(<BarcodeScanner onScan={onScan} />)

    await user.click(screen.getByText('Start Scanner'))

    await waitFor(() => {
      expect(screen.getByText('Stop Scanner')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Stop Scanner'))

    await waitFor(() => {
      expect(screen.getByText('Start Scanner')).toBeInTheDocument()
    })
  })
})
