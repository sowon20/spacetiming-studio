document.addEventListener("DOMContentLoaded", () => {
  // ==========================
  // 상단 상태판 (까만 박스)
  // ==========================
  const statusPill = document.getElementById("studioStatusPill");
  const statusText = document.getElementById("studioStatusText");
  const serverSummary = document.getElementById("serverSummary");
  const nowStatusText = document.getElementById("nowStatusText");
  const loadPercent = document.getElementById("loadPercent");
  const loadBarFill = document.getElementById("loadBarFill");

  function setStudioStatus(label, mode, summary) {
    if (!statusPill || !statusText) return;
    statusText.textContent = label;
    statusPill.classList.remove("online", "offline", "issue");
    if (mode) statusPill.classList.add(mode);
    if (serverSummary && summary) {
      serverSummary.textContent = summary;
    }
  }

  async function pingStudioStatus() {
    try {
      const res = await fetch("https://sowon.mooo.com/director/health", {
        method: "GET",
      });
      if (!res.ok) {
        setStudioStatus("ISSUE", "issue", "응답 지연");
        if (nowStatusText) {
          nowStatusText.textContent = "health는 응답했지만 상태 코드가 이상해.";
        }
        return;
      }
      const data = await res.json().catch(() => ({}));
      const llmAvailable = !!data.llm_available;

      setStudioStatus(
        llmAvailable ? "ONLINE" : "IDLE",
        llmAvailable ? "online" : "issue",
        llmAvailable ? "Gemini · Ready" : "LLM 대기 중"
      );

      if (nowStatusText) {
        nowStatusText.textContent = llmAvailable
          ? "부감독이 바로 대답할 수 있는 상태야."
          : "LLM 준비가 덜 된 것 같아도, 규칙 기반으로는 대답할 수 있어.";
      }

      if (loadPercent && loadBarFill) {
        const p = llmAvailable ? 82 : 38;
        loadPercent.textContent = `${p}%`;
        loadBarFill.style.width = `${p}%`;
      }
    } catch (e) {
      console.error(e);
      setStudioStatus("OFFLINE", "offline", "연결 없음");
      if (nowStatusText) {
        nowStatusText.textContent = "sowon.mooo.com/health에 연결하지 못했어.";
      }
      if (loadPercent && loadBarFill) {
        loadPercent.textContent = "0%";
        loadBarFill.style.width = "0%";
      }
    }
  }

  pingStudioStatus();
  setInterval(pingStudioStatus, 30000);

  // ==========================
  // 오른쪽 레일 탭 (지금은 chat만 실제 사용)
  // ==========================
  const railButtons = document.querySelectorAll(".st-rail-btn");
  const chatView = document.getElementById("view-chat");

  railButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      railButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      const tab = btn.getAttribute("data-tab");
      if (tab === "chat") {
        if (chatView) chatView.style.display = "flex";
      } else {
        // 메모 탭 등은 아직 준비 안 됨 → 나중에 확장용
        if (chatView) chatView.style.display = "flex";
      }
    });
  });

  // ==========================
  // 채팅 로직 (챗GPT 스타일)
  // ==========================
  const chatLog = document.getElementById("chatLog");
  const chatForm = document.getElementById("chatForm");
  const chatInput = document.getElementById("chatInput");
  const chatSendButton = document.getElementById("chatSendButton");
  const chatHint = document.getElementById("chatHint");

  const DIRECTOR_API_URL = "https://sowon.mooo.com/director/analyze";

  function appendMessage(role, text, options = {}) {
    if (!chatLog) return;

    const msg = document.createElement("div");
    msg.className = `st-chat-message ${role}`;
    if (options.typing) {
      msg.classList.add("typing");
    }

    if (role === "assistant") {
      const avatar = document.createElement("div");
      avatar.className = "st-chat-avatar";
      avatar.textContent = "부";
      msg.appendChild(avatar);
    }

    const bubble = document.createElement("div");
    bubble.className = "st-chat-bubble";

    if (options.typing) {
      const dotWrap = document.createElement("div");
      dotWrap.style.display = "inline-flex";
      dotWrap.style.gap = "4px";
      ["", "", ""].forEach(() => {
        const d = document.createElement("div");
        d.className = "st-typing-dot";
        dotWrap.appendChild(d);
      });
      bubble.appendChild(dotWrap);
    } else {
      const name = document.createElement("div");
      name.className = "st-chat-name";
      name.textContent = role === "user" ? "소원" : "부감독";

      const body = document.createElement("div");
      body.className = "st-chat-text";
      body.textContent = text || "";

      const meta = document.createElement("div");
      meta.className = "st-chat-meta";
      meta.textContent = options.meta || "";

      bubble.appendChild(name);
      bubble.appendChild(body);
      bubble.appendChild(meta);
    }

    msg.appendChild(bubble);
    chatLog.appendChild(msg);
    chatLog.scrollTop = chatLog.scrollHeight;

    return msg;
  }

  function setSendingState(isSending) {
    if (chatSendButton) {
      chatSendButton.disabled = isSending;
    }
    if (chatInput) {
      chatInput.disabled = isSending;
    }
    if (chatHint) {
      chatHint.textContent = isSending
        ? "부감독이 대답을 정리하는 중이야…"
        : "Enter로 보내고, Shift+Enter로 줄바꿈할 수 있어.";
    }
  }

  async function sendToDirector(text) {
    const payload = {
      mode: "chat",
      text,
      user_id: "sowon",
      source: "chrome_sidebar",
    };

    try {
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
      // AnalyzeResponse.reply 기준 (백엔드와 맞춰놨다고 가정)
      const replyText = data.reply || data.ai_text || "(응답은 왔지만, 내용이 비어 있어.)";
      return replyText;
    } catch (err) {
      console.error(err);
      return (
        "지금은 부감독 서버에 바로 연결이 잘 안 되는 것 같아.\n" +
        "조금 있다가 다시 시도해보거나, 웹 포털에서 한 번 더 시도해줘."
      );
    }
  }

  if (chatForm && chatInput) {
    chatForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const text = chatInput.value.trim();
      if (!text) return;

      // 유저 메시지 추가
      appendMessage("user", text, { meta: "지금" });
      chatInput.value = "";
      chatInput.style.height = "auto";

      // 타이핑 표시
      setSendingState(true);
      const typingMsg = appendMessage("assistant", "", { typing: true });

      // 백엔드 호출
      const reply = await sendToDirector(text);

      // 타이핑 제거
      if (typingMsg && typingMsg.parentNode) {
        typingMsg.parentNode.removeChild(typingMsg);
      }

      appendMessage("assistant", reply, { meta: "곧 방금" });
      setSendingState(false);
    });

    // textarea 자동 높이 조절 + Enter/Shift+Enter 처리
    chatInput.addEventListener("input", () => {
      chatInput.style.height = "auto";
      const max = 80;
      chatInput.style.height = Math.min(chatInput.scrollHeight, max) + "px";
    });

    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
      }
    });
  }
});