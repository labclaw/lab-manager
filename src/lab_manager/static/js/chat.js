// chat.js — Lab IM: WebSocket chat with AI team members
"use strict";

let chatWs = null;
let chatReconnectTimer = null;
const CHAT_STAFF = [
  "Inventory-Manager",
  "Document-Processor",
];

// --- WebSocket connection ---

function connectChat() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const url = proto + "//" + location.host + "/ws/chat";
  chatWs = new WebSocket(url);

  chatWs.onopen = function () {
    renderChatStatus("connected");
  };

  chatWs.onmessage = function (evt) {
    try {
      const data = JSON.parse(evt.data);
      if (data.type === "history") {
        const container = document.getElementById("chat-messages");
        if (container) {
          container.innerHTML = "";
          (data.messages || []).forEach(function (m) {
            appendChatBubble(m, false);
          });
          scrollChatToBottom();
        }
        return;
      }
      appendChatBubble(data, true);
      scrollChatToBottom();
    } catch (e) {
      console.error("Chat WS parse error:", e);
    }
  };

  chatWs.onclose = function () {
    renderChatStatus("disconnected");
    chatReconnectTimer = setTimeout(connectChat, 3000);
  };

  chatWs.onerror = function () {
    renderChatStatus("error");
  };
}

function disconnectChat() {
  if (chatWs) {
    chatWs.close();
    chatWs = null;
  }
  if (chatReconnectTimer) {
    clearTimeout(chatReconnectTimer);
    chatReconnectTimer = null;
  }
}

function renderChatStatus(status) {
  const el = document.getElementById("chat-status");
  if (!el) return;
  const map = {
    connected: { dot: "bg-accent-green", text: "Connected" },
    disconnected: { dot: "bg-yellow-500", text: "Reconnecting..." },
    error: { dot: "bg-red-500", text: "Connection error" },
  };
  const s = map[status] || map.disconnected;
  el.innerHTML =
    '<span class="w-2 h-2 rounded-full ' +
    s.dot +
    ' inline-block mr-1.5"></span>' +
    s.text;
}

// --- Send message ---

function sendChatMessage() {
  const input = document.getElementById("chat-input");
  if (!input) return;
  const content = input.value.trim();
  if (!content) return;

  const msg = {
    from: currentUser ? currentUser.name : "user",
    content: content,
  };

  if (chatWs && chatWs.readyState === WebSocket.OPEN) {
    chatWs.send(JSON.stringify(msg));
  } else {
    // Fallback to REST
    fetch("/api/v1/chat/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(msg),
    }).catch(function (e) {
      console.error("Chat REST send error:", e);
    });
  }
  input.value = "";
  hideMentionAutocomplete();
}

// --- @mention autocomplete ---

let mentionActiveIndex = -1;

function handleChatKeydown(e) {
  const autocomplete = document.getElementById("mention-autocomplete");
  if (!autocomplete || autocomplete.classList.contains("hidden")) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
    return;
  }

  const items = autocomplete.querySelectorAll(".mention-item");
  if (e.key === "ArrowDown") {
    e.preventDefault();
    mentionActiveIndex = Math.min(mentionActiveIndex + 1, items.length - 1);
    updateMentionHighlight(items);
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    mentionActiveIndex = Math.max(mentionActiveIndex - 1, 0);
    updateMentionHighlight(items);
  } else if (e.key === "Enter" || e.key === "Tab") {
    e.preventDefault();
    if (mentionActiveIndex >= 0 && mentionActiveIndex < items.length) {
      applyMention(items[mentionActiveIndex].dataset.name);
    }
  } else if (e.key === "Escape") {
    hideMentionAutocomplete();
  }
}

function updateMentionHighlight(items) {
  items.forEach(function (el, i) {
    el.classList.toggle("bg-primary/20", i === mentionActiveIndex);
    el.classList.toggle("text-primary", i === mentionActiveIndex);
  });
}

function handleChatInput(e) {
  const input = e.target;
  const val = input.value;
  const cursorPos = input.selectionStart;
  const textBeforeCursor = val.substring(0, cursorPos);

  const atMatch = textBeforeCursor.match(/@([\w-]*)$/);
  if (atMatch) {
    const filter = atMatch[1].toLowerCase();
    const matches = CHAT_STAFF.filter(function (s) {
      return s.toLowerCase().indexOf(filter) === 0;
    });
    if (matches.length > 0) {
      showMentionAutocomplete(matches, input);
      return;
    }
  }
  hideMentionAutocomplete();
}

function showMentionAutocomplete(matches, inputEl) {
  let ac = document.getElementById("mention-autocomplete");
  if (!ac) {
    ac = document.createElement("div");
    ac.id = "mention-autocomplete";
    ac.className =
      "absolute bottom-full left-0 mb-1 bg-surface-dark border border-border-dark rounded-lg shadow-xl overflow-hidden z-50";
    const wrapper = document.getElementById("chat-input-wrapper");
    if (wrapper) wrapper.appendChild(ac);
  }
  mentionActiveIndex = 0;
  let html = "";
  matches.forEach(function (name) {
    html +=
      '<div class="mention-item px-3 py-2 text-sm text-slate-300 cursor-pointer hover:bg-primary/20 hover:text-primary transition-colors" data-name="' +
      name +
      '">' +
      '<span class="material-symbols-outlined text-sm align-middle mr-1">smart_toy</span>' +
      name +
      "</div>";
  });
  ac.innerHTML = html;
  ac.classList.remove("hidden");
  updateMentionHighlight(ac.querySelectorAll(".mention-item"));

  ac.querySelectorAll(".mention-item").forEach(function (el) {
    el.addEventListener("mousedown", function (evt) {
      evt.preventDefault();
      applyMention(el.dataset.name);
    });
  });
}

function hideMentionAutocomplete() {
  const ac = document.getElementById("mention-autocomplete");
  if (ac) ac.classList.add("hidden");
  mentionActiveIndex = -1;
}

function applyMention(name) {
  const input = document.getElementById("chat-input");
  if (!input) return;
  const val = input.value;
  const cursorPos = input.selectionStart;
  const textBefore = val.substring(0, cursorPos);
  const textAfter = val.substring(cursorPos);
  const replaced = textBefore.replace(/@[\w-]*$/, "@" + name + " ");
  input.value = replaced + textAfter;
  input.focus();
  const newPos = replaced.length;
  input.setSelectionRange(newPos, newPos);
  hideMentionAutocomplete();
}

// --- Render ---

function appendChatBubble(msg, animate) {
  const container = document.getElementById("chat-messages");
  if (!container) return;

  const isUser =
    msg.type === "message" &&
    msg.from === (currentUser ? currentUser.name : "user");
  const isSystem = msg.type === "system";
  const isAI = msg.type === "ai_response";

  const wrapper = document.createElement("div");
  wrapper.className =
    "flex gap-2.5 mb-3" + (animate ? " chat-msg-enter" : "");

  if (isUser) {
    wrapper.classList.add("justify-end");
    wrapper.innerHTML =
      '<div class="max-w-[70%] px-4 py-2.5 rounded-2xl rounded-br-sm bg-primary text-white text-sm leading-relaxed">' +
      escapeHtml(msg.content) +
      "</div>";
  } else if (isSystem) {
    wrapper.classList.add("justify-center");
    wrapper.innerHTML =
      '<div class="text-xs text-slate-500 italic">' +
      escapeHtml(msg.content) +
      "</div>";
  } else if (isAI) {
    wrapper.innerHTML =
      '<div class="w-8 h-8 rounded-full bg-accent-green/20 flex items-center justify-center flex-shrink-0 mt-0.5">' +
      '<span class="material-symbols-outlined text-accent-green text-base">smart_toy</span>' +
      "</div>" +
      '<div class="max-w-[70%]">' +
      '<div class="text-xs text-accent-green font-medium mb-1">' +
      escapeHtml(msg.from) +
      "</div>" +
      '<div class="px-4 py-2.5 rounded-2xl rounded-bl-sm bg-surface-dark border border-border-dark text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">' +
      escapeHtml(msg.content) +
      "</div>" +
      "</div>";
  } else {
    // Other user's message
    wrapper.innerHTML =
      '<div class="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">' +
      '<span class="material-symbols-outlined text-primary text-base">person</span>' +
      "</div>" +
      '<div class="max-w-[70%]">' +
      '<div class="text-xs text-slate-500 font-medium mb-1">' +
      escapeHtml(msg.from) +
      "</div>" +
      '<div class="px-4 py-2.5 rounded-2xl rounded-bl-sm bg-surface-dark border border-border-dark text-sm text-slate-300 leading-relaxed">' +
      escapeHtml(msg.content) +
      "</div>" +
      "</div>";
  }

  // Timestamp tooltip
  if (!isSystem) {
    const ts = msg.timestamp
      ? new Date(msg.timestamp).toLocaleTimeString()
      : "";
    const bubble = wrapper.querySelector("div:last-child");
    if (bubble && ts) {
      bubble.title = ts;
    }
  }

  container.appendChild(wrapper);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function scrollChatToBottom() {
  const container = document.getElementById("chat-messages");
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}

// --- Load chat view ---

function loadChat() {
  disconnectChat();
  connectChat();
}
