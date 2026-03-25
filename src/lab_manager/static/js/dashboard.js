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

async function renderStats() {
  const s = stats;
  if (!s) {
    const grid = document.getElementById("stats-grid");
    if (grid) grid.innerHTML = '<p class="text-slate-500 col-span-full text-center py-8">Unable to load dashboard data. Try refreshing the page.</p>';
    return;
  }

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
      sub: parseInt(s.total_items, 10) + " line items",
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
        <span class="material-symbols-outlined text-slate-500 text-xl">${escapeHtml(c.icon)}</span>
        <span class="text-xs text-slate-500 uppercase tracking-wider font-medium">${escapeHtml(c.label)}</span>
      </div>
      <div class="text-3xl font-bold ${escapeHtml(c.color)}">${escapeHtml(String(c.value))}</div>
      <div class="text-xs text-slate-500 mt-1">${escapeHtml(c.sub)}</div>
    </div>`
    )
    .join("");

  // Update sidebar review badge
  const reviewBadge = document.getElementById("review-badge");
  const reviewCount = s.by_status.needs_review || 0;
  if (reviewBadge) {
    if (reviewCount > 0) {
      reviewBadge.textContent = reviewCount > 99 ? "99+" : String(reviewCount);
      reviewBadge.classList.remove("hidden");
    } else {
      reviewBadge.classList.add("hidden");
    }
  }

  // Proactive alert banners — fetch real alerts from backend
  const alertContainer = document.getElementById("alert-banners");
  const banners = [];

  // Document review backlog
  if (reviewCount > 0) {
    banners.push({
      icon: "fact_check",
      cls: "border-amber-500/30 bg-amber-500/5",
      iconCls: "text-amber-400",
      text: `${reviewCount} document${reviewCount !== 1 ? "s" : ""} awaiting your review`,
      action: "review",
      actionLabel: "Review now",
    });
  }

  // Fetch inventory alerts (expiring + low stock) in parallel
  try {
    const [expiringR, lowStockR, alertSummaryR] = await Promise.all([
      apiFetch("/api/v1/inventory/expiring?days=7&page_size=1").catch(() => null),
      apiFetch("/api/v1/inventory/low-stock?page_size=1").catch(() => null),
      apiFetch("/api/v1/alerts/summary").catch(() => null),
    ]);

    if (expiringR && expiringR.ok) {
      const expData = await expiringR.json();
      const expCount = expData.total || 0;
      if (expCount > 0) {
        banners.push({
          icon: "schedule",
          cls: "border-red-500/30 bg-red-500/5",
          iconCls: "text-red-400",
          text: `${expCount} item${expCount !== 1 ? "s" : ""} expiring within 7 days`,
          action: "inventory",
          actionLabel: "View items",
        });
      }
    }

    if (lowStockR && lowStockR.ok) {
      const lsData = await lowStockR.json();
      const lsItems = lsData.items || lsData;
      const lsCount = Array.isArray(lsItems) ? lsItems.length : 0;
      if (lsCount > 0) {
        banners.push({
          icon: "inventory_2",
          cls: "border-orange-500/30 bg-orange-500/5",
          iconCls: "text-orange-400",
          text: `${lsCount} product${lsCount !== 1 ? "s" : ""} below reorder level`,
          action: "inventory",
          actionLabel: "Check stock",
        });
      }
    }

    if (alertSummaryR && alertSummaryR.ok) {
      const summary = await alertSummaryR.json();
      const criticalCount = (summary.by_severity || {}).critical || 0;
      if (criticalCount > 0) {
        banners.push({
          icon: "error",
          cls: "border-red-500/30 bg-red-500/5",
          iconCls: "text-red-400",
          text: `${criticalCount} critical alert${criticalCount !== 1 ? "s" : ""} require attention`,
          action: null,
          actionLabel: null,
        });
      }
    }
  } catch {
    // Non-blocking: alerts are optional
  }

  alertContainer.innerHTML = banners
    .map(
      (a) => `
    <div class="flex items-center gap-3 p-3 rounded-lg border ${escapeHtml(a.cls)}">
      <span class="material-symbols-outlined ${escapeHtml(a.iconCls)}">${escapeHtml(a.icon)}</span>
      <span class="text-sm text-slate-300 flex-1">${escapeHtml(a.text)}</span>
      ${a.action ? `<button onclick="navigateTo('${escapeHtml(a.action)}')" class="text-xs font-medium text-primary hover:text-primary/80 transition-colors whitespace-nowrap">${escapeHtml(a.actionLabel)} &rarr;</button>` : ""}
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
      <div class="text-slate-300 font-semibold w-8">${parseInt(v.count, 10)}</div>
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
      <div class="text-slate-300 font-semibold w-8">${parseInt(count, 10)}</div>
    </div>`
    )
    .join("");
}
