from __future__ import annotations
from .memory_store import save_memory_events, load_recent_memories
from .imported_memory_loader import load_imported_memories
from .soul_loader import (
    build_core_system_prompt,
    build_timeline_context,
)
from .prompt_loader import load_base_system_prompt
from .prompt_assembler import assemble_prompt_for_llm

import os
import json
import re
import logging
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from director_core.config_manager import apply_config_updates

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
    return genai.GenerativeModel("gemini-2.0-flash", system_instruction=SYSTEM_PROMPT)


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

SYSTEM_PROMPT = load_base_system_prompt()

core_soul_prompt = build_core_system_prompt()
if core_soul_prompt:
    SYSTEM_PROMPT = SYSTEM_PROMPT + "\n\n" + core_soul_prompt


def load_recent_dialogue(user_id: str, limit: int = 40) -> str:
    """
    portal_history/{user_id}.chat.jsonl 에서 최근 대화 몇 줄을 읽어서
    LLM 프롬프트에 붙일 수 있는 텍스트 블록으로 만든다.
      예시:
        {"role": "user", "content": "..."}
        {"role": "assistant", "content": "..."}
    """
    try:
        history_path = Path("portal_history") / f"{user_id}.chat.jsonl"
        if not history_path.exists():
            return ""

        lines = history_path.read_text(encoding="utf-8").splitlines()
        if not lines:
            return ""

        # 🔹 최근 limit개만 사용 (헛소리/감탄사 섞여도 길이로 밀어붙이기)
        recent = lines[-limit:]

        blocks: list[str] = []
        for line in recent:
            try:
                obj = json.loads(line)
            except Exception:
                continue

            role = (obj.get("role") or obj.get("speaker") or "user").strip()
            content = (obj.get("content") or obj.get("text") or "").strip()
            if not content:
                continue

            prefix = "assistant" if role == "assistant" else "user"
            blocks.append(f"{prefix}: {content}")

        if not blocks:
            return ""

        return "[Recent dialogue]\n" + "\n".join(blocks)

    except Exception:
        logger.exception("최근 대화 불러오는 중 에러 (무시하고 진행)")
        return ""

def rule_based_analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """
    LLM이 없거나 에러 날 때 쓰는 아주 단순한 fallback.
    지금은 그냥 원래 텍스트를 되비춰주는 정도로만 동작하게 둔다.
    """
    text = (req.text or "").strip()
    if not text:
        text = ""

    reply = (
        "지금은 LLM 쪽에서 오류가 나서, 복잡한 분석 대신 아주 단순하게만 같이 볼 수 있어.\n"
        "네가 방금 보낸 내용은 대략 이런 느낌이야:\n\n"
        f"{text}"
    )

    return AnalyzeResponse(
        ok=True,
        mode=req.mode,
        summary=(text[:80] + "...") if len(text) > 80 else text,
        intent="casual_chat",
        reply=reply,
        episode_hint=EpisodeHint(
            should_create_episode=False,
            suggested_title=None,
            suggested_plan=None,
            priority="normal",
        ),
        raw_model_output={"fallback": True},
    )

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
            combined_prompt = assemble_prompt_for_llm(req)
        except Exception:
            logger.exception("프롬프트 조립 중 에러 발생 - 규칙 기반 fallback으로 전환")
            return rule_based_analyze(req)

        try:
            model = get_gemini_model()
            chat_session = model.start_chat()
            chat = chat_session.send_message(combined_prompt)

            ai_text = (chat.text or "").strip()
            if not ai_text:
                raise ValueError("LLM 응답이 비어 있음")

            return AnalyzeResponse(
                ok=True,
                mode=req.mode,
                summary=(text[:80] + "...") if len(text) > 80 else text,
                intent="casual_chat",  # 나중에 intent 분석 붙이면 여기만 바꾸면 됨
                reply=ai_text,
                episode_hint=EpisodeHint(
                    should_create_episode=False,
                    suggested_title=None,
                    suggested_plan=None,
                    priority="normal",
                ),
                raw_model_output={
                    "combined_prompt": combined_prompt,
                },
            )

        except Exception:
            logger.exception("LLM 호출 중 에러 발생 - 규칙 기반 fallback으로 전환")
            return rule_based_analyze(req)

    # 2) LLM 사용 불가 시, 규칙 기반 분석만 사용
    return rule_based_analyze(req)


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