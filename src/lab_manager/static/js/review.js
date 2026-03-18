/**
 * Review Queue view — needs_review documents with bulk approve/reject.
 */
window.Lab = window.Lab || {};

window.Lab.review = (function () {
  'use strict';
  var C = Lab.components;

  var selected = new Set();
  var docs = [];
  var currentPage = 1;
  var lastData = null;
  var PAGE_SIZE = 50;

  async function init() {
    selected.clear();
    currentPage = 1;
    await loadQueue();
  }

  async function loadQueue() {
    selected.clear();
    var data;
    try {
      data = await Lab.api.documents.list({ status: 'needs_review', page: currentPage, page_size: PAGE_SIZE });
    } catch (_) {
      return;
    }
    lastData = data;
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
      columns: C.docColumns(),
      rows: docs,
      onRowClick: function (id) { Lab.documents.openDetail(id); },
      emptyMsg: 'No documents need review',
      pagination: lastData ? {
        page: lastData.page || 1,
        pages: lastData.pages || 1,
        onChange: function (p) { currentPage = p; loadQueue(); },
      } : null,
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
    var reviewer = Lab.auth.userName();
    var BATCH_SIZE = 5;
    var succeeded = 0;
    var failed = 0;

    for (var i = 0; i < ids.length; i += BATCH_SIZE) {
      var batch = ids.slice(i, i + BATCH_SIZE);
      var results = await Promise.allSettled(batch.map(function (id) {
        var body = { action: action, reviewed_by: reviewer };
        if (notes) body.review_notes = notes;
        return Lab.api.documents.review(id, body);
      }));
      results.forEach(function (r) {
        if (r.status === 'fulfilled') succeeded++;
        else failed++;
      });
    }

    selected.clear();

    if (failed === 0) {
      C.toast(succeeded + ' documents ' + (action === 'approve' ? 'approved' : 'rejected'), 'success');
    } else {
      C.toast(succeeded + ' ' + (action === 'approve' ? 'approved' : 'rejected') + ', ' + failed + ' failed', 'error');
    }

    loadQueue();
  }

  return {
    init: init,
    loadQueue: loadQueue,
    bulkApprove: bulkApprove,
    bulkReject: bulkReject,
  };
})();
