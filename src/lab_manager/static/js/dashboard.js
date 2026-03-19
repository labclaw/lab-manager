// dashboard.js — Stats loading & rendering, vendor chart, type chart
"use strict";

let stats = null;

async function loadStats() {
  try {
    const r = await apiFetch(API + "/stats");
    stats = await r.json();
    renderStats();
  } catch (err) {
    if (err.message !== "Unauthorized") {
      console.error("Failed to load stats:", err);
      showToast("Failed to load dashboard data.", "error");
    }
  }
}

function renderStats() {
  const s = stats;
  if (!s) return;

  const grid = document.getElementById("stats-grid");
  const cards = [
    {
      icon: "description",
      label: "Total Documents",
      value: s.total_documents,
      sub: "scanned lab documents",
      color: "text-primary",
    },
    {
      icon: "check_circle",
      label: "Approved",
      value: s.by_status.approved || 0,
      sub:
        (s.total_documents > 0
          ? (((s.by_status.approved || 0) / s.total_documents) * 100).toFixed(0)
          : 0) + "% auto-approved",
      color: "text-accent-green",
    },
    {
      icon: "pending",
      label: "Needs Review",
      value: s.by_status.needs_review || 0,
      sub: "awaiting scientist verification",
      color: "text-amber-400",
    },
    {
      icon: "shopping_cart",
      label: "Orders",
      value: s.total_orders,
      sub: s.total_items + " line items",
      color: "text-primary",
    },
    {
      icon: "store",
      label: "Vendors",
      value: s.total_vendors,
      sub: "discovered from scans",
      color: "text-primary",
    },
  ];

  grid.innerHTML = cards
    .map(
      (c) => `
    <div class="bg-surface-dark border border-border-dark rounded-xl p-5">
      <div class="flex items-center gap-3 mb-2">
        <span class="material-symbols-outlined text-slate-500 text-xl">${c.icon}</span>
        <span class="text-xs text-slate-500 uppercase tracking-wider font-medium">${c.label}</span>
      </div>
      <div class="text-3xl font-bold ${c.color}">${c.value}</div>
      <div class="text-xs text-slate-500 mt-1">${c.sub}</div>
    </div>`
    )
    .join("");

  // Alert banners
  const alertContainer = document.getElementById("alert-banners");
  const alerts = [];
  if ((s.by_status.needs_review || 0) > 10) {
    alerts.push({
      icon: "warning",
      cls: "border-amber-500/30 bg-amber-500/5",
      text: `${s.by_status.needs_review} documents awaiting review`,
    });
  }
  alertContainer.innerHTML = alerts
    .map(
      (a) => `
    <div class="flex items-center gap-3 p-3 rounded-lg border ${a.cls}">
      <span class="material-symbols-outlined text-amber-400">${a.icon}</span>
      <span class="text-sm text-slate-300">${a.text}</span>
    </div>`
    )
    .join("");

  // Vendor chart
  renderVendorChart(s);
  // Type chart
  renderTypeChart(s);
}

function renderVendorChart(s) {
  const vc = document.getElementById("vendor-chart");
  if (!s.top_vendors || s.top_vendors.length === 0) {
    vc.innerHTML =
      '<div class="text-slate-500 text-sm py-4">No vendor data yet</div>';
    return;
  }
  const maxCount = Math.max(...s.top_vendors.map((v) => v.count));
  vc.innerHTML = s.top_vendors
    .map(
      (v) => `
    <div class="flex items-center gap-3 mb-2 text-sm">
      <div class="w-36 text-right text-slate-400 truncate" title="${escapeHtml(v.name || "")}">${escapeHtml(v.name || "")}</div>
      <div class="h-5 bg-primary rounded" style="width: ${(v.count / maxCount) * 200}px; min-width: 4px;"></div>
      <div class="text-slate-300 font-semibold w-8">${v.count}</div>
    </div>`
    )
    .join("");
}

function renderTypeChart(s) {
  const tc = document.getElementById("type-chart");
  const types = Object.entries(s.by_type)
    .filter(([k]) => k && k !== "null" && k !== "None")
    .sort((a, b) => b[1] - a[1]);
  if (types.length === 0) {
    tc.innerHTML =
      '<div class="text-slate-500 text-sm py-4">No type data yet</div>';
    return;
  }
  const maxType = Math.max(...types.map(([, c]) => c));
  tc.innerHTML = types
    .map(
      ([name, count]) => `
    <div class="flex items-center gap-3 mb-2 text-sm">
      <div class="w-36 text-right text-slate-400 truncate">${escapeHtml(name || "")}</div>
      <div class="h-5 bg-accent-green rounded" style="width: ${(count / maxType) * 200}px; min-width: 4px;"></div>
      <div class="text-slate-300 font-semibold w-8">${count}</div>
    </div>`
    )
    .join("");
}
