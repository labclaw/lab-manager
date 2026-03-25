// chat.js — AI Chat panel for scientist-friendly natural language interaction
"use strict";

let chatHistory = [];
let chatOpen = false;

function toggleChat() {
  chatOpen = !chatOpen;
  const panel = document.getElementById("chat-panel");
  const overlay = document.getElementById("chat-overlay");
  if (chatOpen) {
    panel.classList.add("open");
    overlay.classList.add("show");
    document.getElementById("chat-input").focus();
  } else {
    panel.classList.remove("open");
    overlay.classList.remove("show");
  }
}

function clearChat() {
  chatHistory = [];
  const container = document.getElementById("chat-messages");
  container.innerHTML = `
    <div class="flex gap-3">
      <div class="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
        <span class="material-symbols-outlined text-primary text-sm">smart_toy</span>
      </div>
      <div class="bg-background-dark rounded-xl rounded-tl-sm px-4 py-3 text-sm text-slate-300 max-w-[380px]">
        <p class="mb-2">Hi! I'm your lab assistant. Ask me anything about your inventory, orders, or documents.</p>
        <p class="text-slate-500 text-xs">Try: "Do we have acetone?" or "What's expiring this week?"</p>
      </div>
    </div>`;
}

function quickAsk(question) {
  document.getElementById("chat-input").value = question;
  sendChat(new Event("submit"));
}

function appendUserMessage(text) {
  const container = document.getElementById("chat-messages");
  const userName = currentUser ? escapeHtml(currentUser.name) : "You";
  container.insertAdjacentHTML(
    "beforeend",
    `<div class="flex gap-3 justify-end chat-msg-user">
      <div class="chat-bubble rounded-xl rounded-tr-sm px-4 py-3 text-sm max-w-[380px]">
        ${escapeHtml(text)}
      </div>
      <div class="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
        <span class="material-symbols-outlined text-primary text-sm">person</span>
      </div>
    </div>`
  );
  scrollChatBottom();
}

function appendThinking() {
  const container = document.getElementById("chat-messages");
  container.insertAdjacentHTML(
    "beforeend",
    `<div class="flex gap-3 chat-msg-ai" id="chat-thinking">
      <div class="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
        <span class="material-symbols-outlined text-primary text-sm">smart_toy</span>
      </div>
      <div class="chat-bubble rounded-xl rounded-tl-sm px-4 py-3 text-sm text-slate-400 max-w-[380px]">
        <span class="chat-thinking">Searching your lab data...</span>
      </div>
    </div>`
  );
  scrollChatBottom();
}

function removeThinking() {
  const el = document.getElementById("chat-thinking");
  if (el) el.remove();
}

function appendAIMessage(answer, details) {
  const container = document.getElementById("chat-messages");
  let detailHtml = "";

  // Show result count if available
  if (details && details.row_count != null && details.row_count > 0) {
    detailHtml += `<div class="text-xs text-slate-500 mt-2 pt-2 border-t border-border-dark/50">Based on ${details.row_count} record${details.row_count !== 1 ? "s" : ""} from your database</div>`;
  }

  // Show quick follow-up actions based on context
  let actionsHtml = "";
  if (details && details.raw_results && details.raw_results.length > 0) {
    const actions = suggestFollowUps(details);
    if (actions.length > 0) {
      actionsHtml = `<div class="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-border-dark/50">
        ${actions.map((a) => `<button onclick="quickAsk('${escapeHtml(a)}')" class="px-2 py-1 rounded-md text-[11px] font-medium border border-border-dark text-slate-400 hover:border-primary hover:text-primary transition-colors">${escapeHtml(a)}</button>`).join("")}
      </div>`;
  }
  }

  // Format answer text: support basic markdown-like formatting
  const formattedAnswer = formatAnswer(answer);

  container.insertAdjacentHTML(
    "beforeend",
    `<div class="flex gap-3 chat-msg-ai">
      <div class="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
        <span class="material-symbols-outlined text-primary text-sm">smart_toy</span>
      </div>
      <div class="chat-bubble rounded-xl rounded-tl-sm px-4 py-3 text-sm text-slate-300 max-w-[380px]">
        ${formattedAnswer}
        ${detailHtml}
        ${actionsHtml}
      </div>
    </div>`
  );
  scrollChatBottom();
}

function formatAnswer(text) {
  if (!text) return "";
  // Escape HTML first
  let s = escapeHtml(text);
  // Bold: **text**
  s = s.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  // Line breaks
  s = s.replace(/\n/g, "<br>");
  // Numbered lists: "1. " at start of line
  s = s.replace(/(^|\<br\>)(\d+)\.\s/g, '$1<span class="text-primary font-medium">$2.</span> ');
  return s;
}

function suggestFollowUps(details) {
  const actions = [];
  const results = details.raw_results || [];
  const sql = (details.sql || "").toLowerCase();

  if (sql.includes("inventory") && sql.includes("expiry")) {
    actions.push("Show items expiring this week");
  }
  if (sql.includes("inventory") && !sql.includes("expiry")) {
    actions.push("Which items are expiring soon?");
  }
  if (sql.includes("order")) {
    actions.push("Show pending orders");
  }
  if (sql.includes("vendor")) {
    actions.push("Show spending by vendor");
  }
  if (results.length > 5) {
    actions.push("Export this as CSV");
  }
  return actions.slice(0, 3);
}

function scrollChatBottom() {
  const container = document.getElementById("chat-messages");
  container.scrollTop = container.scrollHeight;
}

async function sendChat(e) {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const question = input.value.trim();
  if (!question) return;

  input.value = "";
  appendUserMessage(question);
  appendThinking();

  const sendBtn = document.getElementById("chat-send-btn");
  sendBtn.disabled = true;

  try {
    const r = await apiFetch("/api/v1/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    removeThinking();

    if (r.ok) {
      const data = await r.json();
      chatHistory.push({ q: question, a: data.answer });
      appendAIMessage(data.answer, data);
    } else if (r.status === 429) {
      appendAIMessage(
        "I'm getting too many questions right now. Please wait a moment and try again.",
        null
      );
    } else {
      const err = await r.json().catch(() => ({}));
      appendAIMessage(
        err.detail || "Sorry, I couldn't process that question. Please try rephrasing it.",
        null
      );
    }
  } catch (err) {
    removeThinking();
    if (err.message !== "Unauthorized") {
      appendAIMessage(
        "Connection error. Please check your network and try again.",
        null
      );
    }
  }

  sendBtn.disabled = false;
  input.focus();
}

// Keyboard shortcut: Ctrl/Cmd+K to open chat
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "k") {
    e.preventDefault();
    toggleChat();
  }
});
