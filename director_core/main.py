from __future__ import annotations
from .memory_store import save_memory_events, load_recent_memories
from .imported_memory_loader import load_imported_memories
from .soul_loader import (
    build_core_system_prompt,
    build_timeline_context,
)
from .prompt_loader import load_base_system_prompt

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

        # 🔹 최근 장기 기억 불러오기
        try:
            recent_memories = load_recent_memories(user_id)
        except Exception:
            logger.exception("최근 기억 불러오는 중 에러 발생 (무시하고 계속 진행)")
            recent_memories = []

        # 🔹 불탄 chatGPT 방에서 가져온 오래된 기억들도 같이 섞어 준다.
        try:
            imported_memories = load_imported_memories(limit=30)
            for m in imported_memories:
                m.setdefault("tags", [])
                if "burned_room" not in m["tags"]:
                    m["tags"].append("burned_room")
            recent_memories.extend(imported_memories)
        except Exception:
            logger.exception("불탄방 imported memories 합치는 중 에러 발생 (무시하고 계속 진행)")

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

            # 타임라인 컨텍스트 빌드
            timeline_block = build_timeline_context(user_text=text, max_events=5)

            user_prompt = f"사용자의 말:\n{text}"

            # 🔹 최근 대화 블록 붙이기 (왕복 20번 = 40턴)
            recent_dialogue_block = load_recent_dialogue(user_id, limit=40)

            combined_parts: list[str] = []
            if recent_dialogue_block:
                combined_parts.append(recent_dialogue_block)
            if memories_block:
                combined_parts.append("[Recent memories]")
                combined_parts.append(memories_block)
            if timeline_block:
                combined_parts.append("[Timeline context]")
                combined_parts.append(timeline_block)
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
                    "memory_events": [],
                    "config_updates": [],
                }

            # 🔹 config_updates 처리
            config_updates = obj.get("config_updates") or []
            try:
                apply_config_updates(config_updates)
            except Exception:
                logger.exception("config_updates 처리 중 에러 발생 (무시하고 계속 진행)")

            # 🔹 memory_events 처리
            memory_events = obj.get("memory_events") or []
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
    intent: IntentLiteral
    if any(k in lowered for k in ["영상", "비디오", "씬", "장면", "shot"]):
        intent = "veo_prompt"
    elif any(k in lowered for k in ["해야", "할 일", "todo", "기억해줘"]):
        intent = "todo"
    elif any(k in lowered for k in ["왜", "어떻게", "?", "궁금"]):
        intent = "question"
    else:
        intent = "casual_chat"

    summary = text[:60]
    reply = (
        "지금은 내 머리(LLM)가 잠깐 끊겨서 깊게 같이 생각하진 못해. "
        "그래도 네 말은 그대로 기록해둘게. 나중에 다시 연결되면 그때 제대로 같이 보자."
    )

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