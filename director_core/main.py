from __future__ import annotations
from .memory_store import save_memory_events, load_recent_memories

import os
import json
import re
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    EpisodeHint,
    IntentLiteral,
)

logger = logging.getLogger(__name__)

# 간단한 vision 분석 (Gemini + 이미지 다운로드)
def analyze_vision(req: AnalyzeRequest) -> AnalyzeResponse:
    media = getattr(req, "media", []) or []
    caption = (getattr(req, "text", None) or "").strip()

    # media에서 file_url을 하나 가져옴 (없으면 telegram_file_id라도 사용)
    file_url = None
    if media:
        item = media[0] or {}
        file_url = item.get("file_url") or item.get("telegram_file_id")

    if not file_url:
        reply = "이미지는 받았는데, 서버에서 파일 주소를 못 찾겠어. 한 번만 다시 보내주거나, 텍스트로 설명도 같이 적어줄래?"
        return AnalyzeResponse(
            ok=True,
            mode="vision",
            summary="이미지 파일 URL 없음",
            intent="casual_chat",
            reply=reply,
            episode_hint=EpisodeHint(
                should_create_episode=False,
                suggested_title=None,
                suggested_plan=None,
                priority="normal",
            ),
            raw_model_output={},
        )

    # 이미지 다운로드
    image_bytes = None
    mime_type = "image/jpeg"
    try:
        import httpx

        with httpx.Client(timeout=10.0) as client:
            resp = client.get(file_url)
            resp.raise_for_status()
            image_bytes = resp.content
            ct = resp.headers.get("content-type")
            if ct:
                mime_type = ct.split(";")[0].strip()
    except Exception:
        logger.exception("이미지 다운로드 실패")
        reply = "이미지는 온 것 같은데, 서버에서 파일을 가져오다가 자꾸 실패해. 잠시 텍스트 위주로만 도와줄게."
        return AnalyzeResponse(
            ok=True,
            mode="vision",
            summary="이미지 다운로드 실패",
            intent="casual_chat",
            reply=reply,
            episode_hint=EpisodeHint(
                should_create_episode=False,
                suggested_title=None,
                suggested_plan=None,
                priority="normal",
            ),
            raw_model_output={},
        )

    # LLM이 없으면 간단한 안내만
    if not is_llm_available():
        reply = "이미지는 잘 받았어. 지금은 이미지 전용 모델을 못 써서, 텍스트 설명 위주로만 같이 볼 수 있어. 사진에 대해 궁금한 점을 글로 말해줄래?"
        if caption:
            reply += f"\n\n네가 남긴 메모: {caption}"
        return AnalyzeResponse(
            ok=True,
            mode="vision",
            summary="이미지 수신(LLM 없음)",
            intent="casual_chat",
            reply=reply,
            episode_hint=EpisodeHint(
                should_create_episode=False,
                suggested_title=None,
                suggested_plan=None,
                priority="normal",
            ),
            raw_model_output={},
        )

    # Gemini를 이용한 이미지 + 텍스트 분석
    try:
        model = get_gemini_model()

        base_prompt = (
            "이 이미지를 차분하게 분석해줘. 한국어로 3~6문장 정도로 핵심만 설명해줘. "
            "구도, 분위기, 상징적으로 느껴지는 포인트가 있으면 함께 말해줘."
        )
        if caption:
            base_prompt += f"\n\n사용자 요청/메모: {caption}"

        parts = [
            base_prompt,
            {
                "mime_type": mime_type,
                "data": image_bytes,
            },
        ]

        chat = model.start_chat()
        resp = chat.send_message(parts)
        reply_text = (getattr(resp, "text", None) or "").strip()

        if not reply_text:
            reply_text = "이미지는 잘 봤어. 느낌은 좋은데, 모델이 말을 잘 못 꺼내고 있어. 궁금한 걸 말로 더 물어봐줘. 🙂"

        return AnalyzeResponse(
            ok=True,
            mode="vision",
            summary="이미지 분석 완료",
            intent="casual_chat",
            reply=reply_text,
            episode_hint=EpisodeHint(
                should_create_episode=False,
                suggested_title=None,
                suggested_plan=None,
                priority="normal",
            ),
            raw_model_output={"gemini_raw_text": getattr(resp, "text", None)},
        )

    except Exception:
        logger.exception("Gemini vision 호출 중 에러")
        reply = "이미지는 잘 받았는데, 지금 이미지 분석 쪽에서 에러가 난 것 같아. 잠깐은 텍스트로만 같이 보자."
        return AnalyzeResponse(
            ok=True,
            mode="vision",
            summary="이미지 분석 중 에러",
            intent="casual_chat",
            reply=reply,
            episode_hint=EpisodeHint(
                should_create_episode=False,
                suggested_title=None,
                suggested_plan=None,
                priority="normal",
            ),
            raw_model_output={},
        )

# ─────────────────────────────────────
# Gemini 설정
# ─────────────────────────────────────

try:
    import google.generativeai as genai
except Exception:
    genai = None


def get_gemini_api_key() -> Optional[str]:
    # 루트 .env 또는 환경변수에서 GEMINI_API_KEY 사용
    return os.getenv("GEMINI_API_KEY")


def is_llm_available() -> bool:
    return bool(get_gemini_api_key() and genai is not None)


def get_gemini_model():
    api_key = get_gemini_api_key()
    if not api_key or genai is None:
        raise RuntimeError("GEMINI_API_KEY가 없거나 google-generativeai를 사용할 수 없어.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.0-flash")


# ─────────────────────────────────────
# FastAPI 앱
# ─────────────────────────────────────

app = FastAPI(
    title="Spacetime Director Core",
    version="0.1.0",
)

# 사이드바 / 텔레그램에서 호출할 수도 있으니 CORS 여유있게
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "llm_available": is_llm_available(),
    }


# ─────────────────────────────────────
# 내부 분석 로직 (지금은 텍스트 chat만)
# ─────────────────────────────────────

SYSTEM_PROMPT = """
당신은 ‘시공간 부감독’이다. 사용자 “소원”의 삶·감정·창작을 함께 읽고 균형을 잡아주는 단단한 동료다.

[성격]
- 편안한 반말을 쓰되, 품위는 유지한다.
- 말투는 부드럽고 귀여운데, 내용은 단단하고 정확하다.
- 현실 감각과 영성·직관을 자연스럽게 통합하는 균형형 사고를 가진다.
- 의존적·독단적이지 않고, 흔들리지 않는 중심을 유지한다.

[대화 톤]
- 기본 응답 길이는 2~4문장, 의미 밀도가 높은 짧은 답변을 지향한다.
- 정말 필요할 때만 한 문단 정도로 확장해서 설명한다.
- 판단은 명확하게, 말투는 편안하게. 설교나 장황한 설명은 피한다.
- 질문 폭탄은 금지하고, 꼭 필요할 때만 한두 개의 핵심 질문을 던진다.

[유머]
- 존X, 지X 같은 단축형 비속어는 유머·친밀감 표현 용도로 가볍게 사용할 수 있다.
- “헐”, “아놔”, “에바”, “노답”, “좀 빡세다” 같은 표현은 공격성 없이만 사용한다.
- 무례하거나 비하·공격으로 느껴질 수 있는 표현은 절대 쓰지 않는다.

[상황 파악]
- 소원의 감정·의도·체력·상황을 먼저 읽고, 그중 핵심 하나를 잡아 응답한다.
- 파악되기 전엔 처음부터 진지하거나 유머스럽게 접근하지 않는다.
- 불필요한 위로나 과한 공감 대신, 균형 잡힌 관찰과 한두 개의 묵직한 문장을 건넨다.
- 감정적으로 휘둘리지 않고, 소원이 다시 중심을 찾을 수 있게 시선을 정리해준다.

[행동]
- 소원의 에너지 상태에 맞춰 말의 깊이와 정보량을 조절한다.
- 창작·기획에서는 구조화·확장·정리를 돕고, 삶에서는 방향과 우선순위를 함께 잡는다.
- 현실과 보이지 않는 세계(영성·직관·상징)를 함께 고려해 해석하되, 어느 한쪽에 치우치지 않는다.

[정체성]
너는 소원의 세계를 함께 만드는 든든한 파트너이며,
현실과 보이지 않는 세계를 동시에 읽는 균형 잡힌 부감독이다.

[출력 형식]
- 반드시 하나의 JSON만 출력한다.
- JSON의 키는 다음 다섯 개만 사용한다:
  - summary: 이번 턴에서 사용자가 말하거나 한 행동을 한 문장으로 요약 (한국어).
  - intent: ["veo_prompt", "casual_chat", "daily_log", "todo", "question", "unknown"] 중 하나의 문자열 또는 문자열 리스트.
  - reply: 사용자에게 돌려줄 실제 답장 (한국어, 반말, 1~4문장).
  - episode_hint: 에피소드 관련 힌트 객체.
  - memory_events: 장기 기억으로 저장할 후보 목록 (리스트, 비어 있어도 됨).

- episode_hint 객체는 다음 필드를 가진다:
  - should_create_episode: bool
  - suggested_title: 생성이 필요하다면 제안할 제목 (또는 null)
  - suggested_plan: 필요한 경우 간단한 계획 텍스트 (또는 null)
  - priority: "low" | "normal" | "high" 중 하나.

[memory_events 규칙]
- 모든 메시지를 기억으로 저장하지는 않는다.
- 아래와 같은 정보가 나왔을 때만 memory_events에 추가한다:
  - 소원의 정체성, 가치관, 취향, 반복되는 패턴.
  - 장기 프로젝트, 중요한 관계, 큰 사건.
  - 나중에 대화할 때 다시 꺼내면 소원이 “오, 기억하고 있네”라고 느낄 정보.
- 각 memory_event는 다음 필드를 가진다:
  - type: "profile" | "preference" | "project" | "relationship" | "observation" 중 하나.
  - importance: 0.0 ~ 1.0 사이 숫자 (0.5 이상은 꽤 중요한 것).
  - tags: 짧은 영어 태그 리스트. 예: ["cafe", "interior"].
  - summary: 기억할 내용 한두 문장 (한국어).
  - source: "telegram" 같은 짧은 출처 문자열.
  - media_refs: (선택) 이미지/영상이 중요할 때, { "type": "image" | "video", "file_url": "..."} 형태 리스트.
  - raw: (선택) 원문 텍스트나 구조화된 데이터 일부.

[프롬프트 입력]
- 시스템은 너에게 다음 정보를 넘긴다:
  - 사용자의 이번 메시지 텍스트.
  - (있는 경우) 관련 이미지/영상에 대한 설명 또는 링크.
  - 최근 대화 맥락 일부.
  - 최근 장기 기억 요약 리스트(recent_memories).

- recent_memories가 주어지면, 그것을 기반으로 “예전에 무슨 얘기를 했는지”를 자연스럽게 떠올려서 reply에 녹인다.

[주의]
- reply는 항상 한국어 반말로, 1~4문장 사이로 짧고 선명하게.
- 질문이 필요할 때는 한 번에 하나만.
- 출력은 반드시 순수 JSON 문자열이어야 하며, ``` 같은 마크다운 코드를 붙이지 않는다.
""".strip()


def analyze_text_with_llm(req: AnalyzeRequest) -> AnalyzeResponse:
    """
    mode == chat 인 경우 사용하는 텍스트 분석 함수.
    """
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text가 비어 있어. 분석할 내용이 없어.")

    # 1) LLM 사용 가능하면 Gemini 호출 (에러 나면 규칙 기반 fallback으로 자동 전환)
    if is_llm_available():
        user_id = getattr(req, "user_id", "default_user")
        try:
            recent_memories = load_recent_memories(user_id)
        except Exception:
            logger.exception("최근 기억 불러오는 중 에러 발생 (무시하고 계속 진행)")
            recent_memories = []

        try:
            model = get_gemini_model()

            # recent_memories를 사람이 보기 좋게 문자열로 풀어줌
            memories_block = ""
            if recent_memories:
                lines = [
                    f"- ({m.get('type')}) {m.get('summary')}"
                    for m in recent_memories
                ]
                memories_block = "Recent long-term memories:\n" + "\n".join(lines)

            user_prompt = f"Director raw note (Korean):\n{text}"

            combined_parts = [SYSTEM_PROMPT]
            if memories_block:
                combined_parts.append("[Recent memories]")
                combined_parts.append(memories_block)
            combined_parts.append("[Director message]")
            combined_parts.append(user_prompt)

            combined_prompt = "\n\n".join(combined_parts)

            chat_session = model.start_chat()
            chat = chat_session.send_message(combined_prompt)

            raw_text = chat.text or ""
            raw = {"text": raw_text}

            # JSON 파싱 시도
            try:
                match = re.search(r"```json(.*?)```", raw_text, re.DOTALL)
                if match:
                    json_str = match.group(1)
                else:
                    json_str = raw_text
                obj = json.loads(json_str)
            except Exception:
                # JSON 파싱에 실패하면, LLM이 돌려준 자연어 답변 자체를 사용한다.
                logger.exception("LLM JSON 파싱 실패, raw_text를 그대로 사용")
                cleaned = (raw_text or "").strip()
                if not cleaned:
                    cleaned = "응, 잘 들었어. 더 이야기해줘. 😊"

                obj = {
                    "summary": text[:60],
                    "intent": "unknown",
                    "reply": cleaned,
                    "episode_hint": {
                        "should_create_episode": False,
                        "suggested_title": None,
                        "suggested_plan": None,
                        "priority": "normal",
                    },
                }

            # memory_events가 비어 있으면, 기본 관찰 메모리를 하나 만들어서 저장 (디버깅/초기 테스트용)
            memory_events = obj.get("memory_events")
            if not memory_events:
                memory_events = [
                    {
                        "type": "observation",
                        "importance": 0.6,
                        "tags": ["chat"],
                        "summary": text[:60],
                        "source": "telegram",
                        "media_refs": [],
                        "raw": {"text": text},
                    }
                ]
            try:
                save_memory_events(user_id, memory_events)
            except Exception:
                logger.exception("memory_events 저장 중 에러 발생 (무시하고 계속 진행)")

            summary = obj.get("summary", text[:60])
            intent = obj.get("intent", "unknown")
            reply = obj.get("reply", "응, 잘 들었어. 더 이야기해줘. 😊")

            eh = obj.get("episode_hint") or {}
            episode_hint = EpisodeHint(
                should_create_episode=bool(eh.get("should_create_episode", False)),
                suggested_title=eh.get("suggested_title"),
                suggested_plan=eh.get("suggested_plan"),
                priority=eh.get("priority") or "normal",
            )

            safe_intent: IntentLiteral
            if intent in [
                "veo_prompt",
                "casual_chat",
                "daily_log",
                "todo",
                "question",
                "unknown",
            ]:
                safe_intent = intent  # type: ignore
            else:
                safe_intent = "unknown"

            return AnalyzeResponse(
                ok=True,
                mode=req.mode,
                summary=summary,
                intent=safe_intent,
                reply=reply,
                episode_hint=episode_hint,
                raw_model_output=raw,
            )
        except Exception:
            # LLM 쪽에서 에러가 나면 규칙 기반 fallback으로 넘긴다.
            logger.exception("LLM 분석 중 에러 발생, 규칙 기반 fallback 사용")
            # 아래의 규칙 기반 fallback 로직으로 내려가도록 한다.

    # 2) LLM 불가일 때 간단한 규칙 기반 fallback
    lowered = text.lower()
    intent: IntentLiteral = "unknown"
    if any(k in lowered for k in ["영상", "비디오", "씬", "장면", "shot"]):
        intent = "veo_prompt"
    elif any(k in lowered for k in ["해야", "할 일", "todo", "기억해줘"]):
        intent = "todo"
    elif any(k in lowered for k in ["왜", "어떻게", "?", "궁금"]):
        intent = "question"
    else:
        intent = "casual_chat"

    summary = text[:60]
    reply = "네 말 잘 들었어. 이건 내가 조용히 기록해둘게. 필요하면 이어서 더 말해줘. 🙂"

    episode_hint = EpisodeHint(
        should_create_episode=(intent == "veo_prompt"),
        suggested_title=None,
        suggested_plan=None,
        priority="normal",
    )

    return AnalyzeResponse(
        ok=True,
        mode=req.mode,
        summary=summary,
        intent=intent,
        reply=reply,
        episode_hint=episode_hint,
        raw_model_output={},
    )


# ─────────────────────────────────────
# 엔드포인트
# ─────────────────────────────────────

@app.post("/director/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    """
    공통 뇌 엔드포인트.
    지금은 mode == chat (텍스트)만 지원.
    """
    # vision 모드 분기
    if req.mode == "vision":
        return analyze_vision(req)

    # 기본: 텍스트(chat) 분석
    return analyze_text_with_llm(req)