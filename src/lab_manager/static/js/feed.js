// feed.js — Proactive AI feed page: alerts, activity, and suggestions
"use strict";

let feedRefreshTimer = null;

const FEED_TYPE_ICONS = {
  alert: "notifications_active",
  activity: "history",
  suggestion: "lightbulb",
};

const PRIORITY_STYLES = {
  high: "bg-red-500/15 text-red-400 border-red-500/30",
  medium: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  low: "bg-slate-500/15 text-slate-400 border-slate-500/30",
};

const PRIORITY_LABELS = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

function _relativeDate(isoTs) {
  if (!isoTs) return "Unknown";
  const d = new Date(isoTs);
  const now = new Date();
  const diff = now - d;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return mins + "m ago";
  const hours = Math.floor(mins / 60);
  if (hours < 24) return hours + "h ago";
  const days = Math.floor(hours / 24);
  if (days === 1) return "Yesterday";
  if (days < 7) return days + "d ago";
  return d.toLocaleDateString();
}

function _dateGroup(isoTs) {
  if (!isoTs) return "Older";
  const d = new Date(isoTs);
  const now = new Date();
  const diff = now - d;
  const days = Math.floor(diff / 86400000);
  if (days < 1) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return "This Week";
  return "Older";
}

function _renderFeedItem(item) {
  const icon = FEED_TYPE_ICONS[item.type] || "info";
  const priorityClass = PRIORITY_STYLES[item.priority] || PRIORITY_STYLES.low;
  const priorityLabel = PRIORITY_LABELS[item.priority] || "Low";
  const readClass = item.is_read ? "opacity-60" : "";
  const relDate = _relativeDate(item.timestamp);

  return `<div class="flex gap-3 p-4 border-b border-border-dark hover:bg-background-dark/30 transition-colors cursor-pointer ${readClass}" data-feed-id="${item.id}" onclick="markFeedRead('${item.id}')">
    <div class="flex-shrink-0 w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
      <span class="material-symbols-outlined text-primary text-lg">${icon}</span>
    </div>
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2 mb-1">
        <span class="text-sm font-medium text-slate-200 truncate">${item.title}</span>
        <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border ${priorityClass}">${priorityLabel}</span>
      </div>
      <p class="text-xs text-slate-400 line-clamp-2">${item.description}</p>
    </div>
    <div class="flex-shrink-0 text-right">
      <span class="text-[11px] text-slate-500">${relDate}</span>
      ${item.action_url ? `<div class="mt-1"><a href="${item.action_url}" class="text-[11px] text-primary hover:underline">View</a></div>` : ""}
    </div>
  </div>`;
}

function _renderFeedGroup(groupName, items) {
  if (!items.length) return "";
  return `<div class="mb-4">
    <div class="px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider bg-background-dark/50">${groupName}</div>
    ${items.map(_renderFeedItem).join("")}
  </div>`;
}

async function loadFeed() {
  const container = document.getElementById("feed-items");
  const countEl = document.getElementById("feed-count");
  if (!container) return;

  container.innerHTML = `<div class="flex items-center justify-center py-12 text-slate-500">
    <span class="material-symbols-outlined animate-spin text-xl mr-2">progress_activity</span>Loading feed...
  </div>`;

  try {
    const r = await fetch("/api/v1/feed/");
    if (!r.ok) throw new Error("Failed to load feed");
    const data = await r.json();
    const items = data.items || [];

    if (countEl) {
      const unread = items.filter((i) => !i.is_read).length;
      countEl.textContent = unread > 0 ? unread : "";
      countEl.classList.toggle("hidden", unread === 0);
    }

    if (!items.length) {
      container.innerHTML = `<div class="flex flex-col items-center justify-center py-16 text-slate-500">
        <span class="material-symbols-outlined text-4xl mb-3">notifications_off</span>
        <p class="text-sm">No feed items yet</p>
        <p class="text-xs text-slate-600 mt-1">Alerts and activity will appear here</p>
      </div>`;
      return;
    }

    const groups = { Today: [], Yesterday: [], "This Week": [], Older: [] };
    for (const item of items) {
      const g = _dateGroup(item.timestamp);
      if (groups[g]) groups[g].push(item);
      else groups["Older"].push(item);
    }

    container.innerHTML =
      _renderFeedGroup("Today", groups["Today"]) +
      _renderFeedGroup("Yesterday", groups["Yesterday"]) +
      _renderFeedGroup("This Week", groups["This Week"]) +
      _renderFeedGroup("Older", groups["Older"]);
  } catch (e) {
    container.innerHTML = `<div class="flex items-center justify-center py-12 text-red-400 text-sm">Failed to load feed</div>`;
  }

  // Auto-refresh every 60 seconds
  if (feedRefreshTimer) clearInterval(feedRefreshTimer);
  feedRefreshTimer = setInterval(() => {
    if (window.location.hash === "#feed") loadFeed();
  }, 60000);
}

async function markFeedRead(itemId) {
  // Optimistically mark as read in the UI
  const el = document.querySelector(`[data-feed-id="${itemId}"]`);
  if (el) el.classList.add("opacity-60");

  try {
    await fetch(`/api/v1/feed/${itemId}/read`, { method: "POST" });
  } catch {}
}
