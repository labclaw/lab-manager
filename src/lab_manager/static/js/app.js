/**
 * App init — hash routing, auth state, view switching.
 * Loaded last so all Lab.* modules are available.
 */
window.Lab = window.Lab || {};

window.Lab.auth = (function () {
  'use strict';

  var currentUser = null;

  async function init() {
    try {
      var data = await Lab.api.auth.me();
      if (data && data.user) {
        currentUser = data.user;
        showApp();
        return;
      }
    } catch (_) {}
    showLogin();
  }

  function showApp() {
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('main-app').classList.remove('hidden');
    document.getElementById('user-name').textContent = currentUser ? currentUser.name : '';
    Lab.search.setupNavSearch();
    route();
  }

  function showLogin() {
    currentUser = null;
    document.getElementById('main-app').classList.add('hidden');
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('login-password').value = '';
  }

  async function handleLogin(e) {
    e.preventDefault();
    var btn = document.getElementById('login-btn');
    var errDiv = document.getElementById('login-error');
    btn.disabled = true;
    btn.textContent = 'Signing in...';
    errDiv.style.display = 'none';

    try {
      var r = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: document.getElementById('login-email').value,
          password: document.getElementById('login-password').value,
        }),
      });
      if (r.ok) {
        var data = await r.json();
        currentUser = data.user;
        showApp();
      } else {
        var err = await r.json().catch(function () { return { detail: 'Login failed' }; });
        errDiv.textContent = err.detail || 'Invalid email or password';
        errDiv.style.display = 'block';
      }
    } catch (_) {
      errDiv.textContent = 'Network error. Please try again.';
      errDiv.style.display = 'block';
    }

    btn.disabled = false;
    btn.textContent = 'Sign In';
  }

  async function handleLogout() {
    await Lab.api.auth.logout();
    showLogin();
  }

  function userName() {
    return currentUser ? currentUser.name : 'scientist';
  }

  return {
    init: init,
    showApp: showApp,
    showLogin: showLogin,
    handleLogin: handleLogin,
    handleLogout: handleLogout,
    userName: userName,
    get currentUser() { return currentUser; },
  };
})();

// ---- Hash router ----

var VIEWS = ['dashboard', 'documents', 'review', 'inventory', 'orders', 'search'];

function route() {
  var hash = window.location.hash.slice(2) || 'dashboard'; // remove #/
  var qIdx = hash.indexOf('?');
  var params = '';
  if (qIdx >= 0) {
    params = hash.slice(qIdx + 1);
    hash = hash.slice(0, qIdx);
  }

  var parts = hash.split('/');
  var view = parts[0];
  var id = parts[1] ? parseInt(parts[1], 10) : null;
  if (isNaN(id)) id = null;

  // Unknown route: redirect to dashboard
  if (VIEWS.indexOf(view) === -1) {
    window.location.hash = '#/dashboard';
    return;
  }

  // Toggle view visibility
  VIEWS.forEach(function (v) {
    var el = document.getElementById('view-' + v);
    if (el) el.classList.toggle('hidden', v !== view);
  });

  // Update nav buttons
  document.querySelectorAll('.navbar .nav-links button').forEach(function (btn) {
    var btnView = btn.dataset.view;
    btn.classList.toggle('active', btnView === view);
  });

  // Initialize the view
  switch (view) {
    case 'dashboard':
      Lab.dashboard.init();
      break;
    case 'documents':
      Lab.documents.init();
      break;
    case 'review':
      Lab.review.init();
      break;
    case 'inventory':
      Lab.inventory.init();
      break;
    case 'orders':
      Lab.orders.init();
      if (id) Lab.orders.showOrderById(id);
      break;
    case 'search':
      var q = new URLSearchParams(params).get('q') || '';
      Lab.search.init(q);
      break;
  }
}

window.addEventListener('hashchange', route);

// Keyboard shortcuts
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') Lab.components.closePanel();
});

// Boot
Lab.auth.init();
