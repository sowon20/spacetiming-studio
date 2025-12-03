from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

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


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


class ChatResponse(BaseModel):
    reply: str


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages 비어 있음")

    # 최신 메시지 = 이번 턴 사용자 입력이라고 가정
    last = req.messages[-1]
    if last.role not in ("user", "소원"):
        raise HTTPException(status_code=400, detail="마지막 메시지는 user여야 함")

    user_input = last.content

    # recent_context 로드 및 업데이트
    ctx = RecentContext()
    ctx.load()
    for m in req.messages:
        ctx.add(m.role, m.content)
    ctx.save()

    # 프롬프트 조립용 recent 리스트 (이미 의미 턴 기준 필터링됨)
    recent_for_prompt = ctx.to_list()

    system_prompt = assemble_director_prompt(
        recent_messages=recent_for_prompt,
        user_input=user_input,
        max_recent=16,
    )

    reply_text = call_model(system_prompt)

    # 부감독 응답도 컨텍스트에 추가
    ctx.add("assistant", reply_text)
    ctx.save()

    return ChatResponse(reply=reply_text)


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "role": "director_core"}
