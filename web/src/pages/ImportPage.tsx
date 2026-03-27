import { useState, useRef, useCallback } from 'react'
import {
  Upload,
  FileSpreadsheet,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Download,
} from 'lucide-react'

const BASE = '/api/v1'

type EntityType = 'vendors' | 'products' | 'inventory'

interface ImportError {
  row: number
  field: string
  message: string
}

interface ImportResult {
  imported: number
  errors: ImportError[]
  skipped: number
}

const ENTITY_OPTIONS: { value: EntityType; label: string; description: string }[] = [
  { value: 'vendors', label: 'Vendors', description: 'Supplier/vendor records' },
  { value: 'products', label: 'Products', description: 'Product catalog items' },
  { value: 'inventory', label: 'Inventory', description: 'Inventory stock items' },
]

const REQUIRED_COLUMNS: Record<EntityType, string[]> = {
  vendors: ['name'],
  products: ['catalog_number', 'name'],
  inventory: ['product_id', 'quantity_on_hand'],
}

const SAMPLE_HEADERS: Record<EntityType, string[]> = {
  vendors: ['name', 'website', 'phone', 'email', 'notes'],
  products: ['catalog_number', 'name', 'vendor_id', 'category', 'cas_number', 'storage_temp', 'unit', 'hazard_info', 'min_stock_level', 'is_hazardous', 'is_controlled'],
  inventory: ['product_id', 'location_id', 'lot_number', 'quantity_on_hand', 'unit', 'expiry_date', 'opened_date', 'status', 'notes', 'received_by'],
}

function parseCSVPreview(text: string, maxRows = 5): { headers: string[]; rows: string[][] } {
  const lines = text.split(/\r?\n/).filter((l) => l.trim())
  if (lines.length === 0) return { headers: [], rows: [] }
  // Simple CSV parse (handles quoted fields with commas)
  const parseLine = (line: string): string[] => {
    const result: string[] = []
    let current = ''
    let inQuotes = false
    for (let i = 0; i < line.length; i++) {
      const ch = line[i]
      if (ch === '"') {
        if (inQuotes && i + 1 < line.length && line[i + 1] === '"') {
          current += '"'
          i++
        } else {
          inQuotes = !inQuotes
        }
      } else if (ch === ',' && !inQuotes) {
        result.push(current.trim())
        current = ''
      } else {
        current += ch
      }
    }
    result.push(current.trim())
    return result
  }
  const headers = parseLine(lines[0])
  const rows = lines.slice(1, 1 + maxRows).map(parseLine)
  return { headers, rows }
}

interface ImportPageProps {
  readonly onError?: (msg: string) => void
}

export function ImportPage({ onError }: ImportPageProps) {
  const [entityType, setEntityType] = useState<EntityType>('vendors')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<{ headers: string[]; rows: string[][] } | null>(null)
  const [totalRows, setTotalRows] = useState(0)
  const [importing, setImporting] = useState(false)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback((f: File | null) => {
    if (!f) return
    setFile(f)
    setResult(null)
    const reader = new FileReader()
    reader.onload = (e) => {
      const text = e.target?.result as string
      const { headers, rows } = parseCSVPreview(text)
      const allLines = text.split(/\r?\n/).filter((l) => l.trim())
      setTotalRows(Math.max(0, allLines.length - 1))
      setPreview({ headers, rows })
    }
    reader.readAsText(f)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f && (f.name.endsWith('.csv') || f.type === 'text/csv')) {
      handleFile(f)
    }
  }, [handleFile])

  const handleImport = useCallback(async () => {
    if (!file) return
    setImporting(true)
    setResult(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${BASE}/import/${entityType}/`, {
        method: 'POST',
        body: form,
      })
      if (res.status === 401) {
        onError?.('Authentication required')
        return
      }
      const data: ImportResult = await res.json()
      setResult(data)
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Import failed')
    } finally {
      setImporting(false)
    }
  }, [file, entityType, onError])

  const downloadTemplate = useCallback(() => {
    const headers = SAMPLE_HEADERS[entityType]
    const csv = headers.join(',') + '\n'
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${entityType}_template.csv`
    a.click()
    URL.revokeObjectURL(url)
  }, [entityType])

  const reset = useCallback(() => {
    setFile(null)
    setPreview(null)
    setResult(null)
    setTotalRows(0)
  }, [])

  const requiredCols = REQUIRED_COLUMNS[entityType]

  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-[var(--foreground)]">Bulk Import</h2>
        <p className="text-sm text-[var(--muted-foreground)] mt-1">
          Import data from CSV files. Use the same format as CSV exports for round-trip compatibility.
        </p>
      </div>

      {/* Entity Type Selector */}
      <div className="bg-[var(--card)] rounded-xl border border-[var(--border)] p-6">
        <h3 className="text-sm font-bold text-[var(--foreground)] mb-3">Data Type</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {ENTITY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => { setEntityType(opt.value); reset() }}
              className={`p-4 rounded-lg border-2 text-left transition-all ${
                entityType === opt.value
                  ? 'border-primary bg-primary/5'
                  : 'border-[var(--border)] hover:border-primary/30'
              }`}
            >
              <p className={`text-sm font-bold ${entityType === opt.value ? 'text-primary' : 'text-[var(--foreground)]'}`}>
                {opt.label}
              </p>
              <p className="text-xs text-[var(--muted-foreground)] mt-0.5">{opt.description}</p>
            </button>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-4">
          <p className="text-xs text-[var(--muted-foreground)]">
            Required columns: <span className="font-mono font-bold text-[var(--foreground)]">{requiredCols.join(', ')}</span>
          </p>
          <button
            onClick={downloadTemplate}
            className="text-xs text-primary hover:underline font-semibold flex items-center gap-1"
          >
            <Download className="size-3" />
            Download template
          </button>
        </div>
      </div>

      {/* File Upload */}
      {!result && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileRef.current?.click()}
          className={`bg-[var(--card)] rounded-xl border-2 border-dashed p-12 text-center cursor-pointer transition-all ${
            dragOver ? 'border-primary bg-primary/5' : 'border-[var(--border)] hover:border-primary/50'
          }`}
        >
          <div className="size-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
            <FileSpreadsheet className="text-primary size-6" />
          </div>
          {file ? (
            <>
              <p className="font-bold text-[var(--foreground)]">{file.name}</p>
              <p className="text-sm text-[var(--muted-foreground)] mt-1">
                {totalRows} data rows detected
              </p>
              <button
                onClick={(e) => { e.stopPropagation(); reset() }}
                className="mt-3 text-sm text-primary hover:underline font-semibold"
              >
                Choose different file
              </button>
            </>
          ) : (
            <>
              <p className="font-bold text-[var(--foreground)]">Drop CSV file here or click to browse</p>
              <p className="text-sm text-[var(--muted-foreground)] mt-1">CSV files only, max 10 MB</p>
            </>
          )}
        </div>
      )}

      <input
        ref={fileRef}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        aria-label="Choose CSV file to import"
        onChange={(e) => { handleFile(e.target.files?.[0] ?? null); e.target.value = '' }}
      />

      {/* Preview Table */}
      {preview && !result && preview.headers.length > 0 && (
        <div className="bg-[var(--card)] rounded-xl border border-[var(--border)] overflow-hidden">
          <div className="px-6 py-4 border-b border-[var(--border)] flex items-center justify-between">
            <h3 className="text-sm font-bold text-[var(--foreground)]">
              Preview (first {Math.min(preview.rows.length, 5)} of {totalRows} rows)
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[var(--background)]">
                  <th className="px-4 py-2.5 text-left text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider">
                    Row
                  </th>
                  {preview.headers.map((h) => (
                    <th
                      key={h}
                      className={`px-4 py-2.5 text-left text-xs font-bold uppercase tracking-wider ${
                        requiredCols.includes(h) ? 'text-primary' : 'text-[var(--muted-foreground)]'
                      }`}
                    >
                      {h}{requiredCols.includes(h) ? ' *' : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {preview.rows.map((row, ri) => (
                  <tr key={ri} className="hover:bg-white/5">
                    <td className="px-4 py-2 text-[var(--muted-foreground)] font-mono text-xs">{ri + 2}</td>
                    {preview.headers.map((_, ci) => (
                      <td key={ci} className="px-4 py-2 text-[var(--foreground)] truncate max-w-[200px]">
                        {row[ci] ?? ''}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Import Button */}
      {file && !result && (
        <div className="flex justify-end">
          <button
            onClick={handleImport}
            disabled={importing}
            className="px-8 py-2.5 bg-primary hover:bg-primary/90 text-white font-bold rounded-lg shadow-lg shadow-primary/20 transition-all flex items-center gap-2 disabled:opacity-50"
          >
            {importing ? (
              <>
                <div className="size-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Importing...
              </>
            ) : (
              <>
                <Upload className="size-4" />
                Import {totalRows} rows
              </>
            )}
          </button>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="bg-[var(--card)] rounded-xl border border-[var(--border)] overflow-hidden">
          <div className="p-6">
            {/* Success summary */}
            {result.imported > 0 && (
              <div className="flex items-center gap-3 mb-4 p-4 rounded-lg bg-accent-green/10">
                <CheckCircle className="size-6 text-accent-green shrink-0" />
                <div>
                  <p className="font-bold text-accent-green">
                    Successfully imported {result.imported} {entityType}
                  </p>
                  {result.skipped > 0 && (
                    <p className="text-sm text-[var(--muted-foreground)] mt-0.5">
                      {result.skipped} duplicate rows skipped
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Skipped only (no imports, no errors) */}
            {result.imported === 0 && result.errors.length === 0 && result.skipped > 0 && (
              <div className="flex items-center gap-3 mb-4 p-4 rounded-lg bg-yellow-500/10">
                <AlertTriangle className="size-6 text-yellow-500 shrink-0" />
                <p className="font-bold text-yellow-500">
                  All {result.skipped} rows were duplicates -- nothing imported
                </p>
              </div>
            )}

            {/* Errors */}
            {result.errors.length > 0 && (
              <div className="mb-4">
                <div className="flex items-center gap-3 p-4 rounded-lg bg-[#FF6B6B]/10 mb-3">
                  <XCircle className="size-6 text-[#FF6B6B] shrink-0" />
                  <p className="font-bold text-[#FF6B6B]">
                    {result.errors.length} validation error{result.errors.length > 1 ? 's' : ''} -- nothing was imported
                  </p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-[var(--background)]">
                        <th className="px-4 py-2.5 text-left text-xs font-bold text-[var(--muted-foreground)] uppercase">Row</th>
                        <th className="px-4 py-2.5 text-left text-xs font-bold text-[var(--muted-foreground)] uppercase">Field</th>
                        <th className="px-4 py-2.5 text-left text-xs font-bold text-[var(--muted-foreground)] uppercase">Error</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border)]">
                      {result.errors.map((err, i) => (
                        <tr key={i} className="hover:bg-white/5">
                          <td className="px-4 py-2 font-mono text-[var(--muted-foreground)]">{err.row || '-'}</td>
                          <td className="px-4 py-2 font-mono text-[var(--foreground)]">{err.field || '-'}</td>
                          <td className="px-4 py-2 text-[#FF6B6B]">{err.message}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex items-center gap-3 mt-4">
              <button
                onClick={reset}
                className="px-6 py-2.5 bg-primary hover:bg-primary/90 text-white font-bold rounded-lg transition-all"
              >
                Import More
              </button>
              <a
                href={`${BASE}/export/${entityType}`}
                className="px-6 py-2.5 border border-[var(--border)] hover:border-primary text-[var(--foreground)] font-bold rounded-lg transition-all flex items-center gap-2"
              >
                <Download className="size-4" />
                Export {entityType} CSV
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
