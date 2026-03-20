// inventory.js — Inventory list, status filter, pagination
"use strict";

let invPage = 0;
const INV_PAGE_SIZE = 30;
let invStatus = "";
const INV_API = "/api/v1/inventory";

// Called when navigating to #inventory view
async function loadInventory() {
  try {
    const params = new URLSearchParams({
      page: invPage + 1,
      page_size: INV_PAGE_SIZE,
    });
    if (invStatus) params.set("status", invStatus);
    const r = await apiFetch(INV_API + "?" + params);
    const data = await r.json();
    const items = data.items || [];
    renderInvRows(items);
    document.getElementById("inv-total").textContent =
      data.total != null ? data.total + " items" : "";
    renderInvPagination(parseInt(data.page, 10) || 1, parseInt(data.pages, 10) || 1);
  } catch (err) {
    if (err.message !== "Unauthorized") {
      console.error("Failed to load inventory:", err);
      showToast("Failed to load inventory. Check your connection.", "error");
    }
  }
}

function renderInvRows(items) {
  const tbody = document.getElementById("inv-tbody");
  if (!tbody) return;
  if (items.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="7" class="px-4 py-10 text-center text-slate-500">No inventory items found</td></tr>';
    return;
  }
  tbody.innerHTML = items.map((item) => `
    <tr class="hover:bg-primary/5 transition-colors">
      <td class="px-4 py-3 font-medium text-slate-200">${escapeHtml(item.product_name || "\u2014")}</td>
      <td class="px-4 py-3 text-slate-400 font-mono text-xs">${escapeHtml(item.catalog_number || "\u2014")}</td>
      <td class="px-4 py-3 text-slate-400 font-mono text-xs">${escapeHtml(item.lot_number || "\u2014")}</td>
      <td class="px-4 py-3 text-right text-slate-300">${escapeHtml(String(item.quantity ?? "\u2014"))}${item.unit ? " " + escapeHtml(item.unit) : ""}</td>
      <td class="px-4 py-3 text-slate-400">${escapeHtml(item.location_name || "\u2014")}</td>
      <td class="px-4 py-3">${invStatusBadge(item.status)}</td>
      <td class="px-4 py-3 text-slate-400 text-xs">${formatDate(item.expiry_date)}</td>
    </tr>`).join("");
}

function invStatusBadge(status) {
  const s = status || "";
  const map = {
    available: "bg-accent-green/10 text-accent-green border-accent-green/20",
    consumed:  "bg-slate-700/50 text-slate-400 border-slate-600",
    expired:   "bg-red-500/10 text-red-400 border-red-500/20",
    disposed:  "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  };
  const cls = map[s] || "bg-slate-700/50 text-slate-400 border-slate-600";
  return `<span class="inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold border ${cls}">${escapeHtml(s || "unknown")}</span>`;
}

function formatDate(dateStr) {
  if (!dateStr) return "\u2014";
  return escapeHtml(dateStr.slice(0, 10));
}

function renderInvPagination(page, pages) {
  const el = document.getElementById("inv-pagination");
  if (!el) return;
  el.innerHTML = `
    <button onclick="invChangePage(-1)" ${page <= 1 ? "disabled" : ""}
      class="px-3 py-1.5 rounded-lg border border-border-dark bg-surface-dark text-slate-300 text-xs disabled:opacity-40 hover:border-primary/50 transition-colors">
      <span class="material-symbols-outlined" style="font-size:14px;vertical-align:middle">chevron_left</span> Prev
    </button>
    <span class="text-xs text-slate-500">Page ${page} of ${pages}</span>
    <button onclick="invChangePage(1)" ${page >= pages ? "disabled" : ""}
      class="px-3 py-1.5 rounded-lg border border-border-dark bg-surface-dark text-slate-300 text-xs disabled:opacity-40 hover:border-primary/50 transition-colors">
      Next <span class="material-symbols-outlined" style="font-size:14px;vertical-align:middle">chevron_right</span>
    </button>`;
}

function invChangePage(delta) {
  invPage = Math.max(0, invPage + delta);
  loadInventory();
}

// Wired up via onchange on #inv-status-filter
function invFilterChanged() {
  const sel = document.getElementById("inv-status-filter");
  invStatus = sel ? sel.value : "";
  invPage = 0;
  loadInventory();
}
