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
    renderHwTotal(data.total || 0);
    renderHwPagination(parseInt(data.page, 10) || 1, parseInt(data.pages, 10) || 1);
    loadHwCategories();
  } catch (err) {
    if (err.message !== "Unauthorized") {
      console.error("Failed to load hardware:", err);
      showToast("Failed to load hardware list.", "error");
    }
  }
}

function renderHwTotal(total) {
  var el = document.getElementById("hw-total");
  if (el) el.textContent = total + " piece" + (total !== 1 ? "s" : "") + " of equipment";
}

function renderHwCards(items) {
  var grid = document.getElementById("hw-grid");
  if (!grid) return;
  if (items.length === 0) {
    grid.innerHTML =
      '<div class="col-span-full flex flex-col items-center py-16 text-center">' +
        '<span class="material-symbols-outlined text-5xl text-slate-600 mb-3">precision_manufacturing</span>' +
        '<p class="text-slate-400 font-medium mb-1">No equipment found</p>' +
        '<p class="text-sm text-slate-600">Try adjusting your filters or add new equipment.</p>' +
      '</div>';
    return;
  }
  grid.innerHTML = items.map(function (item) {
    var statusInfo = hwStatusInfo(item.status);
    var catLabel = item.category ? escapeHtml(item.category) : "General";
    var loc = item.room || "No location set";
    var id = parseInt(item.id, 10);
    if (isNaN(id)) return "";
    var serial = item.serial_number
      ? '<div class="flex items-center gap-2 text-xs text-slate-400">' +
          '<span class="material-symbols-outlined text-sm">tag</span>' +
          'S/N: ' + escapeHtml(item.serial_number) +
        '</div>'
      : "";
    return '<div class="bg-surface-dark border border-border-dark rounded-xl p-5 hover:border-primary/30 transition-colors cursor-pointer group"' +
         ' onclick="openHwDetail(' + id + ')">' +
      '<div class="flex items-start justify-between mb-3">' +
        '<div class="flex items-center gap-2">' +
          '<span class="material-symbols-outlined text-2xl ' + statusInfo.iconColor + '">' + hwCategoryIcon(item.category) + '</span>' +
          '<span class="inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ' + statusInfo.cls + '">' + escapeHtml(statusInfo.label) + '</span>' +
        '</div>' +
      '</div>' +
      '<h3 class="text-sm font-semibold text-white mb-1 group-hover:text-primary transition-colors truncate">' + escapeHtml(item.name) + '</h3>' +
      '<p class="text-xs text-slate-500 mb-3 truncate">' + escapeHtml(item.manufacturer || "") + (item.model ? " " + escapeHtml(item.model) : "") + '</p>' +
      '<div class="space-y-1.5">' +
        '<div class="flex items-center gap-2 text-xs text-slate-400">' +
          '<span class="material-symbols-outlined text-sm">category</span>' +
          escapeHtml(catLabel) +
        '</div>' +
        '<div class="flex items-center gap-2 text-xs text-slate-400">' +
          '<span class="material-symbols-outlined text-sm">location_on</span>' +
          escapeHtml(loc) +
        '</div>' +
        serial +
      '</div>' +
    '</div>';
  }).join("");
}

function hwStatusInfo(status) {
  var map = {
    active:         { label: "Working",      cls: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20", iconColor: "text-emerald-400" },
    maintenance:    { label: "Maintenance",  cls: "bg-amber-500/10 text-amber-400 border border-amber-500/20",       iconColor: "text-amber-400"   },
    broken:         { label: "Needs Repair", cls: "bg-red-500/10 text-red-400 border border-red-500/20",             iconColor: "text-red-400"     },
    retired:        { label: "Retired",      cls: "bg-slate-700/50 text-slate-400 border border-slate-600",           iconColor: "text-slate-400"   },
    decommissioned: { label: "Removed",      cls: "bg-slate-700/50 text-slate-500 border border-slate-700",           iconColor: "text-slate-500"   },
  };
  return map[status] || { label: status || "Unknown", cls: "bg-slate-700/50 text-slate-400 border border-slate-600", iconColor: "text-slate-400" };
}

function hwCategoryIcon(category) {
  if (!category) return "precision_manufacturing";
  var c = category.toLowerCase();
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

var _hwCategoriesLoaded = false;

function loadHwCategories() {
  if (_hwCategoriesLoaded) return;
  var sel = document.getElementById("hw-category-filter");
  if (!sel) return;
  _hwCategoriesLoaded = true;
  // Fetch a broad page to discover all categories
  apiFetch(HW_API + "?page=1&page_size=200").then(function (r) { return r.json(); }).then(function (data) {
    var cats = new Set();
    (data.items || []).forEach(function (item) { if (item.category) cats.add(item.category); });
    var sorted = Array.from(cats).sort();
    sorted.forEach(function (cat) {
      var opt = document.createElement("option");
      opt.value = cat;
      opt.textContent = cat;
      sel.appendChild(opt);
    });
  }).catch(function () {});
}

function openHwDetail(id) {
  if (typeof id !== "number" || isNaN(id)) return;
  apiFetch(HW_API + "/" + id).then(function (r) { return r.json(); }).then(function (item) {
    var statusInfo = hwStatusInfo(item.status);
    var title = document.getElementById("detail-title");
    var body = document.getElementById("detail-body");
    var actions = document.getElementById("detail-actions");
    if (title) title.textContent = item.name;

    var value = item.estimated_value
      ? "$" + escapeHtml(parseFloat(item.estimated_value).toLocaleString(undefined, { minimumFractionDigits: 2 }))
      : "Not recorded";

    var descBlock = item.description
      ? '<div class="bg-background-dark/50 rounded-lg p-3 text-sm text-slate-300">' + escapeHtml(item.description) + '</div>'
      : "";

    var notesBlock = item.notes
      ? '<div>' +
          '<div class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Notes</div>' +
          '<div class="bg-background-dark/50 rounded-lg p-3 text-sm text-slate-300 whitespace-pre-wrap">' + escapeHtml(item.notes) + '</div>' +
        '</div>'
      : "";

    var apiText = item.is_api_controllable
      ? "Yes" + (item.api_interface ? " (" + escapeHtml(item.api_interface) + ")" : "")
      : "No";

    var addedDate = item.created_at ? escapeHtml(item.created_at.slice(0, 10)) : "unknown";
    var updatedDate = item.updated_at ? " &middot; Last updated " + escapeHtml(item.updated_at.slice(0, 10)) : "";

    if (body) body.innerHTML =
      '<div class="space-y-5">' +
        '<div class="flex items-center gap-3 mb-4">' +
          '<span class="material-symbols-outlined text-4xl ' + statusInfo.iconColor + '">' + hwCategoryIcon(item.category) + '</span>' +
          '<div>' +
            '<h3 class="text-lg font-semibold text-white">' + escapeHtml(item.name) + '</h3>' +
            '<span class="inline-block mt-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ' + statusInfo.cls + '">' + escapeHtml(statusInfo.label) + '</span>' +
          '</div>' +
        '</div>' +
        descBlock +
        '<div class="grid grid-cols-2 gap-4">' +
          hwDetailField("Manufacturer", escapeHtml(item.manufacturer || "Unknown"), "") +
          hwDetailField("Model", escapeHtml(item.model || "N/A"), "") +
          hwDetailField("Serial Number", escapeHtml(item.serial_number || "N/A"), "font-mono") +
          hwDetailField("System ID", escapeHtml(item.system_id || "N/A"), "font-mono") +
          hwDetailField("Category", escapeHtml(item.category || "General"), "") +
          hwDetailField("Location / Room", escapeHtml(item.room || "Not assigned"), "") +
          hwDetailField("Estimated Value", value, "") +
          hwDetailField("API Controllable", apiText, "") +
        '</div>' +
        notesBlock +
        '<div class="text-[10px] text-slate-600 pt-2 border-t border-border-dark">' +
          'Added ' + addedDate + updatedDate +
        '</div>' +
      '</div>';

    if (actions) actions.innerHTML =
      '<button onclick="closeDetail()" class="px-4 py-2 rounded-lg text-sm font-medium bg-background-dark text-slate-400 border border-border-dark hover:border-slate-500 transition-colors">Close</button>';

    document.getElementById("overlay").classList.add("show");
    document.getElementById("detail-panel").classList.add("open");
  }).catch(function () {
    showToast("Could not load equipment details.", "error");
  });
}

function hwDetailField(label, valueHtml, extraCls) {
  return '<div>' +
    '<div class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">' + escapeHtml(label) + '</div>' +
    '<div class="text-sm text-slate-200 ' + extraCls + '">' + valueHtml + '</div>' +
  '</div>';
}

function hwFilterChanged() {
  var statusSel = document.getElementById("hw-status-filter");
  var catSel = document.getElementById("hw-category-filter");
  hwStatus = statusSel ? statusSel.value : "";
  hwCategory = catSel ? catSel.value : "";
  hwPage = 0;
  loadHardware();
}

function hwSearchChanged() {
  var input = document.getElementById("hw-search-input");
  hwSearch = input ? input.value.trim() : "";
  hwPage = 0;
  loadHardware();
}

var _hwSearchTimer = null;
function hwSearchDebounce() {
  clearTimeout(_hwSearchTimer);
  _hwSearchTimer = setTimeout(hwSearchChanged, 300);
}

function renderHwPagination(page, pages) {
  var el = document.getElementById("hw-pagination");
  if (!el) return;
  el.innerHTML =
    '<button onclick="hwChangePage(-1)" ' + (page <= 1 ? "disabled" : "") +
      ' class="px-3 py-1.5 rounded-lg border border-border-dark bg-surface-dark text-slate-300 text-xs disabled:opacity-40 hover:border-primary/50 transition-colors">' +
      '<span class="material-symbols-outlined" style="font-size:14px;vertical-align:middle">chevron_left</span> Prev' +
    '</button>' +
    '<span class="text-xs text-slate-500">Page ' + page + ' of ' + pages + '</span>' +
    '<button onclick="hwChangePage(1)" ' + (page >= pages ? "disabled" : "") +
      ' class="px-3 py-1.5 rounded-lg border border-border-dark bg-surface-dark text-slate-300 text-xs disabled:opacity-40 hover:border-primary/50 transition-colors">' +
      'Next <span class="material-symbols-outlined" style="font-size:14px;vertical-align:middle">chevron_right</span>' +
    '</button>';
}

function hwChangePage(delta) {
  hwPage = Math.max(0, hwPage + delta);
  loadHardware();
}
