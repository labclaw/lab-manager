/**
 * Shared UI components — table, pagination, modal, toast, forms, badges.
 */
window.Lab = window.Lab || {};

window.Lab.components = (function () {
  'use strict';

  // ---- HTML escaping ----

  function esc(s) {
    if (s == null || s === '') return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // ---- Humanize snake_case ----

  function humanize(s) {
    if (!s) return '';
    return String(s).replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  // ---- Badge ----

  function badge(status) {
    if (!status) return '';
    var cls = 'badge badge-' + esc(status.replace(/\s+/g, '_'));
    var label = esc(status.replace(/_/g, ' '));
    return '<span class="' + cls + '">' + label + '</span>';
  }

  // ---- Toast ----

  function toast(msg, type) {
    var t = document.createElement('div');
    t.className = 'toast toast-' + (type || 'success');
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 5000);
  }

  // ---- Generic table ----
  // renderTable(containerId, { columns, rows, onRowClick, emptyMsg, pagination, checkbox })
  //   columns: [{key, label, width, render(value, row)}]
  //   rows: data array
  //   onRowClick: function(row)
  //   emptyMsg: string
  //   pagination: {page, pages, onChange(page)}
  //   checkbox: {selected: Set, onToggle(id), onToggleAll()}

  function renderTable(containerId, opts) {
    var el = document.getElementById(containerId);
    if (!el) return;
    if (!el.classList.contains('data-list')) el.classList.add('data-list');

    var cols = opts.columns || [];
    var rows = opts.rows || [];
    var gridCols = cols.map(function (c) { return c.width || '1fr'; }).join(' ');

    // Header
    var headerHtml = '<div class="table-header" style="grid-template-columns:' +
      (opts.checkbox ? '40px ' : '') + gridCols + ';">';
    if (opts.checkbox) {
      var allChecked = rows.length > 0 && rows.every(function (r) { return opts.checkbox.selected.has(r.id); });
      headerHtml += '<div><input type="checkbox" class="row-checkbox" data-action="toggle-all"' +
        (allChecked ? ' checked' : '') + '></div>';
    }
    cols.forEach(function (c) {
      headerHtml += '<div>' + esc(c.label) + '</div>';
    });
    headerHtml += '</div>';

    // Rows
    var rowsHtml = '';
    if (rows.length === 0) {
      rowsHtml = '<div style="padding:40px; text-align:center; color:var(--text-muted);">' +
        esc(opts.emptyMsg || 'No items found') + '</div>';
    } else {
      rows.forEach(function (row) {
        var isSelected = opts.checkbox && opts.checkbox.selected.has(row.id);
        var isDisabled = row._disabled;
        var cls = 'data-row' + (isSelected ? ' selected' : '') + (isDisabled ? ' disabled' : '');
        rowsHtml += '<div class="' + cls + '" style="grid-template-columns:' +
          (opts.checkbox ? '40px ' : '') + gridCols + ';" data-id="' + row.id + '">';

        if (opts.checkbox) {
          rowsHtml += '<div><input type="checkbox" class="row-checkbox" data-action="toggle-row" data-id="' +
            row.id + '"' + (isSelected ? ' checked' : '') + '></div>';
        }

        cols.forEach(function (c) {
          var val = row[c.key];
          var rendered = c.render ? c.render(val, row) : esc(val != null ? val : '');
          rowsHtml += '<div>' + rendered + '</div>';
        });
        rowsHtml += '</div>';
      });
    }

    // Pagination
    var pagHtml = '';
    if (opts.pagination && opts.pagination.pages > 1) {
      var p = opts.pagination;
      pagHtml = '<div class="pagination">' +
        '<button data-action="prev-page"' + (p.page <= 1 ? ' disabled' : '') + '>&laquo; Prev</button>' +
        '<span>Page ' + p.page + ' of ' + p.pages + '</span>' +
        '<button data-action="next-page"' + (p.page >= p.pages ? ' disabled' : '') + '>Next &raquo;</button>' +
        '</div>';
    }

    el.innerHTML = headerHtml + '<div class="table-rows">' + rowsHtml + '</div>' + pagHtml;

    // Event delegation
    el.onclick = function (e) {
      var target = e.target;

      // Checkbox: toggle all
      if (target.dataset.action === 'toggle-all' && opts.checkbox) {
        e.stopPropagation();
        opts.checkbox.onToggleAll();
        return;
      }

      // Checkbox: toggle row
      if (target.dataset.action === 'toggle-row' && opts.checkbox) {
        e.stopPropagation();
        opts.checkbox.onToggle(parseInt(target.dataset.id));
        return;
      }

      // Pagination
      if (target.dataset.action === 'prev-page' && opts.pagination) {
        opts.pagination.onChange(opts.pagination.page - 1);
        return;
      }
      if (target.dataset.action === 'next-page' && opts.pagination) {
        opts.pagination.onChange(opts.pagination.page + 1);
        return;
      }

      // Row click
      if (opts.onRowClick) {
        var row = target.closest('.data-row');
        if (row && row.dataset.id) {
          opts.onRowClick(parseInt(row.dataset.id));
        }
      }
    };
  }

  // ---- Modal ----
  // showModal({title, body, confirmLabel, confirmClass, onConfirm, onCancel})

  function showModal(opts) {
    var modal = document.getElementById('generic-modal');
    if (!modal) return;
    var card = modal.querySelector('.modal-card');
    card.innerHTML =
      '<h3>' + esc(opts.title) + '</h3>' +
      '<div class="modal-body">' + (opts.body || '') + '</div>' +
      '<div class="modal-actions">' +
      '<button class="btn btn-secondary" data-action="modal-cancel">Cancel</button>' +
      '<button class="btn ' + (opts.confirmClass || 'btn-primary') + '" data-action="modal-confirm">' +
      esc(opts.confirmLabel || 'Confirm') + '</button>' +
      '</div>';

    modal.classList.add('show');

    var cleanup = function () {
      modal.classList.remove('show');
      modal.onclick = null;
    };

    modal.onclick = function (e) {
      var btn = e.target.closest('[data-action]');
      var action = btn ? btn.dataset.action : null;
      if (action === 'modal-confirm') {
        cleanup();
        if (opts.onConfirm) opts.onConfirm(card);
      } else if (action === 'modal-cancel' || e.target === modal) {
        cleanup();
        if (opts.onCancel) opts.onCancel();
      }
    };
  }

  function closeModal() {
    var modal = document.getElementById('generic-modal');
    if (modal) {
      modal.classList.remove('show');
      modal.onclick = null;
    }
  }

  // ---- Detail panel ----

  function openPanel(title, bodyHtml, actionsHtml) {
    document.getElementById('detail-title').textContent = title;
    document.getElementById('detail-body').innerHTML = bodyHtml;
    document.getElementById('detail-actions').innerHTML = actionsHtml || '';
    document.getElementById('detail-panel').classList.add('open');
    document.getElementById('overlay').classList.add('show');
  }

  function closePanel() {
    document.getElementById('detail-panel').classList.remove('open');
    document.getElementById('overlay').classList.remove('show');
  }

  // ---- Field row (read-only) ----

  function fieldRow(label, value) {
    return '<div class="field-row"><div class="field-label">' + esc(label) +
      '</div><div class="field-value">' + (value || '&mdash;') + '</div></div>';
  }

  // ---- Editable field row ----

  function editableFieldRow(label, name, value, type) {
    type = type || 'text';
    return '<div class="field-row"><div class="field-label">' + esc(label) +
      '</div><div class="field-value"><input type="' + type + '" name="' + esc(name) +
      '" value="' + esc(value || '') + '"></div></div>';
  }

  // ---- Shared column definitions ----

  function docColumns() {
    return [
      { key: 'id', label: 'ID', width: '60px', render: function (v) { return '<span class="id">#' + v + '</span>'; } },
      { key: 'file_name', label: 'File / Vendor', width: '1fr', render: function (v, row) {
        return '<div><div class="name">' + esc(v || '') + '</div><div class="sub-text">' + esc(row.vendor_name || '') + '</div></div>';
      }},
      { key: 'document_type', label: 'Type', width: '140px', render: function (v) { return esc(humanize(v || '')); } },
      { key: 'status', label: 'Status', width: '120px', render: function (v) { return badge(v); } },
      { key: 'extraction_confidence', label: 'Conf.', width: '80px', render: function (v) {
        return v != null ? (v * 100).toFixed(0) + '%' : '&mdash;';
      }},
    ];
  }

  // ---- Loading indicator ----

  function loading(containerId) {
    var el = document.getElementById(containerId);
    if (el) el.innerHTML = '<div class="loading">Loading...</div>';
  }

  return {
    esc: esc,
    humanize: humanize,
    badge: badge,
    toast: toast,
    renderTable: renderTable,
    showModal: showModal,
    closeModal: closeModal,
    openPanel: openPanel,
    closePanel: closePanel,
    fieldRow: fieldRow,
    editableFieldRow: editableFieldRow,
    docColumns: docColumns,
    loading: loading,
  };
})();
