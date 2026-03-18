/**
 * Orders view — list, filter, detail with items, receive shipment.
 */
window.Lab = window.Lab || {};

window.Lab.orders = (function () {
  'use strict';
  var C = Lab.components;

  var currentPage = 1;
  var currentFilter = {};
  var searchTimer = null;
  var PAGE_SIZE = 30;

  async function init() {
    clearTimeout(searchTimer);
    setupEvents();
    await loadOrders();
  }

  function setupEvents() {
    var searchInput = document.getElementById('ord-search-input');
    if (searchInput) {
      searchInput.oninput = function () {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(function () {
          currentFilter.po_number = searchInput.value;
          currentPage = 1;
          loadOrders();
        }, 300);
      };
    }
  }

  async function loadOrders() {
    var params = Object.assign({ page: currentPage, page_size: PAGE_SIZE }, currentFilter);

    var data;
    try {
      data = await Lab.api.orders.list(params);
    } catch (_) {
      return;
    }

    var items = data.items || [];

    C.renderTable('orders-table', {
      columns: [
        { key: 'id', label: 'ID', width: '50px', render: function (v) { return '<span class="id">#' + v + '</span>'; } },
        { key: 'po_number', label: 'PO #', width: '160px', render: function (v) { return '<strong>' + C.esc(v || '') + '</strong>'; } },
        { key: 'vendor_name', label: 'Vendor', width: '1fr', render: function (v, row) {
          return C.esc(v || (row.vendor ? row.vendor.name : '') || '');
        }},
        { key: 'order_date', label: 'Date', width: '110px', render: function (v) { return C.esc(v || ''); } },
        { key: 'status', label: 'Status', width: '100px', render: function (v) { return C.badge(v); } },
        { key: 'item_count', label: 'Items', width: '60px', render: function (v) { return v || ''; } },
      ],
      rows: items,
      onRowClick: function (id) { openDetail(id); },
      emptyMsg: 'No orders found',
      pagination: {
        page: data.page || 1,
        pages: data.pages || 1,
        onChange: function (p) { currentPage = p; loadOrders(); },
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
    loadOrders();
  }

  async function openDetail(id) {
    var results = await Promise.allSettled([
      Lab.api.orders.get(id),
      Lab.api.orders.items(id),
    ]);

    if (results[0].status !== 'fulfilled') {
      var e = results[0].reason;
      if (e && e.message && e.message.indexOf('404') >= 0) {
        C.openPanel('Not Found', '<p style="color:var(--text-muted); padding:20px;">Order not found.</p>', '');
      } else {
        C.openPanel('Error', '<p style="color:var(--text-muted); padding:20px;">Failed to load order.</p>', '');
      }
      return;
    }

    var order = results[0].value;
    var orderItems = results[1].status === 'fulfilled'
      ? (results[1].value.items || results[1].value || [])
      : [];

    var bodyHtml = '';
    bodyHtml += '<div class="field-group"><h3>Order Info</h3>';
    bodyHtml += C.fieldRow('PO Number', '<strong>' + C.esc(order.po_number) + '</strong>');
    bodyHtml += C.fieldRow('Vendor', C.esc(order.vendor_name || (order.vendor ? order.vendor.name : '')));
    bodyHtml += C.fieldRow('Status', C.badge(order.status));
    bodyHtml += C.fieldRow('Order Date', C.esc(order.order_date || ''));
    bodyHtml += C.fieldRow('Ship Date', C.esc(order.ship_date || ''));
    bodyHtml += C.fieldRow('Received By', C.esc(order.received_by || ''));
    bodyHtml += C.fieldRow('Received Date', C.esc(order.received_date || ''));
    bodyHtml += '</div>';

    // Items table
    if (orderItems.length > 0) {
      bodyHtml += '<div class="field-group"><h3>Line Items (' + orderItems.length + ')</h3>';
      bodyHtml += '<table class="items-table"><thead><tr><th>Catalog #</th><th>Description</th><th>Qty</th><th>Unit</th><th>Lot #</th></tr></thead><tbody>';
      orderItems.forEach(function (it) {
        bodyHtml += '<tr>' +
          '<td><strong>' + C.esc(it.catalog_number || '') + '</strong></td>' +
          '<td>' + C.esc(it.description || '') + '</td>' +
          '<td>' + C.esc(String(it.quantity || '')) + '</td>' +
          '<td>' + C.esc(it.unit || '') + '</td>' +
          '<td>' + C.esc(it.lot_number || '') + '</td>' +
          '</tr>';
      });
      bodyHtml += '</tbody></table></div>';
    }

    // Actions
    var actionsHtml = '';
    if (order.status === 'pending') {
      actionsHtml = '<button class="btn btn-approve" onclick="Lab.orders.receiveOrder(' + id + ')">Mark Received</button>';
    } else {
      actionsHtml = '<span style="color:var(--text-muted); font-size:13px;">Status: ' + C.esc(order.status) +
        (order.received_by ? ' by ' + C.esc(order.received_by) : '') + '</span>';
    }

    C.openPanel('Order ' + (order.po_number || '#' + id), bodyHtml, actionsHtml);
  }

  function receiveOrder(id) {
    // Fetch order items to build the receive payload
    Lab.api.orders.items(id).catch(function (err) {
      C.toast('Failed to load order items', 'error');
      throw err;
    }).then(function (data) {
      var orderItems = data.items || data || [];
      C.showModal({
        title: 'Receive this order?',
        body: '<p>This will mark the order as received and create inventory records for ' +
          (orderItems.length || 'all') + ' item(s).</p>' +
          '<div class="field-row"><div class="field-label">Storage Location ID</div>' +
          '<div class="field-value"><input type="number" id="receive-location" value="1" min="1"></div></div>',
        confirmLabel: 'Receive',
        confirmClass: 'btn-approve',
        onConfirm: async function () {
          var locationId = parseInt(document.getElementById('receive-location').value) || 1;
          var items = orderItems.map(function (it) {
            return {
              order_item_id: it.id,
              product_id: it.product_id,
              quantity: it.quantity || 1,
              lot_number: it.lot_number || null,
              unit: it.unit || null,
            };
          });
          try {
            await Lab.api.orders.receive(id, {
              items: items,
              location_id: locationId,
              received_by: Lab.auth.userName(),
            });
            C.toast('Order received, inventory created!', 'success');
            C.closePanel();
            loadOrders();
          } catch (_) {}
        },
      });
    });
  }

  // Direct navigation to order detail (from hash route)
  function showOrderById(id) {
    openDetail(id);
  }

  return {
    init: init,
    loadOrders: loadOrders,
    setFilter: setFilter,
    openDetail: openDetail,
    receiveOrder: receiveOrder,
    showOrderById: showOrderById,
  };
})();
