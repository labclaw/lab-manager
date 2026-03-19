// app.js — Router (hash-based), auth flow, sidebar active state, init
"use strict";

const VIEWS = ["dashboard", "documents", "review", "inventory", "orders", "upload"];

// --- Auth ---
async function handleLogin(e) {
  e.preventDefault();
  const btn = document.getElementById("login-btn");
  const errDiv = document.getElementById("login-error");
  btn.disabled = true;
  btn.textContent = "Signing in...";
  errDiv.style.display = "none";
  try {
    const r = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: document.getElementById("login-email").value,
        password: document.getElementById("login-password").value,
      }),
    });
    if (r.ok) {
      const data = await r.json();
      currentUser = data.user;
      showApp();
    } else {
      const err = await r.json().catch(() => ({ detail: "Login failed" }));
      errDiv.textContent = err.detail || "Invalid email or password";
      errDiv.style.display = "block";
    }
  } catch {
    errDiv.textContent = "Network error. Please try again.";
    errDiv.style.display = "block";
  }
  btn.disabled = false;
  btn.textContent = "Sign In";
}

async function handleLogout() {
  await fetch("/api/auth/logout", { method: "POST" });
  currentUser = null;
  document.getElementById("main-app").classList.add("hidden");
  document.getElementById("login-screen").classList.remove("hidden");
  document.getElementById("login-password").value = "";
}

function showApp() {
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("main-app").classList.remove("hidden");
  document.getElementById("user-display-name").textContent = currentUser
    ? currentUser.name
    : "";
  loadStats();
  navigateTo("dashboard");
}

// --- Hash-based router ---
function navigateTo(view) {
  window.location.hash = "#" + view;
}

function handleRoute() {
  const hash = window.location.hash.replace("#", "") || "dashboard";
  const view = VIEWS.includes(hash) ? hash : "dashboard";

  // Update sidebar active state
  document.querySelectorAll("[data-nav]").forEach((el) => {
    const isActive = el.dataset.nav === view;
    el.classList.toggle("bg-primary/10", isActive);
    el.classList.toggle("text-primary", isActive);
    el.classList.toggle("text-slate-400", !isActive);
  });

  // Show/hide views
  VIEWS.forEach((v) => {
    const el = document.getElementById("view-" + v);
    if (el) el.classList.toggle("hidden", v !== view);
  });

  // Load data for active view
  if (view === "dashboard") loadStats();
  if (view === "documents") loadDocuments();
  if (view === "review") loadReviewQueue();
}

window.addEventListener("hashchange", handleRoute);

// --- Init ---
async function init() {
  // Check if already authenticated via session cookie
  try {
    const r = await fetch("/api/auth/me");
    if (r.ok) {
      const data = await r.json();
      currentUser = data.user;
      showApp();
      return;
    }
  } catch {}
  // Not authenticated — show login
  document.getElementById("login-screen").classList.remove("hidden");
}

// Keyboard shortcuts
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeDetail();
    closeRejectModal();
  }
});

init();
