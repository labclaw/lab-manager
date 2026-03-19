import { useState, useRef, useCallback } from 'react'
import { documents } from '@/lib/api'
import type { Document } from '@/lib/api'

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
  doc?: Document
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

    // Simulate upload progress
    setUploads((prev) => prev.map((u) => u.id === id ? { ...u, status: 'uploading', progress: 0 } : u))

    try {
      // Progress simulation
      for (const pct of [20, 45, 65, 85]) {
        await new Promise((r) => setTimeout(r, 200))
        setUploads((prev) => prev.map((u) => u.id === id ? { ...u, progress: pct } : u))
      }

      setUploads((prev) => prev.map((u) => u.id === id ? { ...u, status: 'processing', progress: 100 } : u))

      const doc = await documents.upload(file)

      setUploads((prev) => prev.map((u) => u.id === id ? {
        ...u,
        status: 'complete',
        progress: 100,
        doc,
        extractionInfo: `${doc.vendor_name ?? 'Unknown'} | ${doc.document_type ?? 'document'} | ${doc.status === 'approved' ? '97%' : '85%'} Conf.`,
      } : u))
    } catch (err) {
      setUploads((prev) => prev.map((u) => u.id === id ? {
        ...u,
        status: 'failed',
        error: err instanceof Error ? err.message : 'Upload failed',
      } : u))
    }
  }, [])

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
            <span className="material-symbols-outlined text-lg">check_circle</span>
            <span className="text-xs font-bold">Complete</span>
          </div>
        )
      case 'processing':
        return (
          <div className="flex items-center gap-1.5 text-primary">
            <span className="material-symbols-outlined text-lg animate-spin" style={{ animationDuration: '3s' }}>cognition</span>
            <span className="text-xs font-bold">Processing AI...</span>
          </div>
        )
      case 'uploading':
        return (
          <span className="text-xs font-bold text-[#8E8EA0]">{record.progress}%</span>
        )
      case 'failed':
        return (
          <div className="flex items-center gap-1.5 text-[#FF6B6B]">
            <span className="material-symbols-outlined text-lg">error</span>
            <span className="text-xs font-bold">Failed</span>
          </div>
        )
      case 'queued':
        return (
          <div className="flex items-center gap-1.5 text-primary">
            <span className="material-symbols-outlined text-lg animate-spin" style={{ animationDuration: '4s' }}>sync</span>
            <span className="text-xs font-bold">Queued</span>
          </div>
        )
    }
  }

  const fileIcon = (name: string) => {
    if (name.toLowerCase().endsWith('.pdf')) return 'picture_as_pdf'
    return 'image'
  }

  return (
    <div className="flex flex-col gap-8 max-w-5xl mx-auto">
      {/* Upload Zone */}
      <section
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`bg-card-dark rounded-xl border-2 border-dashed p-12 text-center flex flex-col items-center justify-center transition-all group cursor-pointer ${
          dragOver ? 'border-primary bg-primary/5' : 'border-[#2A2A3E] hover:border-primary/50'
        }`}
        onClick={() => fileRef.current?.click()}
      >
        <div className="size-16 rounded-full bg-primary/10 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
          <span className="material-symbols-outlined text-primary text-5xl">cloud_upload</span>
        </div>
        <h3 className="text-2xl font-bold mb-2">Drag & drop files here</h3>
        <p className="text-[#8E8EA0] text-sm mb-8">PDF, PNG, JPG, HEIC -- Max 10MB per file</p>
        <div className="flex items-center gap-4">
          <button
            onClick={(e) => { e.stopPropagation(); fileRef.current?.click() }}
            className="bg-primary hover:bg-primary/90 text-white font-bold py-2.5 px-6 rounded-lg transition-colors flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-xl">upload_file</span>
            Browse Files
          </button>
          <span className="text-[#8E8EA0] text-sm font-medium">or</span>
          <button
            onClick={(e) => { e.stopPropagation(); cameraRef.current?.click() }}
            className="bg-transparent border border-[#2A2A3E] hover:border-primary text-[#F0F0F5] font-bold py-2.5 px-6 rounded-lg transition-all flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-xl">photo_camera</span>
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
        <section className="bg-card-dark rounded-xl border border-[#2A2A3E] overflow-hidden flex flex-col">
          <div className="px-6 py-4 border-b border-[#2A2A3E] flex items-center justify-between">
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
          <div className="divide-y divide-[#2A2A3E]">
            {uploads.map((record) => (
              <div key={record.id} className="p-4 flex items-center gap-4 hover:bg-white/5 transition-colors">
                {/* File icon */}
                <div className={`size-12 rounded-lg bg-slate-800 flex items-center justify-center relative overflow-hidden shrink-0 ${
                  record.status === 'failed' ? 'grayscale' : ''
                }`}>
                  <span className="material-symbols-outlined text-[#8E8EA0]">{fileIcon(record.name)}</span>
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
                      <div className="w-full h-1.5 bg-[#2A2A3E] rounded-full overflow-hidden">
                        <div
                          className="bg-primary h-full transition-all duration-300"
                          style={{ width: `${record.progress}%` }}
                          role="progressbar"
                          aria-valuenow={record.progress}
                          aria-valuemin={0}
                          aria-valuemax={100}
                        />
                      </div>
                      <p className="text-[10px] text-[#8E8EA0] mt-1.5 uppercase tracking-wide font-medium">Uploading...</p>
                    </>
                  ) : (
                    <p className={`text-xs flex items-center gap-2 ${
                      record.status === 'failed' ? 'text-[#FF6B6B]/80' : 'text-[#8E8EA0]'
                    }`}>
                      <span>{fmtSize(record.size)}</span>
                      <span className="size-1 rounded-full bg-[#2A2A3E]" />
                      {record.status === 'complete' && record.extractionInfo && (
                        <span className="text-primary">{record.extractionInfo}</span>
                      )}
                      {record.status === 'processing' && <span>Detecting fields...</span>}
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
                      <span className="material-symbols-outlined">refresh</span>
                    </button>
                    <button className="p-2 text-[#8E8EA0] hover:text-white">
                      <span className="material-symbols-outlined">more_vert</span>
                    </button>
                  </div>
                ) : record.status === 'uploading' ? (
                  <button className="p-2 text-[#8E8EA0] hover:text-white">
                    <span className="material-symbols-outlined">close</span>
                  </button>
                ) : (
                  <button className="p-2 text-[#8E8EA0] hover:text-white">
                    <span className="material-symbols-outlined">more_vert</span>
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Bottom Action Bar */}
      {uploads.length > 0 && (
        <div className="mt-4 p-6 bg-card-dark rounded-xl border border-[#2A2A3E] flex items-center justify-between shadow-2xl">
          <div className="flex items-center gap-4">
            <div className="size-10 rounded-full bg-accent-green/20 flex items-center justify-center text-accent-green">
              <span className="material-symbols-outlined">done_all</span>
            </div>
            <div>
              <p className="font-bold">{completedCount} of {totalCount} files processed</p>
              <p className="text-xs text-[#8E8EA0]">Ready to move to review queue</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setUploads([])}
              className="px-6 py-2.5 bg-[#2A2A3E] hover:bg-[#2A2A3E]/70 text-[#F0F0F5] font-bold rounded-lg transition-all"
            >
              Cancel All
            </button>
            <button
              disabled={completedCount === 0}
              className="px-8 py-2.5 bg-primary hover:bg-primary/90 text-white font-bold rounded-lg shadow-lg shadow-primary/20 transition-all flex items-center gap-2 disabled:opacity-50"
            >
              Send to Review Queue
              <span className="material-symbols-outlined">arrow_forward</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
