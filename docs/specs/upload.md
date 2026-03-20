# Upload — Page Spec

| | |
|---|---|
| **Route** | `/upload` |
| **Status** | Built — **upload action NOT wired to API** |
| **Priority** | **P0 — must fix** |
| **Stitch Screen** | `Document Upload — Lab Manager` |

---

## What Needs to Be Done

**Critical**: The upload form UI exists but does NOT call the API. Wire it:
1. Connect drag-and-drop / file picker to `POST /api/v1/documents/upload`
2. Show real upload progress (multipart upload)
3. Show processing status after upload completes
4. Redirect to `/review` after all files processed

---

## API Contract

### POST /api/v1/documents/upload
Upload a document file for AI extraction.
```
Content-Type: multipart/form-data
Body: file (File)

Allowed MIME types: image/png, image/jpeg, image/tiff, application/pdf
Max file size: 50 MB
```
```json
// Response (201)
{
  "id": 42,
  "file_name": "20260319_143000_invoice.pdf",
  "file_path": "uploads/20260319_143000_invoice.pdf",
  "status": "pending",
  "document_type": null,
  "vendor_name": null,
  "extraction_confidence": null,
  "created_at": "2026-03-19T14:30:00"
}
```
```json
// Error responses
{ "detail": "File type not allowed" }           // 400
{ "detail": "File too large (max 50MB)" }       // 400
{ "detail": "No file provided" }                // 422
```

---

## Component Architecture

```
UploadPage
├── Breadcrumb ("Documents > Upload")
├── DropZone
│   ├── DragOverlay (visual feedback on drag)
│   ├── FileInput (click to browse)
│   └── Restrictions label ("PNG, JPEG, TIFF, PDF — max 50MB")
├── FileList
│   └── FileRow (name, size, status icon, progress bar, remove button)
├── UploadButton ("Upload & Process" — disabled until files selected)
└── CompleteCTA ("Go to Review Queue" — shown after all uploads done)
```

## Data Flow

```typescript
const [files, setFiles] = useState<UploadFile[]>([])
// UploadFile = { file: File, status: 'queued'|'uploading'|'complete'|'error', progress: number, result?: Document }

const uploadMutation = useMutation({
  mutationFn: (file: File) => documents.upload(file),
  onSuccess: (data, file) => {
    // Update file status to 'complete', store result
  },
  onError: (error, file) => {
    // Update file status to 'error', show message
  },
})

// Upload files sequentially or in parallel (max 3 concurrent)
const handleUpload = async () => {
  for (const f of files) {
    await uploadMutation.mutateAsync(f.file)
  }
}
```

### API client addition needed

```typescript
// In api.ts — documents module
upload: async (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${BASE}/api/v1/documents/upload`, {
    method: 'POST',
    body: formData,
    credentials: 'include',
  })
  if (!res.ok) throw new Error((await res.json()).detail ?? 'Upload failed')
  return res.json()
}
```

---

## User Interactions

| Action | Behavior |
|--------|----------|
| Drag file onto drop zone | Add to file list, validate type/size client-side |
| Click drop zone | Open file picker |
| Click remove on file row | Remove from list (before upload) |
| Click "Upload & Process" | Start uploading all files, show progress per file |
| Upload completes | Show "Go to Review Queue" CTA |
| Click "Go to Review Queue" | Navigate to `/review` |

### Client-side validation
- Reject files with wrong MIME type (show inline error)
- Reject files > 50MB (show inline error)
- Allow multiple files

---

## UI States

| State | Condition | Display |
|-------|-----------|---------|
| Empty | No files selected | Drop zone with instructions |
| Files selected | Files in list, not yet uploaded | File list + Upload button enabled |
| Uploading | Upload in progress | Progress bars per file, Upload button disabled |
| Processing | Server processing (extraction) | Spinner/processing indicator per file |
| Complete | All files uploaded | Success message + "Go to Review Queue" button |
| Error | Upload failed for a file | Error message on that file row, retry button |

---

## Acceptance Criteria

- [ ] Drag-and-drop adds files to the upload list
- [ ] Click-to-browse opens file picker
- [ ] Client-side rejects non-image/PDF files with error message
- [ ] Client-side rejects files > 50MB with error message
- [ ] "Upload & Process" sends each file to `POST /api/v1/documents/upload`
- [ ] Progress bar shows upload progress per file
- [ ] Successful upload shows checkmark and document ID
- [ ] Failed upload shows error message with retry option
- [ ] "Go to Review Queue" navigates to `/review` after all uploads complete
- [ ] Multiple files can be uploaded in one session
