// queue.js — Unified PI Decision Queue
"use strict";

const PRIORITY_STYLES = {
  HIGH: "border-red-500/50 bg-red-500/5",
  MEDIUM: "border-amber-500/50 bg-amber-500/5",
  LOW: "border-blue-500/50 bg-blue-500/5",
};

const PRIORITY_BADGE = {
  HIGH: "bg-red-500/20 text-red-400",
  MEDIUM: "bg-amber-500/20 text-amber-400",
  LOW: "bg-blue-500/20 text-blue-400",
};

const TYPE_LABELS = {
  order_request: "Approval",
  document: "Review",
  alert: "Alert",
};

const TYPE_ICONS = {
  order_request: "shopping_cart",
  document: "description",
  alert: "warning",
};

let queueFilter = "all";

async function loadQueue() {
  try {
    const params = new URLSearchParams();
    if (queueFilter !== "all") {
      params.set("item_type", queueFilter);
    }
    const url = "/api/v1/queue/" + (params.toString() ? "?" + params.toString() : "");
    const r = await apiFetch(url);
    if (!r.ok) throw new Error("Failed to load queue");
    const data = await r.json();
    renderQueue(data);
    updateQueueBadge(data.total);
  } catch (err) {
    if (err.message !== "Unauthorized") {
      console.error("Failed to load queue:", err);
      showToast("Failed to load decision queue.", "error");
    }
  }
}

function updateQueueBadge(count) {
  const badge = document.getElementById("queue-badge");
  if (!badge) return;
  if (count > 0) {
    badge.textContent = count > 99 ? "99+" : count;
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }
}

function renderQueue(data) {
  const container = document.getElementById("queue-items");
  if (!container) return;

  const { items, total, counts } = data;

  // Update count displays
  const totalEl = document.getElementById("queue-total");
  if (totalEl) totalEl.textContent = total + " items";

  const reqCount = document.getElementById("queue-count-requests");
  const docCount = document.getElementById("queue-count-documents");
  const alertCount = document.getElementById("queue-count-alerts");
  if (reqCount) reqCount.textContent = counts.order_requests;
  if (docCount) docCount.textContent = counts.documents;
  if (alertCount) alertCount.textContent = counts.alerts;

  // Update filter button active states
  document.querySelectorAll("[data-queue-filter]").forEach((btn) => {
    const isActive = btn.dataset.queueFilter === queueFilter;
    btn.classList.toggle("bg-primary", isActive);
    btn.classList.toggle("text-white", isActive);
    btn.classList.toggle("border-primary", isActive);
    btn.classList.toggle("bg-surface-dark", !isActive);
    btn.classList.toggle("text-slate-400", !isActive);
    btn.classList.toggle("border-border-dark", !isActive);
  });

  if (items.length === 0) {
    container.innerHTML = `
      <div class="flex flex-col items-center justify-center py-16 text-slate-500">
        <span class="material-symbols-outlined text-5xl mb-3">check_circle</span>
        <p class="text-lg font-medium">All caught up!</p>
        <p class="text-sm">No items need your attention right now.</p>
      </div>`;
    return;
  }

  // Group items by type
  const grouped = { alert: [], order_request: [], document: [] };
  for (const item of items) {
    if (grouped[item.type]) {
      grouped[item.type].push(item);
    }
  }

  let html = "";

  // Alerts section (HIGH priority)
  if (grouped.alert.length > 0) {
    html += renderSection("Alerts", "warning", grouped.alert);
  }

  // Approvals section (MEDIUM priority)
  if (grouped.order_request.length > 0) {
    html += renderSection("Approvals", "shopping_cart", grouped.order_request);
  }

  // Reviews section (LOW priority)
  if (grouped.document.length > 0) {
    html += renderSection("Reviews", "description", grouped.document);
  }

  container.innerHTML = html;
}

function renderSection(title, icon, items) {
  const cardsHtml = items.map(renderCard).join("");
  return `
    <div class="mb-6">
      <div class="flex items-center gap-2 mb-3">
        <span class="material-symbols-outlined text-lg text-slate-400">${icon}</span>
        <h3 class="text-sm font-semibold text-slate-300 uppercase tracking-wider">${escapeHtml(title)}</h3>
        <span class="text-xs text-slate-500">(${items.length})</span>
      </div>
      <div class="space-y-2">
        ${cardsHtml}
      </div>
    </div>`;
}

function renderCard(item) {
  const priorityClass = PRIORITY_STYLES[item.priority] || PRIORITY_STYLES.LOW;
  const badgeClass = PRIORITY_BADGE[item.priority] || PRIORITY_BADGE.LOW;
  const typeLabel = TYPE_LABELS[item.type] || item.type;
  const typeIcon = TYPE_ICONS[item.type] || "info";

  let actionsHtml = "";
  if (item.type === "order_request") {
    actionsHtml = `
      <button onclick="queueAction('approve', ${item.id}, 'order_request')"
        class="px-3 py-1.5 text-xs font-medium bg-accent-green/20 text-accent-green rounded-lg hover:bg-accent-green/30 transition-colors border border-accent-green/20">
        Approve
      </button>
      <button onclick="queueAction('reject', ${item.id}, 'order_request')"
        class="px-3 py-1.5 text-xs font-medium bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-colors border border-red-500/20">
        Reject
      </button>`;
  } else if (item.type === "document") {
    actionsHtml = `
      <button onclick="queueNavigate('review')"
        class="px-3 py-1.5 text-xs font-medium bg-primary/20 text-primary rounded-lg hover:bg-primary/30 transition-colors border border-primary/20">
        Review
      </button>`;
  } else if (item.type === "alert") {
    actionsHtml = `
      <button onclick="queueAction('resolve', ${item.id}, 'alert')"
        class="px-3 py-1.5 text-xs font-medium bg-accent-green/20 text-accent-green rounded-lg hover:bg-accent-green/30 transition-colors border border-accent-green/20">
        Resolve
      </button>`;
  }

  return `
    <div class="border ${priorityClass} rounded-xl p-4 flex items-start gap-4 transition-colors hover:bg-white/[0.02]">
      <div class="flex-shrink-0 mt-0.5">
        <span class="material-symbols-outlined text-xl text-slate-400">${typeIcon}</span>
      </div>
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-1">
          <span class="text-sm font-medium text-slate-200 truncate">${escapeHtml(item.title)}</span>
          <span class="px-1.5 py-0.5 text-[10px] font-semibold rounded ${badgeClass} uppercase">${item.priority}</span>
          <span class="px-1.5 py-0.5 text-[10px] font-medium rounded bg-slate-500/20 text-slate-400">${typeLabel}</span>
        </div>
        <p class="text-xs text-slate-400 truncate">${escapeHtml(item.description)}</p>
        <p class="text-[10px] text-slate-600 mt-1">${item.created_at ? new Date(item.created_at).toLocaleString() : ""}</p>
      </div>
      <div class="flex items-center gap-2 flex-shrink-0">
        ${actionsHtml}
      </div>
    </div>`;
}

function setQueueFilter(btn, filter) {
  queueFilter = filter;
  loadQueue();
}

async function queueAction(action, id, type) {
  try {
    let url, method;
    if (type === "order_request") {
      method = "POST";
      url = `/api/v1/requests/${id}/${action}`;
    } else if (type === "alert") {
      method = "POST";
      url = `/api/v1/alerts/${id}/resolve`;
    } else {
      return;
    }

    const body = action === "reject" ? JSON.stringify({ note: "Rejected from queue" }) : "{}";
    const r = await apiFetch(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: body,
    });

    if (r.ok) {
      const label = action === "approve" ? "Approved" : action === "reject" ? "Rejected" : "Resolved";
      showToast(`${label} successfully.`, "success");
      loadQueue();
    } else {
      const err = await r.json().catch(() => ({ detail: "Action failed" }));
      showToast(err.detail || "Action failed.", "error");
    }
  } catch (err) {
    if (err.message !== "Unauthorized") {
      showToast("Network error.", "error");
    }
  }
}

function queueNavigate(target) {
  navigateTo(target);
}
