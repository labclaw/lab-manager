import { useState, useRef, useCallback } from 'react'
import { documents } from '@/lib/api'
import type { Document } from '@/lib/api'
import { Upload, Camera, FileText, CheckCircle2, XCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const ACCEPTED_TYPES = new Set(['image/png', 'image/jpeg', 'image/tiff', 'application/pdf'])
const MAX_BYTES = 50 * 1024 * 1024

interface UploadRecord {
  name: string
  size: number
  doc?: Document
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function UploadPage() {
  const [dragOver, setDragOver] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState<'success' | 'error' | null>(null)
  const [uploadError, setUploadError] = useState('')
  const [validationError, setValidationError] = useState('')
  const [history, setHistory] = useState<UploadRecord[]>([])
  const fileRef = useRef<HTMLInputElement>(null)
  const cameraRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  const validateAndSelect = useCallback((file: File) => {
    if (!ACCEPTED_TYPES.has(file.type)) {
      setValidationError(`Unsupported file type: ${file.type || 'unknown'}. Use PNG, JPEG, TIFF, or PDF.`)
      setSelectedFile(null)
      setPreview(null)
      return
    }
    if (file.size > MAX_BYTES) {
      setValidationError(`File too large (${fmtSize(file.size)}). Maximum is 50 MB.`)
      setSelectedFile(null)
      setPreview(null)
      return
    }
    setSelectedFile(file)
    setUploadResult(null)
    setUploadError('')
    setValidationError('')
    if (file.type.startsWith('image/')) {
      const reader = new FileReader()
      reader.onload = (e) => setPreview(e.target?.result as string)
      reader.readAsDataURL(file)
    } else {
      setPreview(null)
    }
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) validateAndSelect(file)
  }, [validateAndSelect])

  const handleUpload = async () => {
    if (!selectedFile) return
    setUploading(true)
    setUploadResult(null)
    try {
      const doc = await documents.upload(selectedFile)
      setHistory(prev => [{ name: selectedFile.name, size: selectedFile.size, doc }, ...prev])
      setUploadResult('success')
      setTimeout(() => {
        setSelectedFile(null)
        setPreview(null)
        setUploadResult(null)
      }, 3000)
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed')
      setUploadResult('error')
    } finally {
      setUploading(false)
    }
  }

  const resetSelection = () => {
    setSelectedFile(null)
    setPreview(null)
    setUploadResult(null)
    setUploadError('')
    setValidationError('')
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h2 className="text-lg font-display font-semibold text-[var(--foreground)]">Upload Document</h2>
        <p className="text-sm text-[var(--muted-foreground)] mt-1">Upload packing lists, invoices, or certificates for AI extraction.</p>
      </div>

      {/* Validation error */}
      {validationError && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-[var(--destructive)]/10 border border-[var(--destructive)]/30 text-sm text-[var(--destructive)]">
          <XCircle className="w-4 h-4 shrink-0" />
          {validationError}
        </div>
      )}

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
        className={`card cursor-pointer border-2 border-dashed text-center py-12 transition-colors ${
          dragOver ? 'border-[var(--primary)] bg-[var(--primary)]/5' : 'border-[var(--border)]'
        }`}
      >
        <Upload className="w-10 h-10 text-[var(--muted-foreground)] mx-auto mb-3" />
        <p className="text-sm font-medium text-[var(--foreground)]">Drop a file here or click to browse</p>
        <p className="text-xs text-[var(--muted-foreground)] mt-1">PNG, JPEG, TIFF, or PDF — max 50 MB</p>
        <div className="flex items-center justify-center gap-3 mt-4">
          <button
            onClick={(e) => { e.stopPropagation(); cameraRef.current?.click() }}
            className="btn-secondary flex items-center gap-2 text-sm"
          >
            <Camera className="w-4 h-4" /> Take Photo
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); fileRef.current?.click() }}
            className="btn-secondary flex items-center gap-2 text-sm"
          >
            <FileText className="w-4 h-4" /> Choose File
          </button>
        </div>
      </div>

      <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/tiff,application/pdf" className="hidden"
        aria-label="Choose file to upload"
        onChange={(e) => { if (e.target.files?.[0]) validateAndSelect(e.target.files[0]); e.target.value = '' }} />
      <input ref={cameraRef} type="file" accept="image/*" capture="environment" className="hidden"
        aria-label="Take photo to upload"
        onChange={(e) => { if (e.target.files?.[0]) validateAndSelect(e.target.files[0]); e.target.value = '' }} />

      {/* Preview */}
      {selectedFile && (
        <div className="card">
          <div className="flex items-start gap-4">
            <div className="w-20 h-20 rounded-lg bg-[var(--muted)] border border-[var(--border)] flex items-center justify-center overflow-hidden shrink-0">
              {preview ? (
                <img src={preview} alt="preview" className="w-full h-full object-cover" />
              ) : (
                <FileText className="w-8 h-8 text-[var(--muted-foreground)]" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-[var(--foreground)] truncate">{selectedFile.name}</p>
              <p className="text-xs text-[var(--muted-foreground)] mt-0.5">{fmtSize(selectedFile.size)}</p>
              <div className="mt-3">
                {uploadResult === 'success' ? (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-sm text-[var(--accent)]">
                      <CheckCircle2 className="w-4 h-4" /> Uploaded successfully
                    </div>
                    <button onClick={() => navigate('/review')} className="text-xs text-[var(--primary)] hover:underline">
                      Go to review queue
                    </button>
                  </div>
                ) : uploadResult === 'error' ? (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-sm text-[var(--destructive)]">
                      <XCircle className="w-4 h-4" /> {uploadError}
                    </div>
                    <button onClick={handleUpload} className="btn-primary text-sm">Retry</button>
                  </div>
                ) : (
                  <button onClick={handleUpload} disabled={uploading} className="btn-primary flex items-center gap-2 text-sm">
                    {uploading ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Uploading...
                      </>
                    ) : (
                      <>
                        <Upload className="w-4 h-4" /> Upload
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
            <button onClick={resetSelection} aria-label="Remove selected file" className="text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors p-1">
              <XCircle className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      {/* Session history */}
      {history.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-[var(--foreground)]">This Session</h3>
          {history.slice(0, 10).map((rec, i) => (
            <div key={i} className="flex items-center gap-3 px-3 py-2 bg-[var(--muted)] rounded-lg border border-[var(--border)]">
              <CheckCircle2 className="w-4 h-4 text-[var(--accent)] shrink-0" />
              <span className="text-xs text-[var(--foreground)] flex-1 truncate">{rec.name}</span>
              <span className="text-xs text-[var(--muted-foreground)]">{fmtSize(rec.size)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
