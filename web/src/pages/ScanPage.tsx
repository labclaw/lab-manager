import { useState, useCallback } from 'react'
import { BarcodeScanner } from '@/components/BarcodeScanner'
import { inventory, type InventoryItem } from '@/lib/api'
import {
  Package,
  Search,
  Beaker,
  Eye,
  Plus,
  Loader2,
  ScanBarcode,
} from 'lucide-react'

interface ScanPageProps {
  readonly onError?: (msg: string) => void
}

type ViewState = 'scan' | 'searching' | 'results' | 'no-match'

export function ScanPage({ onError }: ScanPageProps) {
  const [view, setView] = useState<ViewState>('scan')
  const [scannedValue, setScannedValue] = useState<string | null>(null)
  const [results, setResults] = useState<InventoryItem[]>([])
  const [matchType, setMatchType] = useState<string>('')

  const handleScan = useCallback(
    async (value: string) => {
      setScannedValue(value)
      setView('searching')

      try {
        const res = await inventory.barcodeLookup(value)
        const items = res.items ?? []
        setResults(items)
        setMatchType(res.match_type ?? '')
        setView(items.length > 0 ? 'results' : 'no-match')
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : 'Failed to search inventory'
        onError?.(msg)
        setView('no-match')
      }
    },
    [onError],
  )

  const handleScanError = useCallback(
    (msg: string) => {
      onError?.(msg)
    },
    [onError],
  )

  const handleScanAgain = () => {
    setScannedValue(null)
    setResults([])
    setMatchType('')
    setView('scan')
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="size-10 flex items-center justify-center bg-primary/10 rounded-lg">
          <ScanBarcode className="size-5 text-primary" />
        </div>
        <div>
          <h1 className="text-xl font-display font-bold text-[var(--foreground)]">
            Scan Barcode
          </h1>
          <p className="text-sm text-[var(--muted-foreground)]">
            Scan a barcode or QR code to look up inventory
          </p>
        </div>
      </div>

      {/* Scanner */}
      {view === 'scan' && (
        <BarcodeScanner onScan={handleScan} onError={handleScanError} />
      )}

      {/* Searching state */}
      {view === 'searching' && (
        <div className="flex flex-col items-center gap-4 py-12">
          <Loader2 className="size-8 text-primary animate-spin" />
          <p className="text-sm text-[var(--muted-foreground)]">
            Searching inventory for{' '}
            <span className="font-mono font-medium text-[var(--foreground)]">
              {scannedValue}
            </span>
          </p>
        </div>
      )}

      {/* Results */}
      {view === 'results' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-[var(--muted-foreground)]">
                Found{' '}
                <span className="font-semibold text-[var(--foreground)]">
                  {results.length}
                </span>{' '}
                item{results.length !== 1 ? 's' : ''} for{' '}
                <span className="font-mono text-primary">{scannedValue}</span>
              </p>
              {matchType === 'catalog_number_exact' && (
                <p className="text-xs text-emerald-600 mt-0.5">
                  Exact catalog number match
                </p>
              )}
              {matchType === 'partial' && (
                <p className="text-xs text-amber-600 mt-0.5">Partial match</p>
              )}
            </div>
            <button
              onClick={handleScanAgain}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary/10 text-primary text-sm font-medium hover:bg-primary/20 transition-colors"
            >
              <Search className="size-4" />
              Scan Again
            </button>
          </div>

          <div className="space-y-3">
            {results.map((item) => (
              <ScanResultCard key={item.id} item={item} />
            ))}
          </div>
        </div>
      )}

      {/* No match */}
      {view === 'no-match' && (
        <div className="flex flex-col items-center gap-4 py-12">
          <div className="size-16 flex items-center justify-center bg-amber-500/10 rounded-full">
            <Package className="size-8 text-amber-500" />
          </div>
          <div className="text-center space-y-1">
            <h3 className="text-lg font-semibold text-[var(--foreground)]">
              No Match Found
            </h3>
            <p className="text-sm text-[var(--muted-foreground)]">
              No inventory items match barcode{' '}
              <span className="font-mono font-medium">{scannedValue}</span>
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleScanAgain}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary/10 text-primary text-sm font-medium hover:bg-primary/20 transition-colors"
            >
              <Search className="size-4" />
              Scan Again
            </button>
            <a
              href="/inventory"
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-primary/10 text-sm font-medium text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
            >
              <Plus className="size-4" />
              Add to Inventory
            </a>
          </div>
        </div>
      )}
    </div>
  )
}

function ScanResultCard({ item }: { readonly item: InventoryItem }) {
  const productName = item.product_name ?? 'Unknown Item'
  const catalogNumber = item.catalog_number ?? '—'
  const vendorName = item.vendor_name ?? '—'
  const quantity = item.quantity_on_hand ?? 0
  const unit = item.unit ?? ''
  const status = item.status ?? 'unknown'
  const lotNumber = item.lot_number ?? '—'

  const statusColor =
    status === 'available'
      ? 'text-emerald-600 bg-emerald-500/10'
      : status === 'low_stock'
        ? 'text-amber-600 bg-amber-500/10'
        : status === 'out_of_stock'
          ? 'text-red-500 bg-red-500/10'
          : 'text-[var(--muted-foreground)] bg-primary/5'

  return (
    <div className="p-4 rounded-xl border border-primary/10 bg-[var(--card)] space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="font-semibold text-[var(--foreground)] truncate">
            {productName}
          </h4>
          <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
            {vendorName} &middot; {catalogNumber}
          </p>
        </div>
        <span
          className={`text-xs font-medium px-2 py-1 rounded-full shrink-0 ${statusColor}`}
        >
          {status.replace('_', ' ')}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3 text-sm">
        <div>
          <p className="text-[var(--muted-foreground)] text-xs">Stock</p>
          <p className="font-medium text-[var(--foreground)]">
            {quantity} {unit}
          </p>
        </div>
        <div>
          <p className="text-[var(--muted-foreground)] text-xs">Lot #</p>
          <p className="font-medium text-[var(--foreground)]">{lotNumber}</p>
        </div>
        <div>
          <p className="text-[var(--muted-foreground)] text-xs">Expiry</p>
          <p className="font-medium text-[var(--foreground)]">
            {item.expiry_date ?? '—'}
          </p>
        </div>
      </div>

      {/* Quick actions */}
      <div className="flex gap-2 pt-1">
        <a
          href={`/inventory?product_id=${item.product_id}`}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/10 text-primary text-xs font-medium hover:bg-primary/20 transition-colors"
        >
          <Eye className="size-3.5" />
          View Details
        </a>
        <button
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-600 text-xs font-medium hover:bg-emerald-500/20 transition-colors"
          title="Log consumption (coming soon)"
        >
          <Beaker className="size-3.5" />
          Log Consumption
        </button>
      </div>
    </div>
  )
}
