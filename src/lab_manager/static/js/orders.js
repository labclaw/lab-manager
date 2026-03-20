// orders.js — Orders list, status filter, pagination
"use strict";

let ordPage = 0;
const ORD_PAGE_SIZE = 25;
let ordStatus = "";

// --- Load & Render ---
async function loadOrders() {
  try {
    const params = new URLSearchParams({
      page: ordPage + 1,
      page_size: ORD_PAGE_SIZE,
    });
    if (ordStatus) params.set("status", ordStatus);
    const r = await apiFetch("/api/v1/orders?" + params);
    const data = await r.json();
    const orders = data.items || [];
    renderOrdRows(orders);
    renderOrdPagination(data);
    const total = document.getElementById("ord-total");
    if (total) total.textContent = data.total ? data.total + " orders" : "";
  } catch (err) {
    if (err.message !== "Unauthorized") {
      console.error("Failed to load orders:", err);
      showToast("Failed to load orders. Check your connection.", "error");
    }
  }
}

function renderOrdRows(orders) {
  const tbody = document.getElementById("ord-tbody");
  if (!tbody) return;
  if (orders.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="6" class="px-4 py-10 text-center text-slate-500">No orders found</td></tr>';
    return;
  }
  tbody.innerHTML = orders
    .map(
      (o) => `
    <tr class="hover:bg-primary/5 transition-colors">
      <td class="px-4 py-3 font-medium text-slate-200">${escapeHtml(o.po_number || "\u2014")}</td>
      <td class="px-4 py-3 text-slate-400">${escapeHtml(o.vendor_name || "\u2014")}</td>
      <td class="px-4 py-3 text-slate-400 text-xs">${formatDate(o.order_date)}</td>
      <td class="px-4 py-3">${ordStatusBadge(o.status)}</td>
      <td class="px-4 py-3 text-right font-medium text-slate-200">${formatCurrency(o.total_amount)}</td>
      <td class="px-4 py-3 text-right text-slate-400">${Array.isArray(o.items) ? o.items.length : 0}</td>
    </tr>`
    )
    .join("");
}

function ordStatusBadge(status) {
  const s = status || "";
  const map = {
    pending: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    received: "bg-accent-green/10 text-accent-green border-accent-green/20",
    cancelled: "bg-red-500/10 text-red-400 border-red-500/20",
  };
  const cls = map[s] || "bg-slate-700/50 text-slate-400 border-slate-600";
  return `<span class="inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold border ${cls}">${escapeHtml(s || "unknown")}</span>`;
}

function formatDate(dateStr) {
  if (!dateStr) return "\u2014";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return escapeHtml(dateStr);
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function formatCurrency(amount) {
  if (amount == null) return "\u2014";
  return "$" + Number(amount).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// --- Pagination ---
function renderOrdPagination(data) {
  const el = document.getElementById("ord-pagination");
  if (!el) return;
  const page = parseInt(data.page, 10) || 1;
  const pages = parseInt(data.pages, 10) || 1;
  el.innerHTML = `
    <button onclick="ordChangePage(-1)" ${page <= 1 ? "disabled" : ""}
      class="px-3 py-1.5 rounded-lg border border-border-dark text-slate-400 hover:text-white hover:border-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-sm">
      <span class="material-symbols-outlined text-base align-middle">chevron_left</span> Prev
    </button>
    <span class="text-slate-500 text-sm">Page ${page} of ${pages}</span>
    <button onclick="ordChangePage(1)" ${page >= pages ? "disabled" : ""}
      class="px-3 py-1.5 rounded-lg border border-border-dark text-slate-400 hover:text-white hover:border-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-sm">
      Next <span class="material-symbols-outlined text-base align-middle">chevron_right</span>
    </button>`;
}

function ordChangePage(delta) {
  ordPage = Math.max(0, ordPage + delta);
  loadOrders();
}

// --- Filter ---
function ordFilterChange() {
  const sel = document.getElementById("ord-status-filter");
  ordStatus = sel ? sel.value : "";
  ordPage = 0;
  loadOrders();
}
