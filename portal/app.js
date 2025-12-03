// app.js
// Spacetime Portal – 프론트만 있는 초기 버전
// (백엔드는 나중에 Gemini/텔레그램/자동화 서버랑 연결) 

const PortalApp = (() => {
  const state = {
    mode: "text", // 'text' | 'voice' | 'call' | 'multi'
    activeView: "portal",
  };

  // DOM 캐시
  const els = {};

  function cacheElements() {
    els.root = document.getElementById("portal-root");
    els.clock = document.getElementById("portal-clock");
    els.modeSwitch = document.getElementById("portal-mode-switch");
    els.modeButtons = els.modeSwitch
      ? Array.from(els.modeSwitch.querySelectorAll("[data-mode]"))
      : [];
    els.modeHint = document.getElementById("portal-mode-hint");

    els.navItems = Array.from(
      document.querySelectorAll(".nav-item[data-view]")
    );
    els.viewSections = Array.from(
      document.querySelectorAll("[data-view-section]")
    );

    els.contextTabs = document.getElementById("context-tabs");
    els.contextTabButtons = els.contextTabs
      ? Array.from(els.contextTabs.querySelectorAll("[data-tab]"))
      : [];
    els.contextTabSections = Array.from(
      document.querySelectorAll("[data-tab-content]")
    );

    els.conversationLog = document.getElementById("conversation-log");
    els.form = document.getElementById("portal-input-form");
    els.input = document.getElementById("portal-input");
    els.voiceToggleBtn = document.getElementById("voice-toggle-btn");
    els.sessionStatusText = document.getElementById("session-status-text");

    // AI Assistant (오른쪽 글라스 카드) 채팅 요소들
    els.assistantChatContainer = document.getElementById("chat-container");
    els.assistantInput = document.getElementById("chat-input");
    els.assistantSendBtn = document.getElementById("chat-send");
    els.assistantImageBtn = document.getElementById("chat-image-btn");
    els.assistantImageInput = document.getElementById("chat-image-input");
  }

  /* 시계 */
  function startClock() {
    if (!els.clock) return;
    const formatter = new Intl.DateTimeFormat("ko-KR", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      weekday: "short",
    });

    const tick = () => {
      const now = new Date();
      const formatted = formatter.format(now);
      els.clock.textContent = formatted;
    };

    tick();
    setInterval(tick, 1000 * 30);
  }

  /* 모드 전환 */
  function bindModeSwitch() {
    if (!els.modeSwitch) return;

    els.modeButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const mode = btn.dataset.mode;
        setMode(mode);
      });
    });
  }

  function setMode(mode) {
    state.mode = mode;

    // UI 업데이트
    els.modeButtons.forEach((btn) => {
      const isActive = btn.dataset.mode === mode;
      btn.classList.toggle("mode-btn--active", isActive);
    });

    if (els.modeHint) {
      const labelMap = {
        text: "텍스트",
        voice: "음성",
        call: "통화",
        multi: "멀티모달",
      };
      const label = labelMap[mode] ?? mode;
      els.modeHint.textContent = `현재 모드: ${label} · 이후 Gemini Live / 음성 / 통화와 연결 예정`;
    }

    if (els.sessionStatusText) {
      els.sessionStatusText.textContent = `모드: ${
        mode === "multi" ? "올인원" : mode
      } · 1인 전용 세션 · 프론트 UI 레벨`;
    }
  }

  /* 내비게이션 뷰 전환 */
  function bindNavigation() {
    els.navItems.forEach((item) => {
      item.addEventListener("click", () => {
        const view = item.dataset.view;
        setView(view);
      });
    });

    const settingsBtn = document.querySelector(
      ".nav-settings-btn[data-view='settings']"
    );
    if (settingsBtn) {
      settingsBtn.addEventListener("click", () => setView("settings"));
    }
  }

  function setView(view) {
    state.activeView = view;

    // 내비 버튼 상태
    els.navItems.forEach((item) => {
      item.classList.toggle(
        "nav-item--active",
        item.dataset.view === view
      );
    });

    // 섹션 표시
    els.viewSections.forEach((section) => {
      const id = section.id || "";
      const isActive = id === `portal-view-${view}`;
      if (section.classList.contains("portal-grid")) {
        section.style.display = isActive ? "grid" : "none";
      } else {
        section.style.display = isActive ? "block" : "none";
      }
    });
  }

  /* 컨텍스트 탭 전환 */
  function bindContextTabs() {
    if (!els.contextTabs) return;

    els.contextTabButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const tab = btn.dataset.tab;
        setContextTab(tab);
      });
    });
  }

  function setContextTab(tab) {
    els.contextTabButtons.forEach((btn) => {
      btn.classList.toggle(
        "side-tab--active",
        btn.dataset.tab === tab
      );
    });

    els.contextTabSections.forEach((section) => {
      const isActive = section.dataset.tabContent === tab;
      section.classList.toggle("side-section--hidden", !isActive);
    });
  }

  /* 대화 입력 처리 (테스트용) */
  function bindConversation() {
    if (!els.form) return;

    els.form.addEventListener("submit", (event) => {
      event.preventDefault();
      const text = (els.input.value || "").trim();
      if (!text) return;

      appendMessage({
        role: "user",
        text,
      });

      els.input.value = "";
      autosizeTextarea();

      // 여기서 이후 백엔드 연결 시:
      // - 텍스트 모드: API 호출
      // - 음성/통화 모드: 별도 핸들러
      // 지금은 프론트 테스트용 더미 응답만.
      appendMessage({
        role: "system",
        text: `지금은 포털 UI 테스트 모드야.\n나중엔 이 자리에 Gemini/부감독 라이브 응답이 들어올 거야.\n\n입력: “${text}”`,
      });
    });

    els.input.addEventListener("input", () => {
      autosizeTextarea();
    });
  }

  function appendMessage({ role, text }) {
    if (!els.conversationLog) return;

    const row = document.createElement("div");
    row.className = `message-row ${
      role === "user" ? "message-row--user" : "message-row--system"
    }`;

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    const meta = document.createElement("div");
    meta.className = "message-meta";

    const roleSpan = document.createElement("span");
    roleSpan.className = "message-role";
    roleSpan.textContent = role === "user" ? "소원" : "부감독";

    const timeSpan = document.createElement("span");
    timeSpan.className = "message-time";
    timeSpan.textContent = "지금";

    meta.appendChild(roleSpan);
    meta.appendChild(timeSpan);

    const textP = document.createElement("p");
    textP.className = "message-text";
    textP.textContent = text;

    bubble.appendChild(meta);
    bubble.appendChild(textP);
    row.appendChild(bubble);

    els.conversationLog.appendChild(row);
    els.conversationLog.scrollTop = els.conversationLog.scrollHeight;
  }

  function autosizeTextarea() {
    if (!els.input) return;
    els.input.style.height = "auto";
    const maxHeight = 120;
    const newHeight = Math.min(els.input.scrollHeight, maxHeight);
    els.input.style.height = `${newHeight}px`;
  }

  /* 음성 토글 (UI 상태만) */
  function bindVoiceToggle() {
    if (!els.voiceToggleBtn) return;

    els.voiceToggleBtn.addEventListener("click", () => {
      const active = els.voiceToggleBtn.classList.toggle("icon-btn--active");
      // 실제 마이크 제어는 나중에
      const label = active ? "음성 대기 중" : "음성 비활성화";
      els.voiceToggleBtn.title = label;
    });
  }

  /* Director 서버 헬스 체크 (세션 상태 표시) */
  function startHealthCheck() {
    const el = els.sessionStatusText;
    if (!el) return;

    async function update() {
      try {
        const res = await fetch("http://localhost:8000/health");
        if (!res.ok) throw new Error("bad status");

        // Online
        el.textContent = "Director · Online · 로컬 서버 연결됨";
        el.classList.add("status-online");
        el.classList.remove("status-offline");
      } catch (err) {
        console.error("[Portal] health check failed:", err);
        // Offline
        el.textContent = "Director · Offline · 서버 꺼져 있거나 연결 안 됨";
        el.classList.add("status-offline");
        el.classList.remove("status-online");
      }
    }

    update();                  // 첫 실행
    setInterval(update, 10000); // 10초 주기 체크
  }

  /* AI Assistant 채팅: Director 서버와 연결 */
  function scrollAssistantChatToBottom() {
    if (!els.assistantChatContainer) return;
    els.assistantChatContainer.scrollTop = els.assistantChatContainer.scrollHeight;
  }

  function addAssistantTextBubble(role, text) {
    if (!els.assistantChatContainer) return;
    const row = document.createElement("div");
    row.classList.add("chat-row", role === "me" ? "me" : "ai");

    const author = document.createElement("div");
    author.classList.add("chat-author-inline", role === "me" ? "me" : "ai");
    author.textContent = role === "me" ? "Sowon" : "Director";

    const bubble = document.createElement("div");
    bubble.classList.add("chat-bubble", role === "me" ? "me" : "ai");
    bubble.textContent = text;

    const metaLine = document.createElement("div");
    metaLine.classList.add("chat-meta-line", role === "me" ? "me" : "ai");

    const meta = document.createElement("span");
    meta.classList.add("chat-meta");
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, "0");
    const mm = String(now.getMinutes()).padStart(2, "0");
    meta.textContent = `오늘 · ${hh}:${mm}`;

    metaLine.appendChild(meta);

    row.appendChild(author);
    row.appendChild(bubble);
    row.appendChild(metaLine);

    els.assistantChatContainer.appendChild(row);
    scrollAssistantChatToBottom();
  }

  function addAssistantImageBubble(role, imageUrl) {
    if (!els.assistantChatContainer) return;
    const row = document.createElement("div");
    row.classList.add("chat-row", role === "me" ? "me" : "ai");

    const author = document.createElement("div");
    author.classList.add("chat-author-inline", role === "me" ? "me" : "ai");
    author.textContent = role === "me" ? "Sowon" : "Director";

    const bubble = document.createElement("div");
    bubble.classList.add("chat-bubble", role === "me" ? "me" : "ai");

    const media = document.createElement("div");
    media.classList.add("media-attachment");
    const img = document.createElement("img");
    img.src = imageUrl;
    img.alt = "첨부 이미지";
    media.appendChild(img);

    bubble.appendChild(media);

    const metaLine = document.createElement("div");
    metaLine.classList.add("chat-meta-line", role === "me" ? "me" : "ai");

    const meta = document.createElement("span");
    meta.classList.add("chat-meta");
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, "0");
    const mm = String(now.getMinutes()).padStart(2, "0");
    meta.textContent = `오늘 · ${hh}:${mm}`;

    metaLine.appendChild(meta);

    row.appendChild(author);
    row.appendChild(bubble);
    row.appendChild(metaLine);

    els.assistantChatContainer.appendChild(row);
    scrollAssistantChatToBottom();
  }

  async function sendTextToDirector(text) {
    console.log("[Portal] Sending text to director:", text);
    try {
      const res = await fetch("http://localhost:8000/director/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: "chat",
          text,
          user_id: "sowon",
        }),
      });

      console.log("[Portal] Director text response status:", res.status);

      if (!res.ok) {
        return "부감독 서버에서 에러 응답이 온 것 같아. 터미널 로그를 한번 확인해줘.";
      }

      const data = await res.json();
      console.log("[Portal] Director text response JSON:", data);

      if (data && typeof data.reply === "string") {
        return data.reply;
      }
      return "텍스트 응답 형식이 예상과 달라. 나중에 로그를 확인해보자.";
    } catch (err) {
      console.error("[Portal] Director text request failed:", err);
      return "부감독 서버에 연결이 안 돼. 서버 주소나 상태를 확인해줘.";
    }
  }

  async function sendImageToDirector(file) {
    if (!file) return "전달할 이미지 파일이 없어요.";
    console.log("[Portal] Sending image to director:", file.name);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("user_id", "sowon");

    try {
      const res = await fetch("http://localhost:8000/director/vision", {
        method: "POST",
        body: formData,
      });

      console.log("[Portal] Director image response status:", res.status);

      if (!res.ok) {
        return "이미지 분석 중 서버 응답에 문제가 있어. 터미널 로그를 한번 확인해줘.";
      }

      const data = await res.json();
      console.log("[Portal] Director image response JSON:", data);

      if (data && typeof data.reply === "string") {
        return data.reply;
      }
      if (data && typeof data.summary === "string") {
        return data.summary;
      }
      return "이미지 분석은 끝났는데, 응답 형식이 예상과 조금 달라. 나중에 로그를 확인해보자.";
    } catch (err) {
      console.error("[Portal] Director image request failed:", err);
      return "이미지 분석 서버에 연결이 안 돼. 서버 주소나 상태를 확인해줘.";
    }
  }

  function bindAssistantChat() {
    // 텍스트 전송
    if (els.assistantSendBtn && els.assistantInput) {
      const handleSend = async () => {
        const text = (els.assistantInput.value || "").trim();
        if (!text) return;
        addAssistantTextBubble("me", text);
        els.assistantInput.value = "";
        const reply = await sendTextToDirector(text);
        addAssistantTextBubble("ai", reply);
      };

      els.assistantSendBtn.addEventListener("click", (e) => {
        e.preventDefault();
        handleSend();
      });

      els.assistantInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.isComposing) {
          e.preventDefault();
          handleSend();
        }
      });
    }

    // 이미지 전송
    if (els.assistantImageBtn && els.assistantImageInput) {
      els.assistantImageBtn.addEventListener("click", (e) => {
        e.preventDefault();
        els.assistantImageInput.click();
      });

      els.assistantImageInput.addEventListener("change", async (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) return;
        const objectUrl = URL.createObjectURL(file);
        addAssistantImageBubble("me", objectUrl);
        const reply = await sendImageToDirector(file);
        addAssistantTextBubble("ai", reply);
        setTimeout(() => URL.revokeObjectURL(objectUrl), 60 * 1000);
      });
    }
  }

  /* 초기화 */
  function init() {
    cacheElements();
    startClock();
    bindModeSwitch();
    bindNavigation();
    bindContextTabs();
    bindConversation();
    bindVoiceToggle();
    startHealthCheck();
    bindAssistantChat();

    // 기본 상태
    setMode(state.mode);
    setView(state.activeView);
    setContextTab("now");
    autosizeTextarea();
  }

  return {
    init,
    getState: () => ({ ...state }),
  };
})();

document.addEventListener("DOMContentLoaded", () => {
  PortalApp.init();
});