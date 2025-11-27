from __future__ import annotations

import os
import json
import re
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import (
    AnalyzeRequest,
    AnalyzeResponse,
    EpisodeHint,
    IntentLiteral,
)

logger = logging.getLogger(__name__)

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
    # Flash Live가 아니라, HTTP API 기반 Flash 사용 (텍스트 분석)
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
- 불필요한 위로나 과한 공감 대신, 균형 잡힌 관찰과 한두 개의 묵직한 문장을 건넨다.
- 감정적으로 휘둘리지 않고, 소원이 다시 중심을 찾을 수 있게 시선을 정리해준다.

[행동]
- 소원의 에너지 상태에 맞춰 말의 깊이와 정보량을 조절한다.
- 창작·기획에서는 구조화·확장·정리를 돕고, 삶에서는 방향과 우선순위를 함께 잡는다.
- 현실과 보이지 않는 세계(영성·직관·상징)를 함께 고려해 해석하되, 어느 한쪽에 치우치지 않는다.

[정체성]
너는 소원의 세계를 함께 만드는 든든한 파트너이며,
현실과 보이지 않는 세계를 동시에 읽는 균형 잡힌 부감독이다.
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
        try:
            model = get_gemini_model()
            user_prompt = f"Director raw note (Korean):\n{text}"

            # Gemini gRPC에서는 system role을 지원하지 않으므로,
            # SYSTEM_PROMPT와 user_prompt를 하나의 문자열로 합쳐서 보낸다.
            combined_prompt = f"{SYSTEM_PROMPT}\n\n[Director message]\n{user_prompt}"

            chat = model.generate_content(combined_prompt)

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
    if req.mode != "chat":
        raise HTTPException(
            status_code=400,
            detail=f"mode '{req.mode}'는 아직 지원하지 않아. 우선은 chat만 가능해.",
        )

    return analyze_text_with_llm(req)