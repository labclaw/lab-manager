// documents.js — Document list, filters, pagination, detail panel
"use strict";

let currentPage = 0;
const PAGE_SIZE = 30;
let currentFilter = "";
let currentSearch = "";
let searchTimer = null;

// --- Load & Render ---
async function loadDocuments() {
  try {
    const params = new URLSearchParams({
      page: currentPage + 1,
      page_size: PAGE_SIZE,
    });
    if (currentFilter) params.set("status", currentFilter);
    if (currentSearch) params.set("search", currentSearch);
    const r = await apiFetch(API + "?" + params);
    const data = await r.json();
    const docs = data.items || [];
    renderDocRows("doc-rows", docs);
    document.getElementById("prev-btn").disabled = currentPage === 0;
    document.getElementById("next-btn").disabled =
      (data.page || 1) >= (data.pages || 1);
    document.getElementById("page-info").textContent =
      "Page " + (data.page || 1) + " of " + (data.pages || 1);
  } catch (err) {
    if (err.message !== "Unauthorized")
      console.error("Failed to load documents:", err);
  }
}

function renderDocRows(containerId, docs) {
  const c = document.getElementById(containerId);
  if (docs.length === 0) {
    c.innerHTML =
      '<div class="p-10 text-center text-slate-500">No documents found</div>';
    return;
  }
  c.innerHTML = docs
    .map(
      (d) => `
    <div class="doc-row grid grid-cols-[60px_1fr_140px_120px_80px_60px] items-center px-4 py-3 border-b border-border-dark cursor-pointer hover:bg-primary/5 transition-colors" onclick="openDetail(${d.id})">
      <div class="text-slate-500 text-sm">#${d.id}</div>
      <div class="min-w-0">
        <div class="font-medium text-sm text-slate-200 truncate">${escapeHtml(d.file_name || "")}</div>
        <div class="text-xs text-slate-500">${escapeHtml(d.vendor_name || "\u2014")}</div>
      </div>
      <div class="text-xs text-slate-400">${escapeHtml(d.document_type || "\u2014")}</div>
      <div>${statusBadge(d.status)}</div>
      <div class="text-sm font-semibold ${confidenceColor(d.extraction_confidence)}">${d.extraction_confidence != null ? (d.extraction_confidence * 100).toFixed(0) + "%" : "\u2014"}</div>
      <div class="text-right">
        <button class="text-xs text-primary hover:text-primary/80 font-medium" onclick="event.stopPropagation(); openDetail(${d.id})">View</button>
      </div>
    </div>`
    )
    .join("");
}

function statusBadge(status) {
  const s = status || "";
  const map = {
    approved:
      "bg-accent-green/10 text-accent-green border-accent-green/20",
    needs_review: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    rejected: "bg-red-500/10 text-red-400 border-red-500/20",
  };
  const cls = map[s] || "bg-slate-700/50 text-slate-400 border-slate-600";
  return `<span class="inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold border ${cls}">${escapeHtml(s.replace("_", " ") || "unknown")}</span>`;
}

function confidenceColor(conf) {
  if (conf == null) return "text-slate-500";
  if (conf >= 0.9) return "text-accent-green";
  if (conf >= 0.7) return "text-amber-400";
  return "text-red-400";
}

// --- Detail panel ---
async function openDetail(id) {
  try {
    const r = await apiFetch(API + "/" + id);
    const doc = await r.json();
    document.getElementById("detail-title").textContent = doc.file_name || "";
    const body = document.getElementById("detail-body");
    const data = doc.extracted_data || {};

    // Build items table
    let itemsHtml = "";
    if (data.items && data.items.length > 0) {
      itemsHtml = `
        <div class="mt-4">
          <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 pb-2 border-b border-border-dark">Line Items (${data.items.length})</h3>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-left text-xs text-slate-500 uppercase">
                  <th class="py-2 px-2">Catalog #</th>
                  <th class="py-2 px-2">Description</th>
                  <th class="py-2 px-2">Qty</th>
                  <th class="py-2 px-2">Unit</th>
                  <th class="py-2 px-2">Lot #</th>
                </tr>
              </thead>
              <tbody>
                ${data.items
                  .map(
                    (it) => `<tr class="border-t border-border-dark">
                  <td class="py-2 px-2 font-medium text-slate-300">${escapeHtml(it.catalog_number || "\u2014")}</td>
                  <td class="py-2 px-2 text-slate-400">${escapeHtml(it.description || "\u2014")}</td>
                  <td class="py-2 px-2 text-slate-400">${escapeHtml(String(it.quantity || "\u2014"))}</td>
                  <td class="py-2 px-2 text-slate-400">${escapeHtml(it.unit || "")}</td>
                  <td class="py-2 px-2 text-slate-400">${escapeHtml(it.lot_number || "\u2014")}</td>
                </tr>`
                  )
                  .join("")}
              </tbody>
            </table>
          </div>
        </div>`;
    }

    body.innerHTML = `
      <img class="w-full max-h-80 object-contain border border-border-dark rounded-lg mb-4 bg-background-dark" src="/scans/${encodeURIComponent(doc.file_name || "")}" onerror="this.style.display='none'" alt="scan">

      <div class="flex gap-3 mb-4 items-center">
        ${statusBadge(doc.status)}
        <span class="text-slate-500 text-sm">Confidence: <strong class="${confidenceColor(doc.extraction_confidence)}">${doc.extraction_confidence != null ? (doc.extraction_confidence * 100).toFixed(0) + "%" : "N/A"}</strong></span>
      </div>

      <div class="mb-4">
        <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 pb-2 border-b border-border-dark">Document Info</h3>
        ${fieldRow("Vendor", escapeHtml(data.vendor_name || ""))}
        ${fieldRow("Type", escapeHtml(data.document_type || ""))}
        ${fieldRow("PO Number", escapeHtml(data.po_number || ""))}
        ${fieldRow("Order Number", escapeHtml(data.order_number || ""))}
        ${fieldRow("Invoice #", escapeHtml(data.invoice_number || ""))}
        ${fieldRow("Delivery #", escapeHtml(data.delivery_number || ""))}
      </div>

      <div class="mb-4">
        <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 pb-2 border-b border-border-dark">Dates</h3>
        ${fieldRow("Order Date", escapeHtml(data.order_date || ""))}
        ${fieldRow("Ship Date", escapeHtml(data.ship_date || ""))}
        ${fieldRow("Received Date", escapeHtml(data.received_date || ""))}
        ${fieldRow("Received By", escapeHtml(data.received_by || ""))}
      </div>

      <div class="mb-4">
        <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 pb-2 border-b border-border-dark">Addresses</h3>
        ${fieldRow("Ship To", escapeHtml(data.ship_to_address || ""))}
        ${fieldRow("Bill To", escapeHtml(data.bill_to_address || ""))}
      </div>

      ${itemsHtml}

      <div class="mt-4">
        <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 pb-2 border-b border-border-dark">OCR Text</h3>
        <div class="flex gap-1 mb-3">
          <button class="tab-btn active px-3 py-1.5 text-xs rounded-md font-medium bg-primary/20 text-primary" onclick="toggleOcr(this, 'extracted')">Extracted Data</button>
          <button class="tab-btn px-3 py-1.5 text-xs rounded-md font-medium bg-surface-dark text-slate-400 border border-border-dark" onclick="toggleOcr(this, 'raw')">Raw OCR Text</button>
        </div>
        <div id="ocr-extracted"><pre class="text-xs max-h-48 overflow-auto bg-background-dark p-3 rounded-lg text-slate-400 border border-border-dark">${escapeHtml(JSON.stringify(data, null, 2))}</pre></div>
        <div id="ocr-raw" class="hidden"><pre class="text-xs max-h-48 overflow-auto bg-background-dark p-3 rounded-lg text-slate-400 border border-border-dark font-mono whitespace-pre-wrap">${escapeHtml(doc.ocr_text || "")}</pre></div>
      </div>
    `;

    // Actions
    const actions = document.getElementById("detail-actions");
    if (doc.status === "needs_review") {
      actions.innerHTML = `
        <button class="px-5 py-2.5 rounded-lg text-sm font-semibold bg-accent-green text-white hover:bg-accent-green/80 transition-colors" onclick="reviewDoc(${doc.id}, 'approve')">Approve & Create Order</button>
        <button class="px-5 py-2.5 rounded-lg text-sm font-semibold bg-red-500 text-white hover:bg-red-600 transition-colors" onclick="openRejectModal(${doc.id})">Reject</button>
        <div class="flex-1"></div>
      `;
    } else {
      actions.innerHTML = `<span class="text-slate-500 text-sm">Status: ${escapeHtml(doc.status || "")}${doc.reviewed_by ? " by " + escapeHtml(doc.reviewed_by) : ""}</span>`;
    }

    document.getElementById("detail-panel").classList.add("open");
    document.getElementById("overlay").classList.add("show");
  } catch (err) {
    if (err.message !== "Unauthorized")
      console.error("Failed to open detail:", err);
  }
}

function closeDetail() {
  document.getElementById("detail-panel").classList.remove("open");
  document.getElementById("overlay").classList.remove("show");
}

function fieldRow(label, value) {
  return `<div class="flex justify-between py-1.5 border-b border-border-dark/50 text-sm">
    <div class="text-slate-500 w-36 flex-shrink-0">${escapeHtml(label)}</div>
    <div class="font-medium text-slate-300 text-right break-all">${value || "\u2014"}</div>
  </div>`;
}

function toggleOcr(btn, mode) {
  btn.parentElement.querySelectorAll("button").forEach((b) => {
    b.className =
      mode === "extracted" && b === btn || mode === "raw" && b === btn
        ? "tab-btn active px-3 py-1.5 text-xs rounded-md font-medium bg-primary/20 text-primary"
        : "tab-btn px-3 py-1.5 text-xs rounded-md font-medium bg-surface-dark text-slate-400 border border-border-dark";
  });
  document
    .getElementById("ocr-extracted")
    .classList.toggle("hidden", mode !== "extracted");
  document
    .getElementById("ocr-raw")
    .classList.toggle("hidden", mode !== "raw");
}

// --- Filters & Pagination ---
function setFilter(btn, status) {
  document.querySelectorAll(".filter-btn").forEach((b) => {
    b.classList.remove("bg-primary", "text-white", "border-primary");
    b.classList.add("bg-surface-dark", "text-slate-400", "border-border-dark");
  });
  btn.classList.remove("bg-surface-dark", "text-slate-400", "border-border-dark");
  btn.classList.add("bg-primary", "text-white", "border-primary");
  currentFilter = status;
  currentPage = 0;
  loadDocuments();
}

function changePage(delta) {
  currentPage = Math.max(0, currentPage + delta);
  loadDocuments();
}

function debounceSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    currentSearch = document.getElementById("search-input").value;
    currentPage = 0;
    loadDocuments();
  }, 300);
}
