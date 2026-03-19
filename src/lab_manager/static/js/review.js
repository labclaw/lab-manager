// review.js — Review queue, 3-column layout, approve/reject/edit actions, reject modal
"use strict";

let pendingRejectId = null;
let reviewDocs = [];
let selectedReviewDoc = null;

async function loadReviewQueue() {
  try {
    const r = await apiFetch(API + "?status=needs_review&page_size=200");
    const data = await r.json();
    reviewDocs = data.items || [];
    renderReviewQueue();
  } catch (err) {
    if (err.message !== "Unauthorized")
      console.error("Failed to load review queue:", err);
  }
}

function renderReviewQueue() {
  const container = document.getElementById("review-content");

  if (reviewDocs.length === 0) {
    container.innerHTML = `
      <div class="flex flex-col items-center justify-center h-full text-center py-20">
        <span class="material-symbols-outlined text-6xl text-slate-600 mb-4">task_alt</span>
        <h3 class="text-lg font-semibold text-slate-300 mb-2">All caught up!</h3>
        <p class="text-sm text-slate-500">No documents need review right now.</p>
      </div>`;
    return;
  }

  container.innerHTML = `
    <div class="flex h-full">
      <!-- Left panel: document list -->
      <div class="w-2/5 border-r border-border-dark overflow-y-auto" id="review-list-panel">
        ${reviewDocs
          .map(
            (d, i) => `
          <div class="review-card p-4 border-b border-border-dark cursor-pointer hover:bg-primary/5 transition-colors ${i === 0 ? "bg-primary/10" : ""}" data-review-idx="${i}" onclick="selectReviewDoc(${i})">
            <div class="flex items-center justify-between mb-1">
              <span class="text-sm font-medium text-slate-300 truncate flex-1">${escapeHtml(d.file_name || "")}</span>
              <span class="text-xs font-semibold ml-2 ${confidenceColor(d.extraction_confidence)}">${d.extraction_confidence != null ? (d.extraction_confidence * 100).toFixed(0) + "%" : "\u2014"}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-xs text-slate-500">#${d.id}</span>
              <span class="text-xs text-slate-500">${escapeHtml(d.vendor_name || "")}</span>
              ${confidenceBadge(d.extraction_confidence)}
            </div>
          </div>`
          )
          .join("")}
      </div>
      <!-- Right panel -->
      <div class="w-3/5 flex flex-col overflow-hidden" id="review-detail-panel">
        <div id="review-preview" class="flex-1 overflow-y-auto p-4"></div>
        <div id="review-action-bar" class="border-t border-border-dark p-4 flex gap-3"></div>
      </div>
    </div>`;

  // Auto-select first document
  if (reviewDocs.length > 0) {
    selectReviewDoc(0);
  }
}

function confidenceBadge(conf) {
  if (conf == null) return "";
  if (conf >= 0.9) return "";
  if (conf >= 0.7)
    return '<span class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">MEDIUM</span>';
  return '<span class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-red-500/10 text-red-400 border border-red-500/20">LOW</span>';
}

async function selectReviewDoc(idx) {
  selectedReviewDoc = idx;
  const d = reviewDocs[idx];

  // Update active card
  document.querySelectorAll(".review-card").forEach((el, i) => {
    el.classList.toggle("bg-primary/10", i === idx);
  });

  // Fetch full doc detail
  try {
    const r = await apiFetch(API + "/" + d.id);
    const doc = await r.json();
    const data = doc.extracted_data || {};

    // Preview area
    const preview = document.getElementById("review-preview");
    let itemsHtml = "";
    if (data.items && data.items.length > 0) {
      itemsHtml = `
        <div class="mt-4">
          <h4 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Line Items (${data.items.length})</h4>
          <div class="overflow-x-auto">
            <table class="w-full text-xs">
              <thead>
                <tr class="text-left text-slate-500 uppercase">
                  <th class="py-1.5 px-2">Catalog #</th>
                  <th class="py-1.5 px-2">Description</th>
                  <th class="py-1.5 px-2">Qty</th>
                  <th class="py-1.5 px-2">Unit</th>
                  <th class="py-1.5 px-2">Lot #</th>
                </tr>
              </thead>
              <tbody>
                ${data.items
                  .map(
                    (it) => `<tr class="border-t border-border-dark">
                  <td class="py-1.5 px-2 font-medium text-slate-300">${escapeHtml(it.catalog_number || "\u2014")}</td>
                  <td class="py-1.5 px-2 text-slate-400">${escapeHtml(it.description || "\u2014")}</td>
                  <td class="py-1.5 px-2 text-slate-400">${escapeHtml(String(it.quantity || "\u2014"))}</td>
                  <td class="py-1.5 px-2 text-slate-400">${escapeHtml(it.unit || "")}</td>
                  <td class="py-1.5 px-2 text-slate-400">${escapeHtml(it.lot_number || "\u2014")}</td>
                </tr>`
                  )
                  .join("")}
              </tbody>
            </table>
          </div>
        </div>`;
    }

    preview.innerHTML = `
      <!-- Document preview -->
      <div class="flex items-center gap-3 p-4 bg-background-dark rounded-lg border border-border-dark mb-4">
        <span class="material-symbols-outlined text-4xl text-primary">picture_as_pdf</span>
        <div>
          <div class="text-sm font-medium text-slate-300">${escapeHtml(doc.file_name || "")}</div>
          <div class="text-xs text-slate-500">Document #${doc.id}</div>
        </div>
      </div>

      <!-- Extracted data grid -->
      <h4 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Extracted Data</h4>
      <div class="grid grid-cols-2 gap-x-4 gap-y-2 mb-4">
        ${reviewFieldCell("Vendor", data.vendor_name)}
        ${reviewFieldCell("PO Number", data.po_number)}
        ${reviewFieldCell("Document Type", data.document_type)}
        ${reviewFieldCell("Order Number", data.order_number)}
        ${reviewFieldCell("Order Date", data.order_date)}
        ${reviewFieldCell("Ship Date", data.ship_date)}
        ${reviewFieldCell("Received Date", data.received_date)}
        ${reviewFieldCell("Received By", data.received_by)}
      </div>

      ${itemsHtml}
    `;

    // Action bar
    const actionBar = document.getElementById("review-action-bar");
    actionBar.innerHTML = `
      <button class="px-5 py-2 rounded-lg text-sm font-semibold bg-accent-green text-white hover:bg-accent-green/80 transition-colors" onclick="reviewDoc(${doc.id}, 'approve')">
        <span class="material-symbols-outlined text-base align-middle mr-1">check</span>Approve
      </button>
      <button class="px-5 py-2 rounded-lg text-sm font-semibold bg-amber-500 text-white hover:bg-amber-600 transition-colors" onclick="reviewDoc(${doc.id}, 'approve')">
        <span class="material-symbols-outlined text-base align-middle mr-1">edit</span>Edit & Approve
      </button>
      <button class="px-5 py-2 rounded-lg text-sm font-semibold bg-red-500 text-white hover:bg-red-600 transition-colors" onclick="openRejectModal(${doc.id})">
        <span class="material-symbols-outlined text-base align-middle mr-1">close</span>Reject
      </button>
    `;
  } catch (err) {
    if (err.message !== "Unauthorized")
      console.error("Failed to load review doc:", err);
  }
}

function reviewFieldCell(label, value) {
  return `<div class="py-1.5 border-b border-border-dark/50">
    <div class="text-[10px] text-slate-500 uppercase">${escapeHtml(label)}</div>
    <div class="text-sm text-slate-300">${escapeHtml(value || "") || "\u2014"}</div>
  </div>`;
}

// --- Review actions ---
async function reviewDoc(id, action, reviewNotes) {
  const reviewer = currentUser ? currentUser.name : "scientist";
  const body = { action, reviewed_by: reviewer };
  if (reviewNotes) body.review_notes = reviewNotes;
  try {
    const r = await apiFetch(API + "/" + id + "/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (r.ok) {
      showToast(
        action === "approve"
          ? "Document approved, order created!"
          : "Document rejected",
        "success"
      );
      closeDetail();
      await loadStats();
      // Refresh current view
      const hash = window.location.hash.replace("#", "");
      if (hash === "review") loadReviewQueue();
      if (hash === "documents") loadDocuments();
    } else {
      showToast("Error: " + (await r.text()), "error");
    }
  } catch (err) {
    if (err.message !== "Unauthorized")
      console.error("Review action failed:", err);
  }
}

// --- Reject modal ---
function openRejectModal(id) {
  pendingRejectId = id;
  document.getElementById("reject-reason").value = "";
  document.getElementById("reject-modal").classList.add("show");
}

function closeRejectModal() {
  pendingRejectId = null;
  document.getElementById("reject-modal").classList.remove("show");
}

async function confirmReject() {
  if (!pendingRejectId) return;
  const reason = document.getElementById("reject-reason").value.trim();
  await reviewDoc(pendingRejectId, "reject", reason || null);
  closeRejectModal();
}
