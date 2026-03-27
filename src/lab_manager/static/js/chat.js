// chat.js — Lab IM: WebSocket chat with AI team members
"use strict";

let chatWs = null;
let chatReconnectTimer = null;
let chatUnreadCount = 0;
let chatLastTimestamp = "";
let _feedPollTimer = null;
let _reconnectAttempts = 0;

var WS_MAX_RETRIES = 10;
var WS_BASE_DELAY = 1000;
var WS_MAX_DELAY = 30000;

const CHAT_STAFF = [
  "Inventory-Manager",
  "Document-Processor",
];

const FEED_POLL_INTERVAL = 10000;
var MAX_FEED_CARDS = 50;

// --- WebSocket connection ---

function connectChat() {
  var proto = location.protocol === "https:" ? "wss:" : "ws:";
  var url = proto + "//" + location.host + "/ws/chat";
  chatWs = new WebSocket(url);

  chatWs.onopen = function () {
    _reconnectAttempts = 0;
    renderChatStatus("connected");
  };

  chatWs.onmessage = function (evt) {
    try {
      var data = JSON.parse(evt.data);
      if (data.type === "history") {
        var container = document.getElementById("chat-messages");
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
      updateUnreadCount(1);
    } catch (e) {
      console.error("Chat WS parse error:", e);
    }
  };

  chatWs.onclose = function () {
    renderChatStatus("disconnected");
    if (_reconnectAttempts >= WS_MAX_RETRIES) {
      renderChatStatus("max_retries");
      return;
    }
    var delay = Math.min(WS_BASE_DELAY * Math.pow(2, _reconnectAttempts), WS_MAX_DELAY);
    _reconnectAttempts++;
    chatReconnectTimer = setTimeout(connectChat, delay);
  };

  chatWs.onerror = function () {
    renderChatStatus("error");
  };
}

function disconnectChat() {
  _reconnectAttempts = WS_MAX_RETRIES + 1; // prevent reconnect after intentional close
  if (chatWs) {
    chatWs.close();
    chatWs = null;
  }
  if (chatReconnectTimer) {
    clearTimeout(chatReconnectTimer);
    chatReconnectTimer = null;
  }
  stopFeedPoll();
}

function renderChatStatus(status) {
  var el = document.getElementById("chat-status");
  if (!el) return;
  var map = {
    connected: { dot: "bg-accent-green", text: "Connected" },
    disconnected: { dot: "bg-yellow-500", text: "Reconnecting..." },
    error: { dot: "bg-red-500", text: "Connection error" },
    max_retries: { dot: "bg-red-500", text: "Disconnected — click to retry" },
  };
  var s = map[status] || map.disconnected;
  el.innerHTML =
    '<span class="w-2 h-2 rounded-full ' +
    s.dot +
    ' inline-block mr-1.5"></span>' +
    s.text;
}

// --- Unread count badge ---

function updateUnreadCount(delta) {
  chatUnreadCount += delta;
  var badge = document.getElementById("chat-unread-badge");
  if (badge) {
    if (chatUnreadCount > 0) {
      badge.textContent = String(chatUnreadCount);
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
  }
}

function clearUnreadCount() {
  chatUnreadCount = 0;
  updateUnreadCount(0);
}

// --- Send message ---

function sendChatMessage() {
  var input = document.getElementById("chat-input");
  if (!input) return;
  var content = input.value.trim();
  if (!content) return;

  var msg = {
    from: currentUser ? currentUser.name : "user",
    content: content,
  };

  if (chatWs && chatWs.readyState === WebSocket.OPEN) {
    chatWs.send(JSON.stringify(msg));
  } else {
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

var mentionActiveIndex = -1;

function handleChatKeydown(e) {
  var autocomplete = document.getElementById("mention-autocomplete");
  if (!autocomplete || autocomplete.classList.contains("hidden")) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
    return;
  }

  var items = autocomplete.querySelectorAll(".mention-item");
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
  var input = e.target;
  var val = input.value;
  var cursorPos = input.selectionStart;
  var textBeforeCursor = val.substring(0, cursorPos);

  var atMatch = textBeforeCursor.match(/@([\w-]*)$/);
  if (atMatch) {
    var filter = atMatch[1].toLowerCase();
    var matches = CHAT_STAFF.filter(function (s) {
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
  var ac = document.getElementById("mention-autocomplete");
  if (!ac) {
    ac = document.createElement("div");
    ac.id = "mention-autocomplete";
    ac.className =
      "absolute bottom-full left-0 mb-1 bg-surface-dark border border-border-dark rounded-lg shadow-xl overflow-hidden z-50";
    var wrapper = document.getElementById("chat-input-wrapper");
    if (wrapper) wrapper.appendChild(ac);
  }
  mentionActiveIndex = 0;
  var html = "";
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
  var ac = document.getElementById("mention-autocomplete");
  if (ac) ac.classList.add("hidden");
  mentionActiveIndex = -1;
}

function applyMention(name) {
  var input = document.getElementById("chat-input");
  if (!input) return;
  var val = input.value;
  var cursorPos = input.selectionStart;
  var textBefore = val.substring(0, cursorPos);
  var textAfter = val.substring(cursorPos);
  var replaced = textBefore.replace(/@[\w-]*$/, "@" + name + " ");
  input.value = replaced + textAfter;
  input.focus();
  var newPos = replaced.length;
  input.setSelectionRange(newPos, newPos);
  hideMentionAutocomplete();
}

// --- Quick action buttons ---

function sendToAIStaff(staffName) {
  var input = document.getElementById("chat-input");
  if (!input) return;
  input.value = "@" + staffName + " ";
  input.focus();
}

function sendDigest() {
  var input = document.getElementById("chat-input");
  if (!input) return;
  input.value = "@Inventory-Manager Give me a summary of current inventory status";
  sendChatMessage();
}

// --- Feed polling ---

function startFeedPoll() {
  stopFeedPoll();
  _feedPollTimer = setInterval(pollFeed, FEED_POLL_INTERVAL);
}

function stopFeedPoll() {
  if (_feedPollTimer) {
    clearInterval(_feedPollTimer);
    _feedPollTimer = null;
  }
}

function pollFeed() {
  var url = "/api/v1/chat/feed?limit=10";
  if (chatLastTimestamp) {
    url += "&since=" + encodeURIComponent(chatLastTimestamp);
  }
  fetch(url)
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.messages && data.messages.length > 0) {
        var feedContent = document.getElementById("chat-feed-content");
        if (feedContent) {
          data.messages.forEach(function (m) {
            renderFeedCard(m, feedContent);
          });
        }
        chatLastTimestamp = data.messages[data.messages.length - 1].timestamp || "";
        updateUnreadCount(data.messages.length);
      }
      var onlineEl = document.getElementById("chat-online-count");
      if (onlineEl) onlineEl.textContent = String(data.online_count || 0);
    })
    .catch(function () {});
}

function renderFeedCard(msg, container) {
  var isAI = msg.type === "ai_response";
  var borderColor = isAI ? "border-l-accent-green" : "border-l-primary";
  var badge = isAI
    ? '<span class="px-1.5 py-0.5 text-xs rounded bg-accent-green/20 text-accent-green">AI</span>'
    : "";

  var card = document.createElement("div");
  card.className =
    "bg-background-dark/50 border border-border-dark border-l-2 " +
    borderColor +
    " rounded-lg p-3 text-xs cursor-pointer hover:bg-primary/5 transition-colors";
  card.innerHTML =
    '<div class="flex items-center gap-1.5 mb-1">' +
    badge +
    '<span class="text-slate-500">' +
    escapeHtml(msg.from || "") +
    "</span>" +
    "</div>" +
    '<div class="text-slate-300 text-xs">' +
    escapeHtml((msg.content || "").substring(0, 120)) +
    "</div>";
  card.addEventListener("click", function () {
    clearUnreadCount();
    showToast("Notification cleared", "success");
  });
  container.insertBefore(card, container.firstChild);
  while (container.children.length > MAX_FEED_CARDS) {
    container.removeChild(container.lastChild);
  }
}

// --- Reasoning chain ---

function runReasoning() {
  var input = document.getElementById("chat-input");
  var query = input ? input.value.trim() : "";
  if (!query) query = "How many reagents do I need to reorder?";

  fetch("/api/v1/chat/reasoning/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query: query }),
  })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.message) {
        appendChatBubble(data.message, true);
        scrollChatToBottom();
      }
      if (data.chain_result) {
        showToast("Reasoning chain completed", "success");
      }
    })
    .catch(function (e) {
      console.error("Reasoning chain error:", e);
      showToast("Reasoning chain failed", "error");
    });
}

// --- Render chat bubble ---

function appendChatBubble(msg, animate) {
  var container = document.getElementById("chat-messages");
  if (!container) return;

  var isUser =
    msg.type === "message" &&
    msg.from === (currentUser ? currentUser.name : "user");
  var isSystem = msg.type === "system";
  var isAI = msg.type === "ai_response";
  var hasReasoning = !!msg.reasoning;

  var wrapper = document.createElement("div");
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
    var reasoningBtn = hasReasoning
      ? '<button onclick="runReasoning()" class="mt-2 px-2 py-1 text-xs bg-accent-green/10 text-accent-green rounded hover:bg-accent-green/20 transition-colors">View Reasoning Chain</button>'
      : "";
    var badgeColor = msg.badge_color === "green" ? "accent-green" : "blue-400";
    var badgeTag = msg.badge
      ? '<span class="px-1.5 py-0.5 text-xs rounded bg-' + badgeColor + '/20 text-' + badgeColor + '">' + escapeHtml(msg.badge) + "</span>"
      : '<span class="px-1.5 py-0.5 text-xs rounded bg-accent-green/20 text-accent-green">AI</span>';

    wrapper.innerHTML =
      '<div class="w-8 h-8 rounded-full bg-accent-green/20 flex items-center justify-center flex-shrink-0 mt-0.5">' +
      '<span class="material-symbols-outlined text-accent-green text-base">smart_toy</span>' +
      "</div>" +
      '<div class="max-w-[70%]">' +
      '<div class="flex items-center gap-2 mb-1">' +
      '<span class="text-xs text-accent-green font-medium">' +
      escapeHtml(msg.from) +
      "</span>" +
      badgeTag +
      "</div>" +
      '<div class="px-4 py-2.5 rounded-2xl rounded-bl-sm bg-surface-dark border border-border-dark text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">' +
      escapeHtml(msg.content) +
      "</div>" +
      reasoningBtn +
      "</div>";
  } else {
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

  if (!isSystem) {
    var ts = msg.timestamp
      ? new Date(msg.timestamp).toLocaleTimeString()
      : "";
    var bubble = wrapper.querySelector("div:last-child");
    if (bubble && ts) {
      bubble.title = ts;
    }
  }

  container.appendChild(wrapper);
}

function scrollChatToBottom() {
  var container = document.getElementById("chat-messages");
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}

// --- Load chat view ---

function loadChat() {
  _reconnectAttempts = 0;
  disconnectChat();
  connectChat();
  startFeedPoll();
}
