/**
 * Dashboard view — stat cards, alert banners, vendor/type charts.
 */
window.Lab = window.Lab || {};

window.Lab.dashboard = (function () {
  'use strict';
  var C = Lab.components;

  var stats = null;

  async function init() {
    try {
      stats = await Lab.api.documents.stats();
    } catch (_) {
      return;
    }
    render();
  }

  function render() {
    if (!stats) return;
    var s = stats;

    // Stat cards
    var grid = document.getElementById('stats-grid');
    if (!grid) return;

    var needsReview = s.by_status.needs_review || 0;
    var warningClass = needsReview > 0 ? ' warning' : '';

    grid.innerHTML =
      '<div class="stat-card">' +
        '<div class="label">Total Documents</div>' +
        '<div class="value">' + s.total_documents + '</div>' +
        '<div class="sub">scanned lab documents</div>' +
      '</div>' +
      '<div class="stat-card">' +
        '<div class="label">Approved</div>' +
        '<div class="value" style="color:var(--success)">' + (s.by_status.approved || 0) + '</div>' +
        '<div class="sub">' + (s.total_documents > 0 ? ((s.by_status.approved || 0) / s.total_documents * 100).toFixed(0) : 0) + '% auto-approved</div>' +
      '</div>' +
      '<div class="stat-card' + warningClass + '">' +
        '<div class="label">Needs Review</div>' +
        '<div class="value"' + (needsReview > 0 ? ' style="color:var(--warning)"' : '') + '>' + needsReview + '</div>' +
        '<div class="sub">awaiting scientist verification</div>' +
      '</div>' +
      '<div class="stat-card">' +
        '<div class="label">Orders Created</div>' +
        '<div class="value">' + s.total_orders + '</div>' +
        '<div class="sub">' + s.total_items + ' line items</div>' +
      '</div>' +
      '<div class="stat-card">' +
        '<div class="label">Vendors</div>' +
        '<div class="value">' + s.total_vendors + '</div>' +
        '<div class="sub">discovered from scans</div>' +
      '</div>';

    // Alert banners
    renderAlerts();

    // Vendor chart
    var vc = document.getElementById('vendor-chart');
    if (vc && s.top_vendors && s.top_vendors.length > 0) {
      var maxCount = Math.max.apply(null, s.top_vendors.map(function (v) { return v.count; }));
      vc.innerHTML = s.top_vendors.map(function (v) {
        return '<div class="vendor-bar">' +
          '<div class="name" title="' + C.esc(v.name || '') + '">' + C.esc(v.name || '') + '</div>' +
          '<div class="bar" style="width:' + (v.count / maxCount * 200) + 'px"></div>' +
          '<div class="count">' + v.count + '</div></div>';
      }).join('');
    } else if (vc) {
      vc.innerHTML = '<div style="color:var(--text-muted); font-size:13px;">No vendor data yet</div>';
    }

    // Type chart
    var tc = document.getElementById('type-chart');
    if (tc && s.by_type) {
      var types = Object.entries(s.by_type)
        .filter(function (e) { return e[0] && e[0] !== 'null' && e[0] !== 'None'; })
        .sort(function (a, b) { return b[1] - a[1]; });
      if (types.length > 0) {
        var maxType = Math.max.apply(null, types.map(function (e) { return e[1]; }));
        tc.innerHTML = types.map(function (e) {
          return '<div class="vendor-bar">' +
            '<div class="name">' + C.esc(C.humanize(e[0])) + '</div>' +
            '<div class="bar" style="width:' + (e[1] / maxType * 200) + 'px; background:var(--chart-secondary)"></div>' +
            '<div class="count">' + e[1] + '</div></div>';
        }).join('');
      } else {
        tc.innerHTML = '<div style="color:var(--text-muted); font-size:13px;">No type data yet</div>';
      }
    }
  }

  async function renderAlerts() {
    var container = document.getElementById('dashboard-alerts');
    if (!container) return;
    var html = '';

    var results = await Promise.allSettled([
      Lab.api.inventory.lowStock(),
      Lab.api.inventory.expiring(30),
    ]);

    if (results[0].status === 'fulfilled') {
      var lowItems = results[0].value.items || results[0].value;
      if (Array.isArray(lowItems) && lowItems.length > 0) {
        html += '<div class="alert-banner">' +
          '<span class="alert-count">' + lowItems.length + '</span>' +
          ' items are below reorder level (low stock)' +
          '</div>';
      }
    }

    if (results[1].status === 'fulfilled') {
      var expItems = results[1].value.items || results[1].value;
      if (Array.isArray(expItems) && expItems.length > 0) {
        html += '<div class="alert-banner" style="background:var(--danger-bg); border-color:var(--danger);">' +
          '<span class="alert-count" style="background:var(--danger);">' + expItems.length + '</span>' +
          ' items expiring within 30 days' +
          '</div>';
      }
    }

    container.innerHTML = html;
  }

  return { init: init, render: render };
})();
