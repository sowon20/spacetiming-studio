// 간단한 상태
let messages = [];
let nextId = 1;
let pinnedId = null;
let attachments = [];

const chatListEl = document.getElementById("chat-list");
const inputEl = document.getElementById("composer-input");
const sendBtn = document.getElementById("send-btn");
const attachBtn = document.getElementById("attach-btn");
const fileInput = document.getElementById("file-input");
const attachmentsStrip = document.getElementById("attachments-strip");
const pinnedBar = document.getElementById("pinned-bar");
const pinnedSummaryEl = document.getElementById("pinned-summary");
const pinnedClearBtn = document.getElementById("pinned-clear");
const pinnedContentBtn = document.getElementById("pinned-content-btn");
const pinModalBackdrop = document.getElementById("pin-modal-backdrop");
const pinModalBody = document.getElementById("pin-modal-body");
const pinModalMeta = document.getElementById("pin-modal-meta");
const pinModalClose = document.getElementById("pin-modal-close");
const heroMeta = document.getElementById("hero-meta");

function nowTimeString() {
  const d = new Date();
  const h = d.getHours();
  const m = String(d.getMinutes()).padStart(2, "0");
  const ampm = h < 12 ? "오전" : "오후";
  const hour12 = h % 12 || 12;
  return `${ampm} ${hour12}:${m}`;
}

function renderMessages() {
  chatListEl.innerHTML = "";
  messages.forEach((msg) => {
    const li = document.createElement("article");
    li.className = `message ${msg.role}` + (msg.id === pinnedId ? " pinned" : "");
    li.dataset.id = msg.id;

    const header = document.createElement("div");
    header.className = "msg-header";

    const author = document.createElement("span");
    author.className = "msg-author";
    author.textContent = msg.role === "user" ? "소원" : "부감독";

    const actions = document.createElement("div");
    actions.className = "msg-actions";

    const btnPin = document.createElement("button");
    btnPin.textContent = "📌";
    btnPin.title = "이 메시지 핀 고정";
    btnPin.dataset.action = "pin";
    btnPin.dataset.id = msg.id;

    const btnRestart = document.createElement("button");
    btnRestart.textContent = "↺";
    btnRestart.title = "이 순간부터 다시 시작";
    btnRestart.dataset.action = "restart";
    btnRestart.dataset.id = msg.id;

    const btnEdit = document.createElement("button");
    btnEdit.textContent = "✎";
    btnEdit.title = "수정";
    btnEdit.dataset.action = "edit";
    btnEdit.dataset.id = msg.id;

    const btnDelete = document.createElement("button");
    btnDelete.textContent = "🗑";
    btnDelete.title = "삭제";
    btnDelete.dataset.action = "delete";
    btnDelete.dataset.id = msg.id;

    actions.append(btnPin, btnRestart, btnEdit, btnDelete);
    header.append(author, actions);

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = msg.content;

    const meta = document.createElement("div");
    meta.className = "msg-meta";
    meta.textContent = msg.time || "";

    li.append(header, bubble, meta);
    chatListEl.appendChild(li);
  });

  chatListEl.scrollTop = chatListEl.scrollHeight;
}

function refreshPinnedBar() {
  if (!pinnedId) {
    pinnedBar.hidden = true;
    return;
  }
  const msg = messages.find((m) => m.id === pinnedId);
  if (!msg) {
    pinnedId = null;
    pinnedBar.hidden = true;
    return;
  }
  pinnedBar.hidden = false;
  const summary =
    msg.content.length > 60 ? msg.content.slice(0, 60) + "…" : msg.content;
  pinnedSummaryEl.textContent = summary;
}

function addMessage(role, content) {
  const msg = {
    id: nextId++,
    role,
    content,
    time: nowTimeString(),
    attachments: attachments.slice(),
  };
  messages.push(msg);
  heroMeta.textContent = `오늘 ${messages.length}개 메시지 기록됨`;
  attachments = [];
  renderAttachments();
  renderMessages();
}

function renderAttachments() {
  attachmentsStrip.innerHTML = "";
  if (!attachments.length) {
    attachmentsStrip.classList.remove("visible");
    return;
  }
  attachmentsStrip.classList.add("visible");
  attachments.forEach((item, idx) => {
    const chip = document.createElement("div");
    const isImage = !!item.previewUrl;
    chip.className = "attachment-chip" + (isImage ? " image" : "");

    if (isImage) {
      const img = document.createElement("img");
      img.className = "attachment-preview-img";
      img.src = item.previewUrl;
      chip.appendChild(img);
    } else {
      const name = document.createElement("span");
      name.className = "attachment-name";
      name.textContent = item.file.name;
      chip.appendChild(name);
    }

    const btnRemove = document.createElement("button");
    btnRemove.className = "attachment-remove";
    btnRemove.textContent = "×";
    btnRemove.dataset.index = idx;
    chip.appendChild(btnRemove);

    attachmentsStrip.appendChild(chip);
  });
}

// 입력창 동작
inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = inputEl.scrollHeight + "px";
  const hasText = inputEl.value.trim().length > 0;
  sendBtn.classList.toggle("disabled", !hasText);
});

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
});

sendBtn.addEventListener("click", () => {
  if (sendBtn.classList.contains("disabled")) return;
  handleSend();
});

function handleSend() {
  const text = inputEl.value.trim();
  if (!text) return;
  addMessage("user", text);
  inputEl.value = "";
  inputEl.style.height = "auto";
  sendBtn.classList.add("disabled");
  // TODO: 여기서 백엔드 호출 붙이면 됨.
}

// 파일 첨부
attachBtn.addEventListener("click", () => {
  fileInput.click();
});

fileInput.addEventListener("change", () => {
  const files = Array.from(fileInput.files || []);
  files.forEach((file) => {
    const item = { file, previewUrl: null };
    if (file.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.onload = (e) => {
        item.previewUrl = e.target.result;
        renderAttachments();
      };
      reader.readAsDataURL(file);
    }
    attachments.push(item);
  });
  renderAttachments();
  fileInput.value = "";
});

attachmentsStrip.addEventListener("click", (e) => {
  const btn = e.target.closest(".attachment-remove");
  if (!btn) return;
  const idx = Number(btn.dataset.index);
  attachments.splice(idx, 1);
  renderAttachments();
});

// 메시지 액션
chatListEl.addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const id = Number(btn.dataset.id);
  const action = btn.dataset.action;
  const idx = messages.findIndex((m) => m.id === id);
  if (idx === -1) return;

  const msg = messages[idx];

  if (action === "pin") {
    pinnedId = pinnedId === id ? null : id;
    refreshPinnedBar();
    renderMessages();
  }

  if (action === "restart") {
    if (
      !confirm(
        "이 메시지 이후의 대화 기록을 모두 지우고\n여기서부터 다시 시작할까요?"
      )
    )
      return;
    messages = messages.slice(0, idx + 1);
    if (pinnedId && !messages.some((m) => m.id === pinnedId)) {
      pinnedId = null;
    }
    renderMessages();
    refreshPinnedBar();
  }

  if (action === "edit") {
    const newText = prompt("메시지 수정", msg.content);
    if (newText === null) return;
    msg.content = newText;
    renderMessages();
    refreshPinnedBar();
  }

  if (action === "delete") {
    if (!confirm("이 메시지를 삭제할까요?")) return;
    messages.splice(idx, 1);
    if (pinnedId === id) pinnedId = null;
    renderMessages();
    refreshPinnedBar();
  }
});

// PIN 모달
pinnedClearBtn.addEventListener("click", () => {
  pinnedId = null;
  refreshPinnedBar();
  renderMessages();
});

pinnedContentBtn.addEventListener("click", () => {
  if (!pinnedId) return;
  const msg = messages.find((m) => m.id === pinnedId);
  if (!msg) return;
  pinModalBody.textContent = msg.content;
  pinModalMeta.textContent = `${msg.role === "user" ? "소원" : "부감독"} · ${
    msg.time || ""
  }`;
  pinModalBackdrop.classList.add("visible");
});

pinModalClose.addEventListener("click", () => {
  pinModalBackdrop.classList.remove("visible");
});

pinModalBackdrop.addEventListener("click", (e) => {
  if (e.target === pinModalBackdrop) {
    pinModalBackdrop.classList.remove("visible");
  }
});

// 초기 더미 메시지
addMessage("assistant", "다시 연결 완료. 지금부터는 이 창이 소원 전용 대기실이야.");
addMessage("user", "좋아. 오늘은 감정 말고 구조부터 같이 봐보자.");
addMessage(
  "assistant",
  "오케이. 지금 화면 기준으로, 필요한 기능부터 하나씩 박아 나가면 된다."
);
