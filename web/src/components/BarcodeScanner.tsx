import { useEffect, useRef, useState, useCallback } from 'react'
import { Html5Qrcode, Html5QrcodeSupportedFormats } from 'html5-qrcode'
import { Camera, CameraOff, AlertCircle } from 'lucide-react'

interface BarcodeScannerProps {
  readonly onScan: (value: string) => void
  readonly onError?: (error: string) => void
}

const SUPPORTED_FORMATS = [
  Html5QrcodeSupportedFormats.QR_CODE,
  Html5QrcodeSupportedFormats.CODE_128,
  Html5QrcodeSupportedFormats.CODE_39,
  Html5QrcodeSupportedFormats.EAN_13,
  Html5QrcodeSupportedFormats.EAN_8,
  Html5QrcodeSupportedFormats.UPC_A,
  Html5QrcodeSupportedFormats.UPC_E,
]

const READER_ID = 'barcode-reader'

export function BarcodeScanner({ onScan, onError }: BarcodeScannerProps) {
  const [scanning, setScanning] = useState(false)
  const [lastResult, setLastResult] = useState<string | null>(null)
  const [permissionError, setPermissionError] = useState<string | null>(null)
  const scannerRef = useRef<Html5Qrcode | null>(null)
  const mountedRef = useRef(true)

  const stopScanner = useCallback(async () => {
    if (scannerRef.current) {
      try {
        const state = scannerRef.current.getState()
        // State 2 = SCANNING
        if (state === 2) {
          await scannerRef.current.stop()
        }
      } catch {
        // Ignore stop errors during cleanup
      }
      scannerRef.current = null
    }
    if (mountedRef.current) {
      setScanning(false)
    }
  }, [])

  const startScanner = useCallback(async () => {
    setPermissionError(null)
    setLastResult(null)

    try {
      const scanner = new Html5Qrcode(READER_ID, {
        formatsToSupport: SUPPORTED_FORMATS,
        verbose: false,
      })
      scannerRef.current = scanner

      await scanner.start(
        { facingMode: 'environment' },
        {
          fps: 10,
          qrbox: { width: 250, height: 250 },
          aspectRatio: 1.0,
        },
        (decodedText) => {
          if (mountedRef.current) {
            setLastResult(decodedText)
            onScan(decodedText)
          }
        },
        () => {
          // Scan failure on individual frame — ignore
        },
      )

      if (mountedRef.current) {
        setScanning(true)
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Camera access denied'

      const isPermission =
        message.includes('NotAllowedError') ||
        message.includes('Permission') ||
        message.includes('denied')

      const displayMsg = isPermission
        ? 'Camera permission denied. Please allow camera access in your browser settings.'
        : `Camera error: ${message}`

      if (mountedRef.current) {
        setPermissionError(displayMsg)
      }
      onError?.(displayMsg)
    }
  }, [onScan, onError])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      stopScanner()
    }
  }, [stopScanner])

  const handleToggle = () => {
    if (scanning) {
      stopScanner()
    } else {
      startScanner()
    }
  }

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Camera viewport */}
      <div className="relative w-full max-w-md aspect-square bg-black/5 rounded-xl overflow-hidden border border-primary/10">
        <div id={READER_ID} className="w-full h-full" />
        {!scanning && !permissionError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-[var(--muted-foreground)]">
            <Camera className="size-12 opacity-40" />
            <p className="text-sm">Tap Start to begin scanning</p>
          </div>
        )}
      </div>

      {/* Permission error */}
      {permissionError && (
        <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 text-red-500 text-sm max-w-md w-full">
          <AlertCircle className="size-5 shrink-0 mt-0.5" />
          <p>{permissionError}</p>
        </div>
      )}

      {/* Last scan result overlay */}
      {lastResult && (
        <div className="p-3 rounded-lg bg-emerald-500/10 text-emerald-600 text-sm font-mono max-w-md w-full text-center">
          Scanned: {lastResult}
        </div>
      )}

      {/* Controls */}
      <button
        onClick={handleToggle}
        className={`flex items-center gap-2 px-6 py-3 rounded-lg font-medium text-sm transition-colors ${
          scanning
            ? 'bg-red-500/10 text-red-500 hover:bg-red-500/20'
            : 'bg-primary/10 text-primary hover:bg-primary/20'
        }`}
      >
        {scanning ? (
          <>
            <CameraOff className="size-5" />
            Stop Scanner
          </>
        ) : (
          <>
            <Camera className="size-5" />
            Start Scanner
          </>
        )}
      </button>
    </div>
  )
}
