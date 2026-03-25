// upload.js — Mobile camera / file upload UI for lab documents
// API: POST /api/v1/documents/upload  multipart "file" field
// Accepted: image/png, image/jpeg, image/tiff, application/pdf  max 50 MB

const ACCEPTED_TYPES = new Set(['image/png', 'image/jpeg', 'image/tiff', 'application/pdf']);
const MAX_BYTES = 50 * 1024 * 1024;

let _uploadSessionHistory = [];

function loadUpload() {
  _bindUploadZone();
}

function _bindUploadZone() {
  const zone      = document.getElementById('upload-zone');
  const fileInput = document.getElementById('upload-file-input');
  const camInput  = document.getElementById('upload-camera-input');
  const btnPhoto  = document.getElementById('btn-take-photo');
  const btnFile   = document.getElementById('btn-choose-file');

  if (!zone) return;

  // Remove old listeners by cloning nodes
  const zoneClone = zone.cloneNode(true);
  zone.parentNode.replaceChild(zoneClone, zone);

  const z  = document.getElementById('upload-zone');
  const fi = document.getElementById('upload-file-input');
  const ci = document.getElementById('upload-camera-input');

  document.getElementById('btn-take-photo').addEventListener('click', () => ci.click());
  document.getElementById('btn-choose-file').addEventListener('click', () => fi.click());

  fi.addEventListener('change', () => { if (fi.files[0]) _handleFile(fi.files[0]); fi.value = ''; });
  ci.addEventListener('change', () => { if (ci.files[0]) _handleFile(ci.files[0]); ci.value = ''; });

  // Drag-and-drop
  z.addEventListener('dragover', e => { e.preventDefault(); z.classList.add('border-primary'); });
  z.addEventListener('dragleave', () => z.classList.remove('border-primary'));
  z.addEventListener('drop', e => {
    e.preventDefault();
    z.classList.remove('border-primary');
    const file = e.dataTransfer.files[0];
    if (file) _handleFile(file);
  });

  // Click anywhere on zone (but not buttons) opens file picker
  z.addEventListener('click', e => {
    if (e.target.closest('button') || e.target.closest('input')) return;
    fi.click();
  });

  _renderHistory();
}

function _handleFile(file) {
  if (!ACCEPTED_TYPES.has(file.type)) {
    showToast(`Unsupported file type: ${file.type || 'unknown'}. Use PNG, JPEG, TIFF, or PDF.`, 'error');
    return;
  }
  if (file.size > MAX_BYTES) {
    showToast(`File too large (${_fmtSize(file.size)}). Maximum is 50 MB.`, 'error');
    return;
  }
  _showPreview(file);
}

function _showPreview(file) {
  const preview = document.getElementById('upload-preview');
  preview.classList.remove('hidden');

  const isImage = file.type.startsWith('image/');

  preview.innerHTML = `
    <div class="flex items-start gap-4">
      <div id="preview-thumb" class="w-20 h-20 rounded-lg bg-[#0f0f23] border border-border-dark flex items-center justify-center overflow-hidden flex-shrink-0">
        ${isImage
          ? '<span class="material-symbols-outlined text-3xl text-slate-500">image</span>'
          : '<span class="material-symbols-outlined text-3xl text-slate-500">picture_as_pdf</span>'}
      </div>
      <div class="flex-1 min-w-0">
        <p class="text-sm font-medium text-slate-200 truncate">${escapeHtml(file.name)}</p>
        <p class="text-xs text-slate-500 mt-0.5">${_fmtSize(file.size)}</p>
        <div id="upload-status" class="mt-3">
          <button id="btn-upload-confirm"
            class="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/80 transition-colors flex items-center gap-2">
            <span class="material-symbols-outlined text-base">upload</span>Upload
          </button>
        </div>
      </div>
      <button id="btn-cancel-preview" class="text-slate-500 hover:text-white transition-colors p-1">
        <span class="material-symbols-outlined">close</span>
      </button>
    </div>`;

  // Render thumbnail for images
  if (isImage) {
    const thumb = document.getElementById('preview-thumb');
    const reader = new FileReader();
    reader.onload = e => {
      thumb.innerHTML = `<img src="${e.target.result}" class="w-full h-full object-cover" alt="preview">`;
    };
    reader.readAsDataURL(file);
  }

  document.getElementById('btn-cancel-preview').addEventListener('click', _resetPreview);
  document.getElementById('btn-upload-confirm').addEventListener('click', () => _doUpload(file));
}

async function _doUpload(file) {
  const statusEl = document.getElementById('upload-status');
  statusEl.innerHTML = `
    <div class="flex items-center gap-2 text-sm text-slate-400">
      <svg class="animate-spin h-4 w-4 text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
      </svg>
      Uploading…
    </div>`;

  const form = new FormData();
  form.append('file', file);

  try {
    const doc = await apiFetch('/api/v1/documents/upload', { method: 'POST', body: form });

    _uploadSessionHistory.unshift({ name: file.name, size: file.size, doc });
    _renderHistory();

    statusEl.innerHTML = `
      <div class="flex items-center gap-2 text-sm text-[#06d6a0]">
        <span class="material-symbols-outlined text-base">check_circle</span>
        Uploaded successfully
      </div>
      <a href="#review" onclick="navigateTo('review')"
        class="inline-flex items-center gap-1 mt-2 text-xs text-primary hover:underline">
        <span class="material-symbols-outlined text-sm">assignment</span>Go to review queue
      </a>`;

    // Auto-reset after 3 s so user can upload another
    setTimeout(_resetPreview, 3000);
  } catch (err) {
    const msg = err?.message || 'Upload failed';
    const isTooBig = /413|too large/i.test(msg);
    showToast(isTooBig ? 'File rejected by server (too large).' : `Upload error: ${msg}`, 'error');
    statusEl.innerHTML = `
      <div class="flex items-center gap-2">
        <button id="btn-upload-confirm"
          class="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/80 transition-colors flex items-center gap-2">
          <span class="material-symbols-outlined text-base">refresh</span>Retry
        </button>
        <button id="btn-cancel-preview" class="text-xs text-slate-500 hover:text-slate-300">Cancel</button>
      </div>`;
    document.getElementById('btn-upload-confirm').addEventListener('click', () => _doUpload(file));
    document.getElementById('btn-cancel-preview').addEventListener('click', _resetPreview);
  }
}

function _resetPreview() {
  const preview = document.getElementById('upload-preview');
  if (preview) { preview.classList.add('hidden'); preview.innerHTML = ''; }
}

function _renderHistory() {
  const list = document.getElementById('upload-history-list');
  if (!list) return;
  if (_uploadSessionHistory.length === 0) {
    list.innerHTML = '<p class="text-xs text-slate-600">No uploads yet this session.</p>';
    return;
  }
  list.innerHTML = _uploadSessionHistory.slice(0, 10).map(({ name, size, doc }) => `
    <div class="flex items-center gap-3 px-3 py-2 bg-[#0f0f23] rounded-lg border border-border-dark">
      <span class="material-symbols-outlined text-base text-[#06d6a0]">check_circle</span>
      <span class="text-xs text-slate-300 flex-1 truncate">${escapeHtml(name)}</span>
      <span class="text-xs text-slate-600">${_fmtSize(size)}</span>
      ${doc?.id ? `<a onclick="navigateTo('documents')" href="#documents"
        class="text-xs text-primary hover:underline ml-1">View</a>` : ''}
    </div>`).join('');
}

function _fmtSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// --- Bulk CSV Import ---

let _importType = 'products';

function switchUploadTab(tab) {
  const docSection = document.getElementById('upload-doc-section');
  const csvSection = document.getElementById('upload-csv-section');
  const tabDoc = document.getElementById('tab-upload-doc');
  const tabCsv = document.getElementById('tab-upload-csv');

  if (tab === 'csv') {
    docSection.classList.add('hidden');
    csvSection.classList.remove('hidden');
    tabDoc.classList.remove('bg-primary', 'text-white');
    tabDoc.classList.add('text-slate-400', 'hover:text-slate-300');
    tabCsv.classList.add('bg-primary', 'text-white');
    tabCsv.classList.remove('text-slate-400', 'hover:text-slate-300');
    _bindCsvZone();
  } else {
    docSection.classList.remove('hidden');
    csvSection.classList.add('hidden');
    tabDoc.classList.add('bg-primary', 'text-white');
    tabDoc.classList.remove('text-slate-400', 'hover:text-slate-300');
    tabCsv.classList.remove('bg-primary', 'text-white');
    tabCsv.classList.add('text-slate-400', 'hover:text-slate-300');
  }
}

function setImportType(type) {
  _importType = type;
  const productsBtn = document.getElementById('import-type-products');
  const vendorsBtn = document.getElementById('import-type-vendors');
  const info = document.getElementById('import-columns-info');

  if (type === 'products') {
    productsBtn.classList.add('border-primary', 'bg-primary/10', 'text-primary');
    productsBtn.classList.remove('border-border-dark', 'text-slate-400');
    vendorsBtn.classList.remove('border-primary', 'bg-primary/10', 'text-primary');
    vendorsBtn.classList.add('border-border-dark', 'text-slate-400');
    info.innerHTML = `
      <div class="text-xs font-medium text-slate-400 mb-1">Expected columns for Products:</div>
      <div class="text-xs text-slate-500">catalog_number (or sku, cat#) &bull; name (or product, description) &bull; vendor (optional) &bull; category (optional) &bull; cas_number (optional) &bull; unit (optional)</div>`;
  } else {
    vendorsBtn.classList.add('border-primary', 'bg-primary/10', 'text-primary');
    vendorsBtn.classList.remove('border-border-dark', 'text-slate-400');
    productsBtn.classList.remove('border-primary', 'bg-primary/10', 'text-primary');
    productsBtn.classList.add('border-border-dark', 'text-slate-400');
    info.innerHTML = `
      <div class="text-xs font-medium text-slate-400 mb-1">Expected columns for Vendors:</div>
      <div class="text-xs text-slate-500">name (or vendor, supplier) &bull; website (optional) &bull; email (optional) &bull; phone (optional)</div>`;
  }
}

function _bindCsvZone() {
  const zone = document.getElementById('csv-drop-zone');
  const fileInput = document.getElementById('csv-file-input');
  if (!zone || !fileInput) return;

  zone.onclick = () => fileInput.click();

  fileInput.onchange = () => {
    if (fileInput.files[0]) _handleCsvImport(fileInput.files[0]);
    fileInput.value = '';
  };

  zone.ondragover = e => { e.preventDefault(); zone.classList.add('border-primary'); };
  zone.ondragleave = () => zone.classList.remove('border-primary');
  zone.ondrop = e => {
    e.preventDefault();
    zone.classList.remove('border-primary');
    if (e.dataTransfer.files[0]) _handleCsvImport(e.dataTransfer.files[0]);
  };
}

async function _handleCsvImport(file) {
  const resultEl = document.getElementById('import-result');
  resultEl.classList.remove('hidden');
  resultEl.innerHTML = `
    <div class="flex items-center gap-2 text-sm text-slate-400">
      <svg class="animate-spin h-4 w-4 text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
      </svg>
      Importing ${escapeHtml(file.name)}...
    </div>`;

  const form = new FormData();
  form.append('file', file);

  try {
    const r = await apiFetch(`/api/v1/import/${_importType}`, { method: 'POST', body: form });
    if (r.ok) {
      const data = await r.json();
      let errorsHtml = '';
      if (data.errors && data.errors.length > 0) {
        errorsHtml = `<div class="mt-2 text-xs text-red-400">${data.errors.slice(0, 5).map(e => escapeHtml(e)).join('<br>')}${data.errors.length > 5 ? `<br>...and ${data.errors.length - 5} more` : ''}</div>`;
      }
      resultEl.innerHTML = `
        <div class="p-4 rounded-lg bg-accent-green/5 border border-accent-green/20">
          <div class="flex items-center gap-2 text-sm text-accent-green mb-2">
            <span class="material-symbols-outlined text-lg">check_circle</span>
            Import complete
          </div>
          <div class="grid grid-cols-3 gap-4 text-center">
            <div>
              <div class="text-2xl font-bold text-accent-green">${data.created}</div>
              <div class="text-xs text-slate-500">Created</div>
            </div>
            <div>
              <div class="text-2xl font-bold text-slate-400">${data.skipped}</div>
              <div class="text-xs text-slate-500">Skipped (duplicates)</div>
            </div>
            <div>
              <div class="text-2xl font-bold ${data.errors.length > 0 ? 'text-red-400' : 'text-slate-400'}">${data.errors.length}</div>
              <div class="text-xs text-slate-500">Errors</div>
            </div>
          </div>
          ${errorsHtml}
        </div>`;
      if (data.created > 0) {
        showToast(`Imported ${data.created} ${_importType} successfully!`, 'success');
      }
    } else {
      const err = await r.json().catch(() => ({ detail: 'Import failed' }));
      resultEl.innerHTML = `
        <div class="p-3 rounded-lg bg-red-500/5 border border-red-500/20 text-sm text-red-400">
          <span class="material-symbols-outlined text-base align-middle mr-1">error</span>
          ${escapeHtml(err.detail || 'Import failed. Please check your file format.')}
        </div>`;
    }
  } catch (err) {
    if (err.message !== 'Unauthorized') {
      resultEl.innerHTML = `
        <div class="p-3 rounded-lg bg-red-500/5 border border-red-500/20 text-sm text-red-400">
          <span class="material-symbols-outlined text-base align-middle mr-1">error</span>
          Connection error. Please try again.
        </div>`;
    }
  }
}
