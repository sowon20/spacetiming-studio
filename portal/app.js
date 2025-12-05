const DIRECTOR_API_URL = "/api/chat";

const chatListEl = document.getElementById("chat-list");
const sessionMetaEl = document.getElementById("session-meta");
const pinnedBarEl = document.getElementById("pinned-bar");
const pinnedSummaryEl = document.getElementById("pinned-summary");
const pinnedContentBtn = document.getElementById("pinned-content-btn");
const pinnedClearBtn = document.getElementById("pinned-clear");

const composerInput = document.getElementById("composer-input");
const sendBtn = document.getElementById("send-btn");
const attachBtn = document.getElementById("attach-btn");
const fileInput = document.getElementById("file-input");
const attachmentsStrip = document.getElementById("attachments-strip");

const pinModalBackdrop = document.getElementById("pin-modal-backdrop");
const pinModalBody = document.getElementById("pin-modal-body");
const pinModalMeta = document.getElementById("pin-modal-meta");
const pinModalClose = document.getElementById("pin-modal-close");

let messages = [];
let pinnedId = null;
let attachments = [];
let typingRow = null;

let isSending = false;

const STORAGE_KEY = "director_chat_messages_v1";

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderContent(raw) {
  if (raw === null || raw === undefined) return "";
  let text = String(raw);

  // 1) HTML 이스케이프 먼저
  text = escapeHtml(text);

  // 2) URL → 링크/이미지 미리보기
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  text = text.replace(urlRegex, (url) => {
    const lower = url.toLowerCase();
    const isImage =
      lower.endsWith(".png") ||
      lower.endsWith(".jpg") ||
      lower.endsWith(".jpeg") ||
      lower.endsWith(".gif") ||
      lower.endsWith(".webp");

    if (isImage) {
      return `<a href="${url}" target="_blank" rel="noopener noreferrer"><img src="${url}" alt="" /></a>`;
    }
    return `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`;
  });

  // 3) **굵게** 처리
  text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  // 4) 줄바꿈 → <br>
  text = text.replace(/\n/g, "<br>");

  return text;
}

function nowTime() {
  const d = new Date();
  const hh = d.getHours().toString().padStart(2, "0");
  const mm = d.getMinutes().toString().padStart(2, "0");
  return `${hh}:${mm}`;
}

function saveToStorage() {
  try {
    // 너무 커지지 않도록 최근 500개만 저장
    const trimmed = messages.slice(-500);
    const payload = {
      messages: trimmed,
      pinnedId,
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch (e) {
    console.warn("localStorage save failed", e);
  }
}

function loadFromStorage() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    messages = parsed.messages || [];
    pinnedId = parsed.pinnedId || null;
  } catch (_) {
    // ignore
  }
}

function renderPinned() {
  if (!pinnedId) {
    pinnedBarEl.hidden = true;
    return;
  }
  const msg = messages.find((m) => m.id === pinnedId);
  if (!msg) {
    pinnedId = null;
    pinnedBarEl.hidden = true;
    return;
  }
  pinnedBarEl.hidden = false;
  pinnedSummaryEl.textContent =
    msg.content.length > 60 ? msg.content.slice(0, 60) + "…" : msg.content;
}

function renderMessages() {
  chatListEl.innerHTML = "";
  messages.forEach((m) => {
    const row = document.createElement("article");
    row.className = `message-row ${m.role}`;
    row.dataset.id = m.id;

    const header = document.createElement("div");
    header.className = "msg-header";

    const author = document.createElement("span");
    author.className = "msg-author";
    author.textContent = m.role === "user" ? "소원" : "부감독";

    const timeEl = document.createElement("span");
    timeEl.className = "msg-time";
    timeEl.textContent = m.time || "";

    const actions = document.createElement("div");
    actions.className = "msg-actions";

    const pinBtn = document.createElement("button");
    pinBtn.textContent = "📌";
    pinBtn.title = "핀";
    pinBtn.onclick = () => {
      pinnedId = m.id;
      saveToStorage();
      renderPinned();
    };

    const editBtn = document.createElement("button");
    editBtn.textContent = "✎";
    editBtn.title = "수정 (아직 준비 중)";
    editBtn.disabled = true;

    const delBtn = document.createElement("button");
    delBtn.textContent = "🗑";
    delBtn.title = "삭제";
    delBtn.onclick = () => {
      messages = messages.filter((x) => x.id !== m.id);
      if (pinnedId === m.id) pinnedId = null;
      saveToStorage();
      renderMessages();
      renderPinned();
      updateSessionMeta();
    };

    actions.append(pinBtn, editBtn, delBtn);

    header.append(author, timeEl, actions);

    const bubbleWrap = document.createElement("div");
    bubbleWrap.className = "msg-bubble-wrap";

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    bubble.innerHTML = renderContent(m.content);

    bubbleWrap.appendChild(bubble);

    row.append(header, bubbleWrap);
    chatListEl.appendChild(row);
  });

  if (typingRow) {
    chatListEl.appendChild(typingRow);
  }

  chatListEl.scrollTop = chatListEl.scrollHeight;
  updateSessionMeta();
}

function updateSessionMeta() {
  const count = messages.length;
  sessionMetaEl.textContent = `오늘 ${count}개 메시지`;
}

function addMessage(role, content) {
  const msg = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role,
    content,
    time: nowTime(),
  };
  messages.push(msg);
  saveToStorage();
  renderMessages();
  return msg;
}

function clearTyping() {
  if (typingRow) {
    typingRow.remove();
    typingRow = null;
  }
}

function showTyping() {
  clearTyping();
  const row = document.createElement("article");
  row.className = "message-row assistant typing";

  const header = document.createElement("div");
  header.className = "msg-header";

  const author = document.createElement("span");
  author.className = "msg-author";
  author.textContent = "부감독";

  const timeEl = document.createElement("span");
  timeEl.className = "msg-time";
  timeEl.textContent = "";

  const actions = document.createElement("div");
  actions.className = "msg-actions";

  header.append(author, timeEl, actions);

  const wrap = document.createElement("div");
  wrap.className = "msg-bubble-wrap";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";

  for (let i = 0; i < 3; i++) {
    const dot = document.createElement("span");
    dot.className = "typing-dot";
    bubble.appendChild(dot);
  }

  wrap.appendChild(bubble);
  row.append(header, wrap);
  typingRow = row;

  chatListEl.appendChild(row);
  chatListEl.scrollTop = chatListEl.scrollHeight;
}

function renderAttachments() {
  attachmentsStrip.innerHTML = "";
  attachments.forEach((f, idx) => {
    const pill = document.createElement("div");
    pill.className = "attachment-pill";

    const nameSpan = document.createElement("span");
    nameSpan.textContent = f.name;

    const removeBtn = document.createElement("button");
    removeBtn.className = "attachment-remove";
    removeBtn.textContent = "×";
    removeBtn.onclick = () => {
      attachments.splice(idx, 1);
      renderAttachments();
    };

    pill.append(nameSpan, removeBtn);
    attachmentsStrip.appendChild(pill);
  });
}

async function sendToDirector(text) {
  const payload = {
    messages: [
      {
        role: "user",
        content: text,
      },
    ],
  };

  const res = await fetch(DIRECTOR_API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  const data = await res.json();
  return data.reply || "(응답이 비었어.)";
}

async function handleSend() {
  // 이미 전송 중이면 무시
  if (isSending) return;

  const raw = composerInput.value.trim();
  if (!raw) return;

  isSending = true;  // 잠금

  addMessage("user", raw);
  composerInput.value = "";
  sendBtn.classList.add("disabled");

  showTyping();

  try {
    const replyText = await sendToDirector(raw);
    clearTyping();
    addMessage("assistant", replyText);
  } catch (err) {
    clearTyping();
    addMessage("assistant", `연결 중 오류가 났어.\n(${err.message})`);
  } finally {
    isSending = false; // 해제
  }
}

function initEvents() {
  composerInput.addEventListener("input", () => {
    const hasText = composerInput.value.trim().length > 0;
    if (hasText) {
      sendBtn.classList.remove("disabled");
    } else {
      sendBtn.classList.add("disabled");
    }
  });

  composerInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!sendBtn.classList.contains("disabled")) {
        handleSend();
      }
    }
  });

  sendBtn.addEventListener("click", () => {
    if (!sendBtn.classList.contains("disabled")) {
      handleSend();
    }
  });

  attachBtn.addEventListener("click", () => {
    fileInput.click();
  });

  fileInput.addEventListener("change", (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    attachments = attachments.concat(files);
    renderAttachments();
  });

  pinnedClearBtn.addEventListener("click", () => {
    pinnedId = null;
    saveToStorage();
    renderPinned();
  });

  pinnedContentBtn.addEventListener("click", () => {
    if (!pinnedId) return;
    const msg = messages.find((m) => m.id === pinnedId);
    if (!msg) return;
    pinModalBody.innerHTML = renderContent(msg.content);
    pinModalMeta.textContent = `${msg.role === "user" ? "소원" : "부감독"} · ${msg.time}`;
    pinModalBackdrop.classList.add("open");
  });

  pinModalClose.addEventListener("click", () => {
    pinModalBackdrop.classList.remove("open");
  });

  pinModalBackdrop.addEventListener("click", (e) => {
    if (e.target === pinModalBackdrop) {
      pinModalBackdrop.classList.remove("open");
    }
  });
}

function init() {
  loadFromStorage();
  renderMessages();
  renderPinned();
  initEvents();
}

document.addEventListener("DOMContentLoaded", init);
