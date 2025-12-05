from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from director_core.prompt_assembler import assemble_director_prompt
from director_core.recent_context import RecentContext

import os
import google.generativeai as genai

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # 실제 모델 이름에 맞게 수정 가능
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY env가 필요해요.")

genai.configure(api_key=GEMINI_API_KEY)
_model = genai.GenerativeModel(GEMINI_MODEL)


def call_model(system_prompt: str) -> str:
    """Gemini Flash 2.5 한 번 호출해서 텍스트만 꺼내오는 자리."""
    resp = _model.generate_content(system_prompt)
    # resp.text 있으면 그거, 아니면 파트들 합쳐서 반환
    if getattr(resp, "text", None):
        return resp.text
    try:
        return "".join(
            part.text
            for part in resp.candidates[0].content.parts
            if hasattr(part, "text")
        )
    except Exception:
        return "부감독: 응답 파싱 중 에러가 나서 원문을 보여주진 못했어."


app = FastAPI(title="Spacetime Director Core")


class ChatMessage(BaseModel):
    role: str
    content: str


class AttachmentMeta(BaseModel):
    name: str
    type: Optional[str] = None
    size: Optional[int] = None


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    attachments: Optional[List[AttachmentMeta]] = None


class ChatResponse(BaseModel):
    reply: str


@app.post("/chat")
async def chat(req: "ChatRequest"):
    """
    director_core recent_context + 부감독 프롬프트 + Gemini 호출
    """
    # 첨부 파일 메타정보는 req.attachments 로 들어온다.
    # assemble_director_prompt 호출 시 attachments 인자로 넘겨서,
    # 프롬프트 상단에 [첨부 파일 정보] 블럭으로 간단히 요약해 준다.
    # 1) 최근 대화 컨텍스트 로드/업데이트
    ctx = RecentContext()
    ctx.load()

    for m in req.messages:
        ctx.add(m.role, m.content)

    ctx.save()

    # 2) 프롬프트에 넣을 최근 대화 뽑기
    recent_for_prompt = ctx.extract_for_prompt(max_turns=32)
    user_input = req.messages[-1].content if req.messages else ""

    # 3) 부감독 인격 프롬프트 조립
    final_prompt = assemble_director_prompt(
        recent_messages=recent_for_prompt,
        user_input=user_input,
        max_recent=32,
        attachments=[a.model_dump() for a in (req.attachments or [])] or None,
    )

    # 4) Gemini 호출
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        resp = model.generate_content(final_prompt)
        reply_text = resp.text.strip() if hasattr(resp, "text") else str(resp)
    except Exception as e:
        reply_text = f"부감독 뇌 연결 중 오류가 있었어. (세부: {e})"

    return {"reply": reply_text}

@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "role": "director_core"}
