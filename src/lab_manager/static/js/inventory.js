/**
 * Inventory view — list, filter, consume, transfer, adjust, dispose, open, history.
 */
window.Lab = window.Lab || {};

window.Lab.inventory = (function () {
  'use strict';
  var C = Lab.components;

  var currentPage = 1;
  var currentFilter = {};
  var searchTimer = null;
  var PAGE_SIZE = 30;

  async function init() {
    clearTimeout(searchTimer);
    setupEvents();
    await loadInventory();
  }

  function setupEvents() {
    var searchInput = document.getElementById('inv-search-input');
    if (searchInput) {
      searchInput.oninput = function () {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(function () {
          currentFilter.search = searchInput.value;
          currentPage = 1;
          loadInventory();
        }, 300);
      };
    }
  }

  async function loadInventory() {
    var params = Object.assign({ page: currentPage, page_size: PAGE_SIZE }, currentFilter);

    var data;
    try {
      data = await Lab.api.inventory.list(params);
    } catch (_) {
      return;
    }

    var items = data.items || [];

    C.renderTable('inventory-table', {
      columns: [
        { key: 'id', label: 'ID', width: '50px', render: function (v) { return '<span class="id">#' + v + '</span>'; } },
        { key: 'product_name', label: 'Product', width: '1fr', render: function (v, row) {
          var name = v || (row.product ? row.product.name : '') || '(unknown)';
          return '<div class="name">' + C.esc(name) + '</div>';
        }},
        { key: 'location_name', label: 'Location', width: '140px', render: function (v, row) {
          return C.esc(v || (row.location ? row.location.name : '') || '');
        }},
        { key: 'quantity_on_hand', label: 'Qty', width: '70px', render: function (v, row) {
          var unit = row.unit || '';
          return '<strong>' + (v != null ? v : 0) + '</strong>' + (unit ? ' ' + C.esc(unit) : '');
        }},
        { key: 'status', label: 'Status', width: '100px', render: function (v, row) {
          var badges = C.badge(v);
          // Expiry check
          if (row.expiry_date) {
            var exp = new Date(row.expiry_date);
            var now = new Date();
            if (exp < now) {
              badges += ' ' + C.badge('expired');
            } else {
              var daysLeft = Math.ceil((exp - now) / 86400000);
              if (daysLeft <= 30) {
                badges += ' <span style="color:var(--warning); font-size:11px;">' + daysLeft + 'd</span>';
              }
            }
          }
          return badges;
        }},
        { key: '_actions', label: '', width: '160px', render: function (_, row) {
          if (row.status === 'disposed') return '';
          var btns = '';
          var qty = row.quantity_on_hand || 0;
          btns += '<button class="btn btn-sm btn-secondary" onclick="event.stopPropagation(); Lab.inventory.consumeModal(' + row.id + ')"' +
            (qty <= 0 ? ' disabled title="Out of stock"' : '') + '>Consume</button> ';
          btns += '<button class="btn btn-sm btn-secondary" onclick="event.stopPropagation(); Lab.inventory.moreActions(' + row.id + ')">More</button>';
          return btns;
        }},
      ],
      rows: items.map(function (item) {
        if (item.status === 'disposed') item._disabled = true;
        return item;
      }),
      onRowClick: function (id) { openDetail(id); },
      emptyMsg: 'No inventory items',
      pagination: {
        page: data.page || 1,
        pages: data.pages || 1,
        onChange: function (p) { currentPage = p; loadInventory(); },
      },
    });
  }

  function setFilter(key, value) {
    if (value) {
      currentFilter[key] = value;
    } else {
      delete currentFilter[key];
    }
    currentPage = 1;
    loadInventory();
  }

  async function showLowStock() {
    currentFilter = {};
    try {
      var data = await Lab.api.inventory.lowStock();
      var items = data.items || data || [];
      C.renderTable('inventory-table', {
        columns: getColumns(),
        rows: items,
        onRowClick: function (id) { openDetail(id); },
        emptyMsg: 'No low stock items',
      });
    } catch (_) {}
  }

  async function showExpiring() {
    currentFilter = {};
    try {
      var data = await Lab.api.inventory.expiring(30);
      var items = data.items || data || [];
      C.renderTable('inventory-table', {
        columns: getColumns(),
        rows: items,
        onRowClick: function (id) { openDetail(id); },
        emptyMsg: 'No items expiring soon',
      });
    } catch (_) {}
  }

  function getColumns() {
    return [
      { key: 'id', label: 'ID', width: '50px', render: function (v) { return '#' + v; } },
      { key: 'product_name', label: 'Product', width: '1fr', render: function (v, row) {
        return C.esc(v || (row.product ? row.product.name : '') || '');
      }},
      { key: 'quantity_on_hand', label: 'Qty', width: '70px', render: function (v) { return '<strong>' + (v || 0) + '</strong>'; } },
      { key: 'status', label: 'Status', width: '100px', render: function (v) { return C.badge(v); } },
    ];
  }

  // ---- Detail panel ----

  async function openDetail(id) {
    var results = await Promise.allSettled([
      Lab.api.inventory.get(id),
      Lab.api.inventory.history(id),
    ]);

    if (results[0].status !== 'fulfilled') {
      C.openPanel('Not Found', '<p>Inventory item not found.</p>', '');
      return;
    }

    var item = results[0].value;

    var bodyHtml = '';
    bodyHtml += '<div class="field-group"><h3>Item Info</h3>';
    bodyHtml += C.fieldRow('Product', C.esc(item.product_name || (item.product ? item.product.name : '')));
    bodyHtml += C.fieldRow('Location', C.esc(item.location_name || (item.location ? item.location.name : '')));
    bodyHtml += C.fieldRow('Quantity', '<strong>' + (item.quantity_on_hand || 0) + '</strong> ' + C.esc(item.unit || ''));
    bodyHtml += C.fieldRow('Lot #', C.esc(item.lot_number));
    bodyHtml += C.fieldRow('Status', C.badge(item.status));
    bodyHtml += C.fieldRow('Expiry', C.esc(item.expiry_date || ''));
    bodyHtml += '</div>';

    // History
    if (results[1].status === 'fulfilled') {
      var history = results[1].value;
      var entries = Array.isArray(history) ? history : (history.items || []);
      if (entries.length > 0) {
        bodyHtml += '<div class="field-group"><h3>Activity History</h3><div class="history-list">';
        entries.forEach(function (e) {
          bodyHtml += '<div class="history-entry">' +
            '<div class="time">' + C.esc(e.created_at || e.timestamp || '') + '</div>' +
            '<div class="action">' + C.badge(e.action) + '</div>' +
            '<div>' + C.esc(e.note || e.reason || e.purpose || '') + '</div>' +
            '</div>';
        });
        bodyHtml += '</div></div>';
      }
    }

    // Actions
    var actionsHtml = '';
    if (item.status !== 'disposed') {
      var qty = item.quantity_on_hand || 0;
      actionsHtml += '<button class="btn btn-primary" onclick="Lab.inventory.consumeModal(' + id + ')"' +
        (qty <= 0 ? ' disabled' : '') + '>Consume</button>';
      actionsHtml += '<button class="btn btn-secondary" onclick="Lab.inventory.transferModal(' + id + ')">Transfer</button>';
      actionsHtml += '<button class="btn btn-secondary" onclick="Lab.inventory.adjustModal(' + id + ')">Adjust</button>';
      actionsHtml += '<button class="btn btn-reject" onclick="Lab.inventory.disposeModal(' + id + ')">Dispose</button>';
    }

    C.openPanel(item.product_name || 'Inventory Item', bodyHtml, actionsHtml);
  }

  // ---- Action modals ----

  function consumeModal(id) {
    C.showModal({
      title: 'Consume Inventory',
      body: '<label>Quantity</label><input type="number" id="consume-qty" min="1" value="1">' +
        '<label>Reason / Purpose</label><input type="text" id="consume-reason" placeholder="e.g. Western blot experiment">',
      confirmLabel: 'Consume',
      confirmClass: 'btn-primary',
      onConfirm: async function () {
        var qty = parseFloat(document.getElementById('consume-qty').value);
        if (isNaN(qty) || qty <= 0) { C.toast('Quantity must be a positive number', 'error'); return; }
        var reason = document.getElementById('consume-reason').value;
        try {
          await Lab.api.inventory.consume(id, {
            quantity: qty,
            consumed_by: Lab.auth.userName(),
            purpose: reason,
          });
          C.toast('Consumed ' + qty + ' units', 'success');
          C.closePanel();
          loadInventory();
        } catch (_) {}
      },
    });
  }

  function transferModal(id) {
    // Load locations
    C.showModal({
      title: 'Transfer Inventory',
      body: '<label>New Location</label><input type="number" id="transfer-location" placeholder="Location ID">' +
        '<p style="color:var(--text-muted); font-size:12px;">Enter the target location ID</p>',
      confirmLabel: 'Transfer',
      confirmClass: 'btn-primary',
      onConfirm: async function () {
        var locId = parseInt(document.getElementById('transfer-location').value);
        if (isNaN(locId) || locId <= 0) { C.toast('Enter a valid location ID', 'error'); return; }
        try {
          await Lab.api.inventory.transfer(id, {
            location_id: locId,
            transferred_by: Lab.auth.userName(),
          });
          C.toast('Transferred successfully', 'success');
          C.closePanel();
          loadInventory();
        } catch (_) {}
      },
    });
  }

  function adjustModal(id) {
    C.showModal({
      title: 'Adjust Inventory',
      body: '<label>New Quantity</label><input type="number" id="adjust-qty" min="0">' +
        '<label>Reason</label><input type="text" id="adjust-reason" placeholder="e.g. Physical count correction">',
      confirmLabel: 'Adjust',
      confirmClass: 'btn-primary',
      onConfirm: async function () {
        var qty = parseFloat(document.getElementById('adjust-qty').value);
        if (isNaN(qty) || qty < 0) { C.toast('Quantity must be zero or positive', 'error'); return; }
        var reason = document.getElementById('adjust-reason').value;
        try {
          await Lab.api.inventory.adjust(id, {
            new_quantity: qty,
            reason: reason,
            adjusted_by: Lab.auth.userName(),
          });
          C.toast('Adjusted to ' + qty, 'success');
          C.closePanel();
          loadInventory();
        } catch (_) {}
      },
    });
  }

  function disposeModal(id) {
    C.showModal({
      title: 'Dispose Inventory',
      body: '<label>Reason</label><input type="text" id="dispose-reason" placeholder="e.g. Expired 2026-03-01">',
      confirmLabel: 'Dispose',
      confirmClass: 'btn-reject',
      onConfirm: async function () {
        var reason = document.getElementById('dispose-reason').value;
        try {
          await Lab.api.inventory.dispose(id, {
            reason: reason,
            disposed_by: Lab.auth.userName(),
          });
          C.toast('Item disposed', 'success');
          C.closePanel();
          loadInventory();
        } catch (_) {}
      },
    });
  }

  function moreActions(id) {
    C.showModal({
      title: 'More Actions',
      body: '<div style="display:flex; flex-direction:column; gap:8px;">' +
        '<button class="btn btn-secondary" onclick="Lab.components.closeModal(); Lab.inventory.transferModal(' + id + ')">Transfer to another location</button>' +
        '<button class="btn btn-secondary" onclick="Lab.components.closeModal(); Lab.inventory.adjustModal(' + id + ')">Adjust quantity (physical count)</button>' +
        '<button class="btn btn-secondary" onclick="Lab.components.closeModal(); Lab.inventory.openItem(' + id + ')">Mark as opened</button>' +
        '<button class="btn btn-reject" onclick="Lab.components.closeModal(); Lab.inventory.disposeModal(' + id + ')">Dispose / Discard</button>' +
        '</div>',
      confirmLabel: 'Close',
      confirmClass: 'btn-secondary',
      onConfirm: function () {},
    });
  }

  async function openItem(id) {
    try {
      await Lab.api.inventory.open(id, {
        opened_by: Lab.auth.userName(),
      });
      C.toast('Item marked as opened', 'success');
      loadInventory();
    } catch (_) {}
  }

  return {
    init: init,
    loadInventory: loadInventory,
    setFilter: setFilter,
    showLowStock: showLowStock,
    showExpiring: showExpiring,
    openDetail: openDetail,
    consumeModal: consumeModal,
    transferModal: transferModal,
    adjustModal: adjustModal,
    disposeModal: disposeModal,
    moreActions: moreActions,
    openItem: openItem,
  };
})();
