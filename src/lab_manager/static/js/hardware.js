// hardware.js — Hardware/Equipment page for scientists
"use strict";

let hwPage = 0;
const HW_PAGE_SIZE = 30;
let hwStatus = "";
let hwCategory = "";
let hwSearch = "";
const HW_API = "/api/v1/equipment";

async function loadHardware() {
  try {
    const params = new URLSearchParams({
      page: hwPage + 1,
      page_size: HW_PAGE_SIZE,
    });
    if (hwStatus) params.set("status", hwStatus);
    if (hwCategory) params.set("category", hwCategory);
    if (hwSearch) params.set("search", hwSearch);
    const r = await apiFetch(HW_API + "?" + params);
    const data = await r.json();
    const items = data.items || [];
    renderHwCards(items);
    renderHwSummary(items, data.total || 0);
    renderHwPagination(parseInt(data.page, 10) || 1, parseInt(data.pages, 10) || 1);
    loadHwCategories(items);
  } catch (err) {
    if (err.message !== "Unauthorized") {
      console.error("Failed to load hardware:", err);
      showToast("Failed to load hardware list.", "error");
    }
  }
}

function renderHwSummary(items, total) {
  const el = document.getElementById("hw-total");
  if (el) el.textContent = total + " piece" + (total !== 1 ? "s" : "") + " of equipment";

  // Count statuses from full dataset hint — we show totals from current filter
  const counts = { active: 0, maintenance: 0, broken: 0, retired: 0 };
  items.forEach((item) => {
    if (counts[item.status] !== undefined) counts[item.status]++;
  });
  const summaryEl = document.getElementById("hw-status-summary");
  if (summaryEl) {
    summaryEl.innerHTML = `
      <div class="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
        <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
        <span class="text-xs text-emerald-400 font-medium">${counts.active} Working</span>
      </div>
      <div class="flex items-center gap-2 px-3 py-1.5 bg-amber-500/10 border border-amber-500/20 rounded-lg">
        <span class="w-2 h-2 rounded-full bg-amber-400"></span>
        <span class="text-xs text-amber-400 font-medium">${counts.maintenance} In Maintenance</span>
      </div>
      <div class="flex items-center gap-2 px-3 py-1.5 bg-red-500/10 border border-red-500/20 rounded-lg">
        <span class="w-2 h-2 rounded-full bg-red-400"></span>
        <span class="text-xs text-red-400 font-medium">${counts.broken} Needs Repair</span>
      </div>
    `;
  }
}

function renderHwCards(items) {
  const grid = document.getElementById("hw-grid");
  if (!grid) return;
  if (items.length === 0) {
    grid.innerHTML = `
      <div class="col-span-full flex flex-col items-center py-16 text-center">
        <span class="material-symbols-outlined text-5xl text-slate-600 mb-3">precision_manufacturing</span>
        <p class="text-slate-400 font-medium mb-1">No equipment found</p>
        <p class="text-sm text-slate-600">Try adjusting your filters or add new equipment.</p>
      </div>`;
    return;
  }
  grid.innerHTML = items.map((item) => {
    const statusInfo = hwStatusInfo(item.status);
    const catLabel = item.category ? escapeHtml(item.category) : "General";
    const loc = item.room || "No location set";
    return `
    <div class="bg-surface-dark border border-border-dark rounded-xl p-5 hover:border-primary/30 transition-colors cursor-pointer group"
         onclick="openHwDetail(${item.id})">
      <div class="flex items-start justify-between mb-3">
        <div class="flex items-center gap-2">
          <span class="material-symbols-outlined text-2xl ${statusInfo.iconColor}">${hwCategoryIcon(item.category)}</span>
          <span class="inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${statusInfo.cls}">${escapeHtml(statusInfo.label)}</span>
        </div>
      </div>
      <h3 class="text-sm font-semibold text-white mb-1 group-hover:text-primary transition-colors truncate">${escapeHtml(item.name)}</h3>
      <p class="text-xs text-slate-500 mb-3 truncate">${escapeHtml(item.manufacturer || "")}${item.model ? " " + escapeHtml(item.model) : ""}</p>
      <div class="space-y-1.5">
        <div class="flex items-center gap-2 text-xs text-slate-400">
          <span class="material-symbols-outlined text-sm">category</span>
          ${escapeHtml(catLabel)}
        </div>
        <div class="flex items-center gap-2 text-xs text-slate-400">
          <span class="material-symbols-outlined text-sm">location_on</span>
          ${escapeHtml(loc)}
        </div>
        ${item.serial_number ? `<div class="flex items-center gap-2 text-xs text-slate-400">
          <span class="material-symbols-outlined text-sm">tag</span>
          S/N: ${escapeHtml(item.serial_number)}
        </div>` : ""}
      </div>
    </div>`;
  }).join("");
}

function hwStatusInfo(status) {
  const map = {
    active:         { label: "Working",     cls: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20", iconColor: "text-emerald-400" },
    maintenance:    { label: "Maintenance", cls: "bg-amber-500/10 text-amber-400 border border-amber-500/20",       iconColor: "text-amber-400"   },
    broken:         { label: "Needs Repair",cls: "bg-red-500/10 text-red-400 border border-red-500/20",             iconColor: "text-red-400"     },
    retired:        { label: "Retired",     cls: "bg-slate-700/50 text-slate-400 border border-slate-600",          iconColor: "text-slate-400"   },
    decommissioned: { label: "Removed",     cls: "bg-slate-700/50 text-slate-500 border border-slate-700",          iconColor: "text-slate-500"   },
  };
  return map[status] || { label: status || "Unknown", cls: "bg-slate-700/50 text-slate-400 border border-slate-600", iconColor: "text-slate-400" };
}

function hwCategoryIcon(category) {
  if (!category) return "precision_manufacturing";
  const c = category.toLowerCase();
  if (c.includes("microscop"))   return "microscope";
  if (c.includes("centrifug"))   return "rotate_right";
  if (c.includes("freezer") || c.includes("refrigerat") || c.includes("cold")) return "ac_unit";
  if (c.includes("oven") || c.includes("incubat") || c.includes("heat")) return "thermostat";
  if (c.includes("scale") || c.includes("balance") || c.includes("weigh")) return "scale";
  if (c.includes("pipet"))       return "colorize";
  if (c.includes("spectro") || c.includes("photometer")) return "light_mode";
  if (c.includes("pcr") || c.includes("thermal cycl")) return "biotech";
  if (c.includes("shaker") || c.includes("mixer") || c.includes("vortex")) return "blender";
  if (c.includes("pump"))        return "water_pump";
  if (c.includes("hood") || c.includes("cabinet") || c.includes("safety")) return "shield";
  if (c.includes("computer") || c.includes("software")) return "computer";
  if (c.includes("ph ") || c.includes("meter") || c.includes("sensor")) return "speed";
  return "precision_manufacturing";
}

function loadHwCategories() {
  // Populate category filter dynamically from a separate call if not yet loaded
  const sel = document.getElementById("hw-category-filter");
  if (!sel || sel.options.length > 1) return; // already populated
  apiFetch(HW_API + "?page=1&page_size=200").then(r => r.json()).then(data => {
    const cats = new Set();
    (data.items || []).forEach(item => { if (item.category) cats.add(item.category); });
    const sorted = [...cats].sort();
    sorted.forEach(cat => {
      const opt = document.createElement("option");
      opt.value = cat;
      opt.textContent = cat;
      sel.appendChild(opt);
    });
  }).catch(() => {});
}

function openHwDetail(id) {
  apiFetch(HW_API + "/" + id).then(r => r.json()).then(item => {
    const statusInfo = hwStatusInfo(item.status);
    const title = document.getElementById("detail-title");
    const body = document.getElementById("detail-body");
    const actions = document.getElementById("detail-actions");
    if (title) title.textContent = item.name;

    const value = item.estimated_value
      ? "$" + parseFloat(item.estimated_value).toLocaleString(undefined, { minimumFractionDigits: 2 })
      : "Not recorded";

    if (body) body.innerHTML = `
      <div class="space-y-5">
        <div class="flex items-center gap-3 mb-4">
          <span class="material-symbols-outlined text-4xl ${statusInfo.iconColor}">${hwCategoryIcon(item.category)}</span>
          <div>
            <h3 class="text-lg font-semibold text-white">${escapeHtml(item.name)}</h3>
            <span class="inline-block mt-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${statusInfo.cls}">${escapeHtml(statusInfo.label)}</span>
          </div>
        </div>

        ${item.description ? `<div class="bg-background-dark/50 rounded-lg p-3 text-sm text-slate-300">${escapeHtml(item.description)}</div>` : ""}

        <div class="grid grid-cols-2 gap-4">
          <div>
            <div class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Manufacturer</div>
            <div class="text-sm text-slate-200">${escapeHtml(item.manufacturer || "Unknown")}</div>
          </div>
          <div>
            <div class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Model</div>
            <div class="text-sm text-slate-200">${escapeHtml(item.model || "N/A")}</div>
          </div>
          <div>
            <div class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Serial Number</div>
            <div class="text-sm text-slate-200 font-mono">${escapeHtml(item.serial_number || "N/A")}</div>
          </div>
          <div>
            <div class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">System ID</div>
            <div class="text-sm text-slate-200 font-mono">${escapeHtml(item.system_id || "N/A")}</div>
          </div>
          <div>
            <div class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Category</div>
            <div class="text-sm text-slate-200">${escapeHtml(item.category || "General")}</div>
          </div>
          <div>
            <div class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Location / Room</div>
            <div class="text-sm text-slate-200">${escapeHtml(item.room || "Not assigned")}</div>
          </div>
          <div>
            <div class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Estimated Value</div>
            <div class="text-sm text-slate-200">${value}</div>
          </div>
          <div>
            <div class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">API Controllable</div>
            <div class="text-sm text-slate-200">${item.is_api_controllable ? "Yes" + (item.api_interface ? " (" + escapeHtml(item.api_interface) + ")" : "") : "No"}</div>
          </div>
        </div>

        ${item.notes ? `
        <div>
          <div class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Notes</div>
          <div class="bg-background-dark/50 rounded-lg p-3 text-sm text-slate-300 whitespace-pre-wrap">${escapeHtml(item.notes)}</div>
        </div>` : ""}

        <div class="text-[10px] text-slate-600 pt-2 border-t border-border-dark">
          Added ${item.created_at ? escapeHtml(item.created_at.slice(0, 10)) : "unknown"}
          ${item.updated_at ? " &middot; Last updated " + escapeHtml(item.updated_at.slice(0, 10)) : ""}
        </div>
      </div>`;

    if (actions) actions.innerHTML = `
      <button onclick="closeDetail()" class="px-4 py-2 rounded-lg text-sm font-medium bg-background-dark text-slate-400 border border-border-dark hover:border-slate-500 transition-colors">Close</button>`;

    document.getElementById("overlay").classList.add("show");
    document.getElementById("detail-panel").classList.add("open");
  }).catch(() => {
    showToast("Could not load equipment details.", "error");
  });
}

function hwFilterChanged() {
  const statusSel = document.getElementById("hw-status-filter");
  const catSel = document.getElementById("hw-category-filter");
  hwStatus = statusSel ? statusSel.value : "";
  hwCategory = catSel ? catSel.value : "";
  hwPage = 0;
  loadHardware();
}

function hwSearchChanged() {
  const input = document.getElementById("hw-search-input");
  hwSearch = input ? input.value.trim() : "";
  hwPage = 0;
  loadHardware();
}

let _hwSearchTimer = null;
function hwSearchDebounce() {
  clearTimeout(_hwSearchTimer);
  _hwSearchTimer = setTimeout(hwSearchChanged, 300);
}

function renderHwPagination(page, pages) {
  const el = document.getElementById("hw-pagination");
  if (!el) return;
  el.innerHTML = `
    <button onclick="hwChangePage(-1)" ${page <= 1 ? "disabled" : ""}
      class="px-3 py-1.5 rounded-lg border border-border-dark bg-surface-dark text-slate-300 text-xs disabled:opacity-40 hover:border-primary/50 transition-colors">
      <span class="material-symbols-outlined" style="font-size:14px;vertical-align:middle">chevron_left</span> Prev
    </button>
    <span class="text-xs text-slate-500">Page ${page} of ${pages}</span>
    <button onclick="hwChangePage(1)" ${page >= pages ? "disabled" : ""}
      class="px-3 py-1.5 rounded-lg border border-border-dark bg-surface-dark text-slate-300 text-xs disabled:opacity-40 hover:border-primary/50 transition-colors">
      Next <span class="material-symbols-outlined" style="font-size:14px;vertical-align:middle">chevron_right</span>
    </button>`;
}

function hwChangePage(delta) {
  hwPage = Math.max(0, hwPage + delta);
  loadHardware();
}
