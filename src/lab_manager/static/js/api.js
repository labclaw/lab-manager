// api.js — API helpers, escapeHtml, toast notifications
"use strict";

const API = "/api/v1/documents";
let currentUser = null;

/**
 * Fetch wrapper that redirects to login on 401.
 */
async function apiFetch(url, opts) {
  const r = await fetch(url, opts);
  if (r.status === 401) {
    currentUser = null;
    document.getElementById("main-app").classList.add("hidden");
    document.getElementById("login-screen").classList.remove("hidden");
    showToast("Session expired. Please sign in again.", "error");
    throw new Error("Unauthorized");
  }
  return r;
}

/**
 * XSS prevention — escape HTML entities before inserting into innerHTML.
 * Must be called on every API-supplied string value before interpolation.
 * Returns "" for null/undefined; handles numeric 0 correctly.
 */
function escapeHtml(s) {
  if (s == null || s === "") return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Show a toast notification at the bottom of the screen.
 */
function showToast(msg, type) {
  const t = document.createElement("div");
  t.className = "toast toast-" + type;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 5000);
}
