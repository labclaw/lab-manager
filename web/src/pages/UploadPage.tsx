import { useState, useRef, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { documents, type Document as AppDocument } from '@/lib/api'
import {
  CheckCircle,
  BrainCog,
  XCircle,
  RefreshCw,
  CloudUpload,
  Upload,
  Camera,
  FileImage,
  FileText,
  MoreVertical,
  X,
  CheckCheck,
  ArrowRight,
} from 'lucide-react'

const ACCEPTED_TYPES = new Set(['image/png', 'image/jpeg', 'image/heic', 'image/tiff', 'application/pdf'])
const MAX_BYTES = 10 * 1024 * 1024

type UploadStatus = 'queued' | 'uploading' | 'processing' | 'complete' | 'failed'

interface UploadRecord {
  id: number
  name: string
  size: number
  file: File
  status: UploadStatus
  progress: number
  doc?: AppDocument
  error?: string
  extractionInfo?: string
}

let nextId = 0

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function UploadPage() {
  const [dragOver, setDragOver] = useState(false)
  const [uploads, setUploads] = useState<UploadRecord[]>([])
  const fileRef = useRef<HTMLInputElement>(null)
  const cameraRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const intervalsRef = useRef<Set<ReturnType<typeof setInterval>>>(new Set())

  useEffect(() => {
    const intervals = intervalsRef.current
    return () => {
      for (const interval of intervals) {
        clearInterval(interval)
      }
      intervals.clear()
    }
  }, [])

  const pollDocument = useCallback((uploadId: number, docId: number) => {
    const interval = setInterval(async () => {
      try {
        const doc = await documents.get(docId)
        const finalStatuses = ['needs_review', 'extracted', 'approved', 'ocr_failed', 'rejected']
        if (finalStatuses.includes(doc.status ?? '')) {
          clearInterval(interval)
          intervalsRef.current.delete(interval)
          setUploads((prev) => prev.map((u) => u.id === uploadId ? {
            ...u,
            status: doc.status === 'ocr_failed' ? 'failed' : 'complete',
            progress: 100,
            doc,
            extractionInfo: [
              doc.vendor_name ?? 'Unknown vendor',
              doc.document_type ?? 'document',
              doc.extraction_confidence != null ? `${Math.round(doc.extraction_confidence * 100)}% conf.` : null,
            ].filter(Boolean).join(' | '),
            error: doc.status === 'ocr_failed' ? 'OCR processing failed' : undefined,
          } : u))
        } else {
          setUploads((prev) => prev.map((u) => u.id === uploadId ? {
            ...u,
            doc,
            extractionInfo: [
              doc.vendor_name || 'Processing...',
              doc.document_type || '',
              doc.extraction_confidence != null ? `${Math.round(doc.extraction_confidence * 100)}% conf.` : null,
            ].filter(Boolean).join(' | '),
          } : u))
        }
      } catch {
        // Swallow poll errors — the upload itself succeeded
      }
    }, 3000)
    intervalsRef.current.add(interval)
  }, [])

  const processFile = useCallback(async (file: File) => {
    if (!ACCEPTED_TYPES.has(file.type)) return
    if (file.size > MAX_BYTES) return

    const id = ++nextId
    const record: UploadRecord = {
      id,
      name: file.name,
      size: file.size,
      file,
      status: 'queued',
      progress: 0,
    }
    setUploads((prev) => [...prev, record])

    setUploads((prev) => prev.map((u) => u.id === id ? { ...u, status: 'uploading', progress: -1 } : u))

    try {
      const doc = await documents.upload(file)

      const finalStatuses = ['needs_review', 'extracted', 'approved', 'ocr_failed', 'rejected']
      if (finalStatuses.includes(doc.status ?? '')) {
        setUploads((prev) => prev.map((u) => u.id === id ? {
          ...u,
          status: doc.status === 'ocr_failed' ? 'failed' : 'complete',
          progress: 100,
          doc,
          extractionInfo: [
            doc.vendor_name ?? 'Unknown vendor',
            doc.document_type ?? 'document',
            doc.extraction_confidence != null ? `${Math.round(doc.extraction_confidence * 100)}% conf.` : null,
          ].filter(Boolean).join(' | '),
          error: doc.status === 'ocr_failed' ? 'OCR processing failed' : undefined,
        } : u))
      } else {
        setUploads((prev) => prev.map((u) => u.id === id ? {
          ...u,
          status: 'processing',
          progress: -1,
          doc,
          extractionInfo: doc.vendor_name ? `${doc.vendor_name} | Processing...` : 'Processing...',
        } : u))
        pollDocument(id, doc.id)
      }
    } catch (err) {
      setUploads((prev) => prev.map((u) => u.id === id ? {
        ...u,
        status: 'failed',
        error: err instanceof Error ? err.message : 'Upload failed',
      } : u))
    }
  }, [pollDocument])

  const handleFiles = useCallback((files: FileList | null) => {
    if (!files) return
    for (let i = 0; i < files.length; i++) {
      const f = files[i]
      if (f) processFile(f)
    }
  }, [processFile])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    handleFiles(e.dataTransfer.files)
  }, [handleFiles])

  const retryUpload = useCallback((record: UploadRecord) => {
    setUploads((prev) => prev.filter((u) => u.id !== record.id))
    processFile(record.file)
  }, [processFile])

  const clearCompleted = useCallback(() => {
    setUploads((prev) => prev.filter((u) => u.status !== 'complete'))
  }, [])

  const completedCount = uploads.filter((u) => u.status === 'complete').length
  const totalCount = uploads.length

  const statusIcon = (record: UploadRecord) => {
    switch (record.status) {
      case 'complete':
        return (
          <div className="flex items-center gap-1.5 text-accent-green">
            <CheckCircle className="size-5" />
            <span className="text-xs font-bold">Complete</span>
          </div>
        )
      case 'processing':
        return (
          <div className="flex items-center gap-1.5 text-primary">
            <BrainCog className="size-5 animate-spin" style={{ animationDuration: '3s' }} />
            <span className="text-xs font-bold">Processing AI...</span>
          </div>
        )
      case 'uploading':
        return record.progress >= 0 ? (
          <span className="text-xs font-bold text-[var(--muted-foreground)]">{record.progress}%</span>
        ) : (
          <span className="text-xs font-bold text-[var(--muted-foreground)]">Uploading...</span>
        )
      case 'failed':
        return (
          <div className="flex items-center gap-1.5 text-[#FF6B6B]">
            <XCircle className="size-5" />
            <span className="text-xs font-bold">Failed</span>
          </div>
        )
      case 'queued':
        return (
          <div className="flex items-center gap-1.5 text-primary">
            <RefreshCw className="size-5 animate-spin" style={{ animationDuration: '4s' }} />
            <span className="text-xs font-bold">Queued</span>
          </div>
        )
    }
  }

  const fileIcon = (name: string) => {
    if (name.toLowerCase().endsWith('.pdf')) return <FileText className="text-[var(--muted-foreground)]" />
    return <FileImage className="text-[var(--muted-foreground)]" />
  }

  return (
    <div className="flex flex-col gap-6 md:gap-8 max-w-5xl mx-auto">
      {/* Upload Zone */}
      <section
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`bg-[var(--card)] rounded-xl border-2 border-dashed p-6 md:p-12 min-h-[40vh] md:min-h-[60vh] text-center flex flex-col items-center justify-center transition-all group cursor-pointer ${
          dragOver ? 'border-primary bg-primary/5' : 'border-[var(--border)] hover:border-primary/50'
        }`}
        onClick={() => fileRef.current?.click()}
      >
        <div className="size-12 md:size-16 rounded-full bg-primary/10 flex items-center justify-center mb-4 md:mb-6 group-hover:scale-110 transition-transform">
          <CloudUpload className="text-primary size-8 md:size-12" />
        </div>
        <h3 className="text-xl md:text-2xl font-bold mb-2">Drag & drop files here</h3>
        <p className="text-[var(--muted-foreground)] text-xs md:text-sm mb-6 md:mb-8">PDF, PNG, JPG, HEIC -- Max 10MB per file</p>
        <div className="flex items-center gap-4">
          <button
            onClick={(e) => { e.stopPropagation(); fileRef.current?.click() }}
            className="bg-primary hover:bg-primary/90 text-white font-bold py-2.5 px-6 rounded-lg transition-colors flex items-center gap-2"
          >
            <Upload className="size-5" />
            Browse Files
          </button>
          <span className="md:hidden text-[var(--muted-foreground)] text-sm font-medium">or</span>
          <button
            onClick={(e) => { e.stopPropagation(); cameraRef.current?.click() }}
            className="md:hidden bg-transparent border border-[var(--border)] hover:border-primary text-[var(--foreground)] font-bold py-2.5 px-6 rounded-lg transition-all flex items-center gap-2"
          >
            <Camera className="size-5" />
            Take Photo
          </button>
        </div>
      </section>

      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg,image/heic,image/tiff,application/pdf"
        multiple
        className="hidden"
        aria-label="Choose files to upload"
        onChange={(e) => { handleFiles(e.target.files); e.target.value = '' }}
      />
      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        aria-label="Take photo to upload"
        onChange={(e) => { handleFiles(e.target.files); e.target.value = '' }}
      />

      {/* Upload Session List */}
      {uploads.length > 0 && (
        <section className="bg-[var(--card)] rounded-xl border border-[var(--border)] overflow-hidden flex flex-col">
          <div className="px-6 py-4 border-b border-[var(--border)] flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h3 className="text-lg font-bold">Upload Session</h3>
              <span className="px-2 py-0.5 bg-primary/20 text-primary text-xs font-bold rounded-full">
                {totalCount} Files
              </span>
            </div>
            <button
              onClick={clearCompleted}
              className="text-primary text-sm font-semibold hover:underline"
            >
              Clear completed
            </button>
          </div>
          <div className="divide-y divide-[var(--border)]">
            {uploads.map((record) => (
              <div key={record.id} className="p-4 flex items-center gap-4 hover:bg-white/5 transition-colors">
                {/* File icon */}
                <div className={`size-12 rounded-lg bg-[var(--card)] flex items-center justify-center relative overflow-hidden shrink-0 ${
                  record.status === 'failed' ? 'grayscale' : ''
                }`}>
                  {fileIcon(record.name)}
                  {record.status === 'complete' && (
                    <div className="absolute inset-0 bg-accent-green/10 opacity-50" />
                  )}
                  {record.status === 'processing' && (
                    <div className="absolute inset-0 bg-primary/20 animate-pulse" />
                  )}
                  {record.status === 'failed' && (
                    <div className="absolute inset-0 bg-[#FF6B6B]/10" />
                  )}
                </div>

                {/* File info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-sm font-semibold truncate">{record.name}</p>
                    {statusIcon(record)}
                  </div>

                  {record.status === 'uploading' ? (
                    <>
                      <div className="w-full h-1.5 bg-[var(--border)] rounded-full overflow-hidden">
                        {record.progress < 0 ? (
                          <div className="bg-primary h-full w-1/3 rounded-full animate-[indeterminate_1.5s_ease-in-out_infinite]" />
                        ) : (
                          <div
                            className="bg-primary h-full transition-all duration-300"
                            style={{ width: `${record.progress}%` }}
                            role="progressbar"
                            aria-valuenow={record.progress}
                            aria-valuemin={0}
                            aria-valuemax={100}
                          />
                        )}
                      </div>
                      <p className="text-[10px] text-[var(--muted-foreground)] mt-1.5 uppercase tracking-wide font-medium">Uploading...</p>
                    </>
                  ) : record.status === 'processing' ? (
                    <div className="w-full h-1.5 bg-[var(--border)] rounded-full overflow-hidden">
                      <div className="bg-primary h-full w-1/3 rounded-full animate-[indeterminate_1.5s_ease-in-out_infinite]" />
                    </div>
                  ) : (
                    <p className={`text-xs flex items-center gap-2 ${
                      record.status === 'failed' ? 'text-[#FF6B6B]/80' : 'text-[var(--muted-foreground)]'
                    }`}>
                      <span>{fmtSize(record.size)}</span>
                      <span className="size-1 rounded-full bg-[var(--border)]" />
                      {record.status === 'complete' && record.extractionInfo && (
                        <span className="text-primary">{record.extractionInfo}</span>
                      )}
                      {record.status === 'failed' && <span>{record.error ?? 'Network error'}</span>}
                      {record.status === 'queued' && <span>Waiting for worker...</span>}
                    </p>
                  )}
                </div>

                {/* Action buttons */}
                {record.status === 'failed' ? (
                  <div className="flex gap-2">
                    <button
                      onClick={() => retryUpload(record)}
                      className="p-2 text-primary hover:bg-primary/10 rounded-lg transition-colors"
                    >
                      <RefreshCw />
                    </button>
                    <button className="p-2 text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
                      <MoreVertical />
                    </button>
                  </div>
                ) : record.status === 'uploading' ? (
                  <button className="p-2 text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
                    <X />
                  </button>
                ) : (
                  <button className="p-2 text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
                    <MoreVertical />
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Bottom Action Bar */}
      {uploads.length > 0 && (
        <div className="mt-4 p-4 md:p-6 bg-[var(--card)] rounded-xl border border-[var(--border)] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-2xl">
          <div className="flex items-center gap-3 md:gap-4">
            <div className="size-10 rounded-full bg-accent-green/20 flex items-center justify-center text-accent-green shrink-0">
              <CheckCheck />
            </div>
            <div>
              <p className="font-bold text-sm md:text-base">{completedCount} of {totalCount} files processed</p>
              <p className="text-xs text-[var(--muted-foreground)]">
                {completedCount > 0 ? 'Documents sent to review queue' : 'Processing...'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 md:gap-3 w-full sm:w-auto">
            <button
              onClick={() => setUploads([])}
              className="px-4 md:px-6 py-2.5 bg-[var(--border)] hover:bg-[var(--border)]/70 text-[var(--foreground)] font-bold rounded-lg transition-all text-sm"
            >
              Clear
            </button>
            {completedCount > 0 && (
              <button
                onClick={() => navigate('/review')}
                className="flex-1 sm:flex-none px-4 md:px-8 py-2.5 bg-primary hover:bg-primary/90 text-white font-bold rounded-lg shadow-lg shadow-primary/20 transition-all flex items-center justify-center gap-2 text-sm"
              >
                <span className="hidden md:inline">View in </span>Review Queue
                <ArrowRight className="size-4" />
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
