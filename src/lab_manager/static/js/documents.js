/**
 * Documents view — list, filter, search, detail panel with inline editing.
 */
window.Lab = window.Lab || {};

window.Lab.documents = (function () {
  'use strict';
  var C = Lab.components;

  var currentPage = 1;
  var currentFilter = '';
  var currentSearch = '';
  var searchTimer = null;
  var PAGE_SIZE = 30;
  var editingDoc = null; // document being edited (with local changes)
  var originalDoc = null; // snapshot before edits

  async function init() {
    clearTimeout(searchTimer);
    currentPage = 1;
    currentFilter = '';
    currentSearch = '';
    editingDoc = null;
    originalDoc = null;
    setupEvents();
    await loadDocuments();
  }

  function setupEvents() {
    var searchInput = document.getElementById('doc-search-input');
    if (searchInput) {
      searchInput.oninput = function () {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(function () {
          currentSearch = searchInput.value;
          currentPage = 1;
          loadDocuments();
        }, 300);
      };
    }
  }

  async function loadDocuments() {
    var params = { page: currentPage, page_size: PAGE_SIZE };
    if (currentFilter) params.status = currentFilter;
    if (currentSearch) params.search = currentSearch;

    var data;
    try {
      data = await Lab.api.documents.list(params);
    } catch (_) {
      return;
    }

    var docs = data.items || [];
    C.renderTable('doc-table', {
      columns: C.docColumns(),
      rows: docs,
      onRowClick: function (id) { openDetail(id); },
      emptyMsg: 'No documents found',
      pagination: {
        page: data.page || 1,
        pages: data.pages || 1,
        onChange: function (p) { currentPage = p; loadDocuments(); },
      },
    });
  }

  function setFilter(status) {
    currentFilter = status;
    currentPage = 1;
    loadDocuments();

    // Update filter button states
    document.querySelectorAll('#view-documents .filter-btn').forEach(function (btn) {
      btn.classList.toggle('active', btn.dataset.status === status);
    });
  }

  async function openDetail(id) {
    var doc;
    try {
      doc = await Lab.api.documents.get(id);
    } catch (_) {
      return;
    }

    originalDoc = JSON.parse(JSON.stringify(doc));
    editingDoc = null;
    renderDetail(doc, false);
  }

  function renderDetail(doc, editing) {
    var data = editing && editingDoc ? editingDoc.extracted_data : (doc.extracted_data || {});
    var items = data.items || [];

    // Scan image
    var bodyHtml = '<img class="scan-image" src="/scans/' + encodeURIComponent(doc.file_name || '') +
      '" onerror="this.style.display=\'none\'" alt="scan">';

    // Status + confidence
    bodyHtml += '<div style="display:flex; gap:8px; margin-bottom:16px; align-items:center;">' +
      C.badge(doc.status) +
      '<span style="color:var(--text-muted); font-size:13px;">Confidence: <strong>' +
      (doc.extraction_confidence != null ? (doc.extraction_confidence * 100).toFixed(0) + '%' : 'N/A') +
      '</strong></span></div>';

    // Document info
    bodyHtml += '<div class="field-group"><h3>Document Info';
    if (doc.status === 'needs_review' && !editing) {
      bodyHtml += '<button class="btn btn-sm btn-secondary" onclick="Lab.documents.startEdit()">Edit</button>';
    }
    if (editing) {
      bodyHtml += '<button class="btn btn-sm btn-secondary" onclick="Lab.documents.cancelEdit()">Cancel</button>';
    }
    bodyHtml += '</h3>';

    if (editing) {
      bodyHtml += C.editableFieldRow('Vendor', 'vendor_name', data.vendor_name);
      bodyHtml += C.editableFieldRow('Type', 'document_type', data.document_type);
      bodyHtml += C.editableFieldRow('PO Number', 'po_number', data.po_number);
      bodyHtml += C.editableFieldRow('Order Number', 'order_number', data.order_number);
      bodyHtml += C.editableFieldRow('Invoice #', 'invoice_number', data.invoice_number);
      bodyHtml += C.editableFieldRow('Order Date', 'order_date', data.order_date, 'date');
      bodyHtml += C.editableFieldRow('Ship Date', 'ship_date', data.ship_date, 'date');
    } else {
      bodyHtml += C.fieldRow('Vendor', C.esc(data.vendor_name));
      bodyHtml += C.fieldRow('Type', C.esc(C.humanize(data.document_type)));
      bodyHtml += C.fieldRow('PO Number', C.esc(data.po_number));
      bodyHtml += C.fieldRow('Order Number', C.esc(data.order_number));
      bodyHtml += C.fieldRow('Invoice #', C.esc(data.invoice_number));
      bodyHtml += C.fieldRow('Order Date', C.esc(data.order_date));
      bodyHtml += C.fieldRow('Ship Date', C.esc(data.ship_date));
    }
    bodyHtml += '</div>';

    // Line items
    if (items.length > 0 || editing) {
      bodyHtml += '<div class="field-group"><h3>Line Items (' + items.length + ')';
      if (editing) {
        bodyHtml += '<button class="btn btn-sm btn-secondary" onclick="Lab.documents.addItem()">+ Add Row</button>';
      }
      bodyHtml += '</h3>';
      bodyHtml += '<table class="items-table"><thead><tr><th>Catalog #</th><th>Description</th><th>Qty</th><th>Unit</th><th>Lot #</th>';
      if (editing) bodyHtml += '<th></th>';
      bodyHtml += '</tr></thead><tbody>';

      items.forEach(function (it, idx) {
        if (editing) {
          bodyHtml += '<tr>' +
            '<td><input name="item_catalog_' + idx + '" value="' + C.esc(it.catalog_number || '') + '"></td>' +
            '<td><input name="item_desc_' + idx + '" value="' + C.esc(it.description || '') + '"></td>' +
            '<td><input name="item_qty_' + idx + '" value="' + C.esc(String(it.quantity || '')) + '" type="number" style="width:60px"></td>' +
            '<td><input name="item_unit_' + idx + '" value="' + C.esc(it.unit || '') + '" style="width:60px"></td>' +
            '<td><input name="item_lot_' + idx + '" value="' + C.esc(it.lot_number || '') + '"></td>' +
            '<td><button class="btn-row-delete" onclick="Lab.documents.removeItem(' + idx + ')">&times;</button></td>' +
            '</tr>';
        } else {
          bodyHtml += '<tr>' +
            '<td><strong>' + C.esc(it.catalog_number || '') + '</strong></td>' +
            '<td>' + C.esc(it.description || '') + '</td>' +
            '<td>' + C.esc(String(it.quantity || '')) + '</td>' +
            '<td>' + C.esc(it.unit || '') + '</td>' +
            '<td>' + C.esc(it.lot_number || '') + '</td>' +
            '</tr>';
        }
      });
      bodyHtml += '</tbody></table></div>';
    }

    // OCR text
    bodyHtml += '<div class="field-group"><h3>OCR Text</h3>' +
      '<div class="tab-bar">' +
      '<button class="active" onclick="Lab.documents.toggleOcr(this,\'extracted\')">Extracted Data</button>' +
      '<button onclick="Lab.documents.toggleOcr(this,\'raw\')">Raw OCR Text</button>' +
      '</div>' +
      '<div id="ocr-extracted"><pre style="font-size:12px; max-height:200px; overflow:auto; background:#f8fafc; padding:8px; border-radius:6px;">' +
      C.esc(JSON.stringify(data, null, 2)) + '</pre></div>' +
      '<div id="ocr-raw" class="hidden"><div class="ocr-text">' + C.esc(doc.ocr_text || '') + '</div></div></div>';

    // Actions
    var actionsHtml = '';
    if (doc.status === 'needs_review') {
      if (editing) {
        actionsHtml = '<button class="btn btn-approve" onclick="Lab.documents.saveAndApprove(' + doc.id + ')">Save &amp; Approve</button>' +
          '<button class="btn btn-reject" onclick="Lab.documents.openRejectModal(' + doc.id + ')">Reject</button>';
      } else {
        actionsHtml = '<button class="btn btn-approve" onclick="Lab.documents.approve(' + doc.id + ')">Approve</button>' +
          '<button class="btn btn-reject" onclick="Lab.documents.openRejectModal(' + doc.id + ')">Reject</button>';
      }
    } else {
      actionsHtml = '<span style="color:var(--text-muted); font-size:13px;">Status: ' + C.esc(doc.status || '') +
        (doc.reviewed_by ? ' by ' + C.esc(doc.reviewed_by) : '') + '</span>';
    }

    C.openPanel(doc.file_name || 'Document', bodyHtml, actionsHtml);
  }

  function startEdit() {
    if (!originalDoc) return;
    editingDoc = JSON.parse(JSON.stringify(originalDoc));
    renderDetail(originalDoc, true);
  }

  function cancelEdit() {
    editingDoc = null;
    renderDetail(originalDoc, false);
  }

  function collectEditedData() {
    if (!editingDoc) return null;
    var body = document.getElementById('detail-body');
    var data = editingDoc.extracted_data || {};

    // Collect field values
    var fields = ['vendor_name', 'document_type', 'po_number', 'order_number', 'invoice_number', 'order_date', 'ship_date'];
    fields.forEach(function (f) {
      var input = body.querySelector('input[name="' + f + '"]');
      if (input) data[f] = input.value;
    });

    // Collect item values
    var items = data.items || [];
    items.forEach(function (it, idx) {
      var cat = body.querySelector('input[name="item_catalog_' + idx + '"]');
      var desc = body.querySelector('input[name="item_desc_' + idx + '"]');
      var qty = body.querySelector('input[name="item_qty_' + idx + '"]');
      var unit = body.querySelector('input[name="item_unit_' + idx + '"]');
      var lot = body.querySelector('input[name="item_lot_' + idx + '"]');
      if (cat) it.catalog_number = cat.value;
      if (desc) it.description = desc.value;
      if (qty) it.quantity = parseFloat(qty.value) || 0;
      if (unit) it.unit = unit.value;
      if (lot) it.lot_number = lot.value;
    });

    data.items = items;
    return data;
  }

  function addItem() {
    if (!editingDoc) return;
    collectEditedData();
    if (!editingDoc.extracted_data) editingDoc.extracted_data = {};
    if (!editingDoc.extracted_data.items) editingDoc.extracted_data.items = [];
    editingDoc.extracted_data.items.push({
      catalog_number: '', description: '', quantity: 1, unit: '', lot_number: '',
    });
    renderDetail(originalDoc, true);
  }

  function removeItem(idx) {
    if (!editingDoc || !editingDoc.extracted_data || !editingDoc.extracted_data.items) return;
    // Collect current values first
    collectEditedData();
    editingDoc.extracted_data.items.splice(idx, 1);
    renderDetail(originalDoc, true);
  }

  async function saveAndApprove(id) {
    var data = collectEditedData();
    if (!data) return;

    try {
      // 1. Save edits
      await Lab.api.documents.update(id, {
        extracted_data: data,
        vendor_name: data.vendor_name,
        document_type: data.document_type,
      });

      // 2. Approve
      await Lab.api.documents.review(id, {
        action: 'approve',
        reviewed_by: Lab.auth.userName(),
      });

      C.toast('Document approved, order created!', 'success');
      C.closePanel();
      editingDoc = null;
      originalDoc = null;
      loadDocuments();
    } catch (err) {
      // If update succeeded but review failed, edits are saved server-side.
      // Reload to show current state so user can retry approve.
      var doc = await Lab.api.documents.get(id).catch(function () { return null; });
      if (doc) {
        originalDoc = JSON.parse(JSON.stringify(doc));
        editingDoc = null;
        renderDetail(doc, false);
        C.toast('Edits saved but approval failed — please try approving again', 'error');
      }
    }
  }

  async function approve(id) {
    try {
      await Lab.api.documents.review(id, {
        action: 'approve',
        reviewed_by: Lab.auth.userName(),
      });
      C.toast('Document approved, order created!', 'success');
      C.closePanel();
      loadDocuments();
    } catch (_) {}
  }

  function openRejectModal(id) {
    C.showModal({
      title: 'Reject Document',
      body: '<p style="color:var(--text-muted); font-size:14px; margin-bottom:12px;">Optionally provide a reason for rejecting this document.</p>' +
        '<textarea id="reject-reason" placeholder="Reason for rejection (optional)..."></textarea>',
      confirmLabel: 'Reject',
      confirmClass: 'btn-reject',
      onConfirm: function () {
        var reason = document.getElementById('reject-reason');
        var notes = reason ? reason.value.trim() : '';
        rejectDoc(id, notes || null);
      },
    });
  }

  async function rejectDoc(id, notes) {
    var body = { action: 'reject', reviewed_by: Lab.auth.userName() };
    if (notes) body.review_notes = notes;
    try {
      await Lab.api.documents.review(id, body);
      C.toast('Document rejected', 'success');
      C.closePanel();
      loadDocuments();
    } catch (_) {}
  }

  function toggleOcr(btn, mode) {
    btn.parentElement.querySelectorAll('button').forEach(function (b) { b.classList.remove('active'); });
    btn.classList.add('active');
    document.getElementById('ocr-extracted').classList.toggle('hidden', mode !== 'extracted');
    document.getElementById('ocr-raw').classList.toggle('hidden', mode !== 'raw');
  }

  return {
    init: init,
    loadDocuments: loadDocuments,
    setFilter: setFilter,
    openDetail: openDetail,
    startEdit: startEdit,
    cancelEdit: cancelEdit,
    addItem: addItem,
    removeItem: removeItem,
    saveAndApprove: saveAndApprove,
    approve: approve,
    openRejectModal: openRejectModal,
    toggleOcr: toggleOcr,
  };
})();
