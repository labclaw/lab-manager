/**
 * Search view — unified search bar, grouped results, autocomplete.
 */
window.Lab = window.Lab || {};

window.Lab.search = (function () {
  'use strict';
  var C = Lab.components;
  var suggestTimer = null;

  function init(query) {
    if (query) {
      var input = document.getElementById('search-main-input');
      if (input) input.value = query;
      doSearch(query);
    }
    setupNavSearch();
  }

  function setupNavSearch() {
    var navInput = document.getElementById('nav-search-input');
    if (!navInput) return;

    navInput.onkeydown = function (e) {
      if (e.key === 'Enter') {
        var q = navInput.value.trim();
        if (q) {
          window.location.hash = '#/search?q=' + encodeURIComponent(q);
        }
      }
    };

    navInput.oninput = function () {
      clearTimeout(suggestTimer);
      var q = navInput.value.trim();
      if (q.length < 2) {
        hideAutocomplete();
        return;
      }
      suggestTimer = setTimeout(function () { showSuggestions(q); }, 200);
    };

    // Close autocomplete on click outside
    document.addEventListener('click', function (e) {
      if (!e.target.closest('.nav-search')) hideAutocomplete();
    });
  }

  async function showSuggestions(q) {
    try {
      var data = await Lab.api.search.suggest(q, 5);
      var items = data.suggestions || data.hits || data || [];
      if (!Array.isArray(items) || items.length === 0) {
        hideAutocomplete();
        return;
      }

      var dropdown = document.getElementById('autocomplete-dropdown');
      if (!dropdown) return;
      dropdown.innerHTML = items.map(function (item) {
        var label = item.name || item.title || item.file_name || JSON.stringify(item);
        var type = item._index || item.type || '';
        return '<div class="autocomplete-item" data-value="' + C.esc(label) + '">' +
          C.esc(label) +
          (type ? ' <span style="color:var(--text-muted); font-size:11px;">' + C.esc(type) + '</span>' : '') +
          '</div>';
      }).join('');
      dropdown.classList.remove('hidden');

      dropdown.onclick = function (e) {
        var item = e.target.closest('.autocomplete-item');
        if (item) {
          var val = item.dataset.value;
          document.getElementById('nav-search-input').value = val;
          hideAutocomplete();
          window.location.hash = '#/search?q=' + encodeURIComponent(val);
        }
      };
    } catch (_) {
      hideAutocomplete();
    }
  }

  function hideAutocomplete() {
    var dropdown = document.getElementById('autocomplete-dropdown');
    if (dropdown) dropdown.classList.add('hidden');
  }

  async function doSearch(query) {
    var container = document.getElementById('search-results');
    if (!container) return;

    if (!query) {
      container.innerHTML = '<div style="padding:40px; text-align:center; color:var(--text-muted);">Enter a search term above</div>';
      return;
    }

    container.innerHTML = '<div class="loading">Searching...</div>';

    try {
      var data = await Lab.api.search.query(query);
      renderResults(container, data, query);
    } catch (_) {
      container.innerHTML = '<div style="padding:40px; text-align:center; color:var(--text-muted);">Search failed</div>';
    }
  }

  function renderResults(container, data, query) {
    // data may be {results: [{index, hits}]} or similar
    var results = data.results || data.hits || [];
    if (Array.isArray(data) && data.length === 0) results = [];

    // Normalize into groups
    var groups = {};
    if (Array.isArray(results)) {
      results.forEach(function (r) {
        if (r.index || r._index) {
          var idx = r.index || r._index;
          if (!groups[idx]) groups[idx] = [];
          if (r.hits) {
            groups[idx] = groups[idx].concat(r.hits);
          } else {
            groups[idx].push(r);
          }
        }
      });
    }

    // Also handle flat list
    if (Object.keys(groups).length === 0 && results.length > 0) {
      groups['Results'] = results;
    }

    var totalHits = Object.values(groups).reduce(function (sum, arr) { return sum + arr.length; }, 0);

    if (totalHits === 0) {
      container.innerHTML = '<div style="padding:40px; text-align:center;">' +
        '<div style="color:var(--text-muted); font-size:16px; margin-bottom:8px;">No results found</div>' +
        '<div style="color:var(--text-muted); font-size:14px;">Try a different search term or check your spelling</div>' +
        '</div>';
      return;
    }

    var html = '<div class="search-results">';
    Object.keys(groups).forEach(function (groupName) {
      var items = groups[groupName];
      html += '<div class="search-group"><h3>' + C.esc(groupName) + ' (' + items.length + ')</h3>';
      items.forEach(function (item) {
        var title = item.name || item.title || item.file_name || item.po_number || '';
        var sub = item.vendor_name || item.catalog_number || item.description || '';
        html += '<div class="search-result-item">' +
          '<div style="font-weight:500;">' + C.esc(title) + '</div>' +
          (sub ? '<div style="font-size:13px; color:var(--text-muted);">' + C.esc(sub) + '</div>' : '') +
          '</div>';
      });
      html += '</div>';
    });
    html += '</div>';

    container.innerHTML = html;
  }

  return {
    init: init,
    doSearch: doSearch,
    setupNavSearch: setupNavSearch,
  };
})();
