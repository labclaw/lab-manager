/**
 * Lab Manager API client — centralized fetch with auth handling and error toasts.
 *
 * Usage: Lab.api.fetch('/api/orders/'), Lab.api.orders.list({page: 1}), etc.
 */
window.Lab = window.Lab || {};

window.Lab.api = (function () {
  'use strict';

  // ---- Core fetch wrapper ----

  async function apiFetch(url, opts) {
    opts = opts || {};
    opts.headers = opts.headers || {};
    if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }

    var r;
    try {
      r = await fetch(url, opts);
    } catch (e) {
      Lab.components.toast('Network error. Check your connection.', 'error');
      throw e;
    }

    if (r.status === 401) {
      Lab.auth.showLogin();
      Lab.components.toast('Session expired. Please sign in again.', 'error');
      throw new Error('Unauthorized');
    }

    if (!r.ok) {
      var err;
      try { err = await r.json(); } catch (_) { err = {}; }
      var msg = err.detail || ('Error ' + r.status);
      Lab.components.toast(msg, 'error');
      throw new Error(msg);
    }

    return r;
  }

  // ---- Convenience helpers ----

  function buildParams(obj) {
    var p = new URLSearchParams();
    Object.keys(obj).forEach(function (k) {
      if (obj[k] != null && obj[k] !== '') p.set(k, obj[k]);
    });
    return p.toString();
  }

  // ---- Resource helpers ----

  var documents = {
    list: function (params) {
      return apiFetch('/api/documents/?' + buildParams(params)).then(function (r) { return r.json(); });
    },
    get: function (id) {
      return apiFetch('/api/documents/' + id).then(function (r) { return r.json(); });
    },
    update: function (id, data) {
      return apiFetch('/api/documents/' + id, { method: 'PATCH', body: data });
    },
    review: function (id, body) {
      return apiFetch('/api/documents/' + id + '/review', { method: 'POST', body: body });
    },
    stats: function () {
      return apiFetch('/api/documents/stats').then(function (r) { return r.json(); });
    },
  };

  var orders = {
    list: function (params) {
      return apiFetch('/api/orders/?' + buildParams(params)).then(function (r) { return r.json(); });
    },
    get: function (id) {
      return apiFetch('/api/orders/' + id).then(function (r) { return r.json(); });
    },
    items: function (orderId) {
      return apiFetch('/api/orders/' + orderId + '/items').then(function (r) { return r.json(); });
    },
    receive: function (id, body) {
      return apiFetch('/api/orders/' + id + '/receive', { method: 'POST', body: body });
    },
  };

  var inventory = {
    list: function (params) {
      return apiFetch('/api/inventory/?' + buildParams(params)).then(function (r) { return r.json(); });
    },
    get: function (id) {
      return apiFetch('/api/inventory/' + id).then(function (r) { return r.json(); });
    },
    history: function (id) {
      return apiFetch('/api/inventory/' + id + '/history').then(function (r) { return r.json(); });
    },
    consume: function (id, body) {
      return apiFetch('/api/inventory/' + id + '/consume', { method: 'POST', body: body });
    },
    transfer: function (id, body) {
      return apiFetch('/api/inventory/' + id + '/transfer', { method: 'POST', body: body });
    },
    adjust: function (id, body) {
      return apiFetch('/api/inventory/' + id + '/adjust', { method: 'POST', body: body });
    },
    dispose: function (id, body) {
      return apiFetch('/api/inventory/' + id + '/dispose', { method: 'POST', body: body });
    },
    open: function (id, body) {
      return apiFetch('/api/inventory/' + id + '/open', { method: 'POST', body: body });
    },
    lowStock: function () {
      return apiFetch('/api/inventory/low-stock').then(function (r) { return r.json(); });
    },
    expiring: function (days) {
      return apiFetch('/api/inventory/expiring?days=' + (days || 30)).then(function (r) { return r.json(); });
    },
  };

  var search = {
    query: function (q, index, limit) {
      var params = { q: q };
      if (index) params.index = index;
      if (limit) params.limit = limit;
      return apiFetch('/api/search/?' + buildParams(params)).then(function (r) { return r.json(); });
    },
    suggest: function (q, limit) {
      return apiFetch('/api/search/suggest?' + buildParams({ q: q, limit: limit || 5 })).then(function (r) { return r.json(); });
    },
  };

  var analytics = {
    dashboard: function () {
      return apiFetch('/api/analytics/dashboard').then(function (r) { return r.json(); });
    },
  };

  var alerts = {
    summary: function () {
      return apiFetch('/api/alerts/summary').then(function (r) { return r.json(); });
    },
  };

  var vendors = {
    list: function (params) {
      return apiFetch('/api/vendors/?' + buildParams(params || {})).then(function (r) { return r.json(); });
    },
  };

  var auth = {
    login: function (email, password) {
      return apiFetch('/api/auth/login', { method: 'POST', body: { email: email, password: password } });
    },
    me: function () {
      return fetch('/api/auth/me').then(function (r) { return r.ok ? r.json() : null; });
    },
    logout: function () {
      return fetch('/api/auth/logout', { method: 'POST' });
    },
  };

  return {
    fetch: apiFetch,
    buildParams: buildParams,
    documents: documents,
    orders: orders,
    inventory: inventory,
    search: search,
    analytics: analytics,
    alerts: alerts,
    vendors: vendors,
    auth: auth,
  };
})();
