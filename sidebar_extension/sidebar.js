document.addEventListener("DOMContentLoaded", () => {
  // ==========================
  // 탭 전환
  // ==========================
  const tabButtons = document.querySelectorAll(".tab-button");
  const views = document.querySelectorAll(".view");

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const viewName = btn.getAttribute("data-view");

      tabButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      if (!views || views.length === 0) return;

      views.forEach((v) => {
        const expectedId = viewName ? `view-${viewName}` : null;
        if (expectedId && v.id === expectedId) {
          v.classList.add("active");
        } else {
          v.classList.remove("active");
        }
      });
    });
  });

  // ==========================
  // 대시보드 더미 데이터 (나중에 API로 교체)
  // ==========================
  const currentTitleEl = document.getElementById("currentTitle");
  const currentDateEl = document.getElementById("currentDate");
  const currentStageEl = document.getElementById("currentStage");
  const currentProgressTextEl = document.getElementById("currentProgressText");
  const currentProgressFillEl = document.getElementById("currentProgressFill");
  const currentLoglineEl = document.getElementById("currentLogline");
  const upcomingListEl = document.getElementById("upcomingList");

  const demoProjects = [
    {
      id: 1,
      title: "몽환적인 우주 냉장고",
      date: "2025-12-07",
      dateLabel: "12월 7일 (토) 22:00",
      logline: "냉장고 안 얼음 소리로 우주의 시간을 보여주는 5분짜리 영상.",
      stage: "프롬프트 정리 완료",
      stageKey: "prompting",
      progress: 45,
      emoji: "🧊",
      thumbnailUrl: "https://img.youtube.com/vi/AG3iz3xPQXE/hqdefault.jpg",
    },
    {
      id: 2,
      title: "창문 밖, 다른 시간대의 지구",
      date: "2025-12-14",
      dateLabel: "12월 14일 (토) 22:00",
      logline: "창문 밖 풍경이 시간대마다 다른 지구의 모습을 보여주는 영상.",
      stage: "아이디어 스케치",
      stageKey: "planning",
      progress: 15,
      emoji: "🪟",
      thumbnailUrl: "https://img.youtube.com/vi/1S7__LzfOUw/hqdefault.jpg",
    },
    {
      id: 3,
      title: "방 안에 떨어진 작은 운석",
      date: "2025-12-21",
      dateLabel: "12월 21일 (토) 22:00",
      logline: "책상 위 작은 돌이 사실 오래된 운석이라는 걸 알아차리는 순간.",
      stage: "대기",
      stageKey: "queued",
      progress: 0,
      emoji: "☄️",
      thumbnailUrl: null,
    },
  ];

  function initDashboard(projects) {
    if (!projects || projects.length === 0) {
      return;
    }

    const current = projects[0];

    if (
      currentTitleEl &&
      currentDateEl &&
      currentStageEl &&
      currentProgressTextEl &&
      currentProgressFillEl &&
      currentLoglineEl
    ) {
      currentTitleEl.textContent = current.title;
      currentDateEl.textContent = current.dateLabel;
      currentStageEl.textContent = current.stage;
      currentProgressTextEl.textContent = `${current.progress}%`;
      currentProgressFillEl.style.width = `${current.progress}%`;
      currentLoglineEl.textContent = current.logline;
    }

    if (!upcomingListEl) return;

    upcomingListEl.innerHTML = "";

    projects.slice(0, 3).forEach((p) => {
      const item = document.createElement("div");
      item.className = "upcoming-item";

      const thumbHtml = p.thumbnailUrl
        ? `<div class="thumb thumb-image"><img src="${p.thumbnailUrl}" alt="${p.title}" /></div>`
        : `<div class="thumb">${p.emoji || "🎬"}</div>`;

      item.innerHTML = `
        ${thumbHtml}
        <div class="upcoming-main">
          <div class="upcoming-title">${p.title}</div>
          <div class="upcoming-meta">
            <span>${p.dateLabel}</span>
            <span>${p.stage}</span>
          </div>
          <div class="upcoming-logline">${p.logline}</div>
        </div>
      `;

      upcomingListEl.appendChild(item);
    });
  }

  initDashboard(demoProjects);

  // ==========================
  // Prompt Lab (프롬프트 / Flow 제어)
  // ==========================
  const ideaInput = document.getElementById("ideaInput");
  const btnGeneratePrompt = document.getElementById("btnGeneratePrompt");
  const btnRunFlow = document.getElementById("btnRunFlow");
  const btnCopyMain = document.getElementById("btnCopyMain");

  const titleOutput = document.getElementById("titleOutput");
  const mainPromptOutput = document.getElementById("mainPromptOutput");
  const teaserPromptOutput = document.getElementById("teaserPromptOutput");
  const statusBar = document.getElementById("statusBar");
  const statusText = document.getElementById("statusText");
  const statusDot = statusBar ? statusBar.querySelector(".status-dot") : null;

  let lastPayload = null; // Flow로 넘길 최신 프롬프트 세트
  let lastEpisodeId = null; // 최근 생성된 에피소드 ID (피드백용)

  function setStatus(mode, text) {
    if (statusText) {
      statusText.textContent = text || "";
    }

    if (!statusDot) return;

    statusDot.classList.remove("idle", "ok", "error");
    if (mode === "ok") statusDot.classList.add("ok");
    else if (mode === "error") statusDot.classList.add("error");
    else statusDot.classList.add("idle");
  }

  async function generatePrompt() {
    if (!ideaInput) return;

    const idea = ideaInput.value.trim();
    if (!idea) {
      setStatus("error", "아이디어를 한 줄이라도 적어줘.");
      return;
    }

    if (btnGeneratePrompt) {
      btnGeneratePrompt.disabled = true;
    }
    if (btnRunFlow) {
      btnRunFlow.disabled = true;
    }

    setStatus("idle", "부감독이 기획 정리 중…");

    const roughTitle = idea.split("\n")[0].slice(0, 40) || "Untitled";

    try {
      const res = await fetch("http://127.0.0.1:8899/veo/prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: roughTitle,
          plan: idea,
        }),
      });

      const data = await res.json();

      if (!data.ok) {
        setStatus("error", data.error || "프롬프트 생성 중 오류가 났어.");
        if (btnGeneratePrompt) btnGeneratePrompt.disabled = false;
        if (btnRunFlow) btnRunFlow.disabled = false;
        return;
      }

      const main = data.main_prompt || "";
      const teaser = data.teaser_prompt || "";
      const finalTitle = data.title || roughTitle;

      if (titleOutput) {
        titleOutput.textContent = finalTitle;
        titleOutput.classList.remove("muted");
      }
      if (mainPromptOutput) {
        mainPromptOutput.textContent = main;
        mainPromptOutput.classList.remove("muted");
      }
      if (teaserPromptOutput) {
        teaserPromptOutput.textContent = teaser;
        teaserPromptOutput.classList.remove("muted");
      }

      lastEpisodeId = data.episode_id || null;

      lastPayload = {
        episode_id: lastEpisodeId,
        title: finalTitle,
        main_prompt: main,
        teaser_prompt: teaser,
        plan: idea,
      };

      setStatus("ok", "프롬프트 준비 완료. Flow로 보낼 수 있어.");

      if (btnGeneratePrompt) btnGeneratePrompt.disabled = false;
      if (btnRunFlow) btnRunFlow.disabled = false;
    } catch (err) {
      console.error(err);
      setStatus("error", "부감독 서버(8899)에 연결하지 못했어.");
      if (btnGeneratePrompt) btnGeneratePrompt.disabled = false;
      if (btnRunFlow) btnRunFlow.disabled = false;
    }
  }

  async function runFlow() {
    if (!lastPayload) {
      setStatus("error", "먼저 프롬프트를 한 번 생성해줘.");
      return;
    }

    if (btnRunFlow) btnRunFlow.disabled = true;

    setStatus("idle", "Flow에 프롬프트 전달 중…");

    try {
      const res = await fetch("http://127.0.0.1:8898/flow/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(lastPayload),
      });

      const data = await res.json();

      if (!data.ok) {
        setStatus("error", data.error || "Flow 자동 실행 중 오류가 났어.");
        if (btnRunFlow) btnRunFlow.disabled = false;
        return;
      }

      setStatus("ok", "Flow 브라우저 탭에 프롬프트 전달 완료!");
      if (btnRunFlow) btnRunFlow.disabled = false;
    } catch (err) {
      console.error(err);
      setStatus("error", "Flow 서버(8898)에 연결하지 못했어.");
      if (btnRunFlow) btnRunFlow.disabled = false;
    }
  }

  function copyMainPrompt() {
    if (!mainPromptOutput) return;

    const text = mainPromptOutput.textContent.trim();
    if (!text) {
      setStatus("error", "복사할 메인 프롬프트가 아직 없어.");
      return;
    }

    navigator.clipboard
      .writeText(text)
      .then(() => {
        setStatus("ok", "메인 프롬프트를 클립보드에 복사했어.");
      })
      .catch((err) => {
        console.error(err);
        setStatus("error", "클립보드 복사에 실패했어.");
      });
  }

  async function sendFeedback(verdict) {
    if (!lastEpisodeId) {
      setStatus("error", "먼저 프롬프트를 생성해서 에피소드를 만들어야 해.");
      return;
    }
  
    const labels = {
      approved: "합격",
      revise: "수정",
      discard: "폐기",
    };
  
    const note = window.prompt("감독 메모 (선택 입력 가능):") || "";
  
    setStatus("idle", `${labels[verdict] || "피드백"} 저장 중…`);
  
    try {
      const res = await fetch("http://127.0.0.1:8899/veo/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          episode_id: lastEpisodeId,
          verdict,
          note: note || undefined,
        }),
      });
  
      const data = await res.json();
  
      if (!data.ok) {
        setStatus("error", data.error || "피드백 저장 중 오류가 났어.");
        return;
      }
  
      setStatus("ok", `피드백이 저장됐어. (${labels[verdict] || verdict})`);
    } catch (err) {
      console.error(err);
      setStatus("error", "피드백 API 서버(8899)에 연결하지 못했어.");
    }
  }
  
  const btnApprove = document.querySelector(".fb-approve");
  const btnRevise = document.querySelector(".fb-revise");
  const btnDiscard = document.querySelector(".fb-discard");
  
  if (btnApprove) {
    btnApprove.addEventListener("click", () => sendFeedback("approved"));
  }
  if (btnRevise) {
    btnRevise.addEventListener("click", () => sendFeedback("revise"));
  }
  if (btnDiscard) {
    btnDiscard.addEventListener("click", () => sendFeedback("discard"));
  }

  if (btnGeneratePrompt) {
    btnGeneratePrompt.addEventListener("click", generatePrompt);
  }
  if (btnRunFlow) {
    btnRunFlow.addEventListener("click", runFlow);
  }
  if (btnCopyMain) {
    btnCopyMain.addEventListener("click", copyMainPrompt);
  }
});