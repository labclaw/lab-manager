/**
 * Review Queue view — needs_review documents with bulk approve/reject.
 */
window.Lab = window.Lab || {};

window.Lab.review = (function () {
  'use strict';
  var C = Lab.components;

  var selected = new Set();
  var docs = [];

  async function init() {
    selected.clear();
    await loadQueue();
  }

  async function loadQueue() {
    var data;
    try {
      data = await Lab.api.documents.list({ status: 'needs_review', page_size: 200 });
    } catch (_) {
      return;
    }
    docs = data.items || [];
    render();
  }

  function render() {
    // Bulk action bar
    var bulkBar = document.getElementById('review-bulk-bar');
    if (bulkBar) {
      if (selected.size > 0) {
        bulkBar.classList.remove('hidden');
        bulkBar.innerHTML =
          '<span class="bulk-count">' + selected.size + ' selected</span>' +
          '<button class="btn btn-sm btn-approve" onclick="Lab.review.bulkApprove()">Approve Selected</button>' +
          '<button class="btn btn-sm btn-reject" onclick="Lab.review.bulkReject()">Reject Selected</button>';
      } else {
        bulkBar.classList.add('hidden');
        bulkBar.innerHTML = '';
      }
    }

    C.renderTable('review-table', {
      columns: [
        { key: 'id', label: 'ID', width: '60px', render: function (v) { return '<span class="id">#' + v + '</span>'; } },
        { key: 'file_name', label: 'File / Vendor', width: '1fr', render: function (v, row) {
          return '<div><div class="name">' + C.esc(v || '') + '</div><div class="sub-text">' + C.esc(row.vendor_name || '') + '</div></div>';
        }},
        { key: 'document_type', label: 'Type', width: '140px', render: function (v) { return C.esc(v || ''); } },
        { key: 'status', label: 'Status', width: '120px', render: function (v) { return C.badge(v); } },
        { key: 'extraction_confidence', label: 'Conf.', width: '80px', render: function (v) {
          return v != null ? (v * 100).toFixed(0) + '%' : '&mdash;';
        }},
      ],
      rows: docs,
      onRowClick: function (id) { Lab.documents.openDetail(id); },
      emptyMsg: 'No documents need review',
      checkbox: {
        selected: selected,
        onToggle: function (id) {
          if (selected.has(id)) selected.delete(id);
          else selected.add(id);
          render();
        },
        onToggleAll: function () {
          if (selected.size === docs.length) {
            selected.clear();
          } else {
            docs.forEach(function (d) { selected.add(d.id); });
          }
          render();
        },
      },
    });
  }

  function bulkApprove() {
    if (selected.size === 0) return;
    var count = selected.size;
    C.showModal({
      title: 'Approve ' + count + ' documents?',
      body: '<p>This will approve ' + count + ' documents and create orders for each.</p>',
      confirmLabel: 'Approve ' + count,
      confirmClass: 'btn-approve',
      onConfirm: function () { executeBulk('approve'); },
    });
  }

  function bulkReject() {
    if (selected.size === 0) return;
    var count = selected.size;
    C.showModal({
      title: 'Reject ' + count + ' documents?',
      body: '<label>Reason (applied to all)</label>' +
        '<textarea id="bulk-reject-reason" placeholder="Reason for rejection (optional)..."></textarea>',
      confirmLabel: 'Reject ' + count,
      confirmClass: 'btn-reject',
      onConfirm: function () {
        var textarea = document.getElementById('bulk-reject-reason');
        var reason = textarea ? textarea.value.trim() : '';
        executeBulk('reject', reason || null);
      },
    });
  }

  async function executeBulk(action, notes) {
    var ids = Array.from(selected);
    var user = Lab.auth.currentUser;
    var reviewer = user ? user.name : 'scientist';
    var succeeded = 0;
    var failed = 0;

    for (var i = 0; i < ids.length; i++) {
      var body = { action: action, reviewed_by: reviewer };
      if (notes) body.review_notes = notes;
      try {
        await Lab.api.documents.review(ids[i], body);
        succeeded++;
      } catch (_) {
        failed++;
      }
    }

    selected.clear();

    if (failed === 0) {
      C.toast(succeeded + ' documents ' + (action === 'approve' ? 'approved' : 'rejected'), 'success');
    } else {
      C.toast(succeeded + ' ' + (action === 'approve' ? 'approved' : 'rejected') + ', ' + failed + ' failed', 'error');
    }

    loadQueue();
    Lab.dashboard.init();
  }

  return {
    init: init,
    loadQueue: loadQueue,
    bulkApprove: bulkApprove,
    bulkReject: bulkReject,
  };
})();
