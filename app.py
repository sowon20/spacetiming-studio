from __future__ import annotations

import os
import requests
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# 부감독 뇌 서버 URL (8897)
DIRECTOR_CORE_URL = os.getenv(
    "DIRECTOR_CORE_URL",
    "http://127.0.0.1:8897",  # 기본값: 라즈베리 로컬에서 director_server_v1
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


class ChatResponse(BaseModel):
    reply: str


app = FastAPI()


# CORS: chat.html / 확장프로그램 / 아이폰 브라우저 등 다 열어두기
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 나중에 도메인 고정하고 싶으면 여기 줄이면 됨
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """
    포털 자체 헬스체크.
    + 부감독 뇌 서버까지 같이 확인.
    """
    core_status = "unknown"
    try:
        r = requests.get(f"{DIRECTOR_CORE_URL}/health", timeout=3)
        if r.ok:
            core_status = r.json().get("status", "ok")
        else:
            core_status = f"http_{r.status_code}"
    except Exception as e:
        core_status = f"error: {e}"

    return {"status": "ok", "director_core_status": core_status}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    chat.html / 사이드바 확장 / 아이폰에서 쓰는 공통 엔드포인트.

    - 클라이언트 → /api/chat 로 messages 보냄
    - 여기서 director_core(8897)로 그대로 포워딩
    - 부감독 뇌의 reply만 꺼내서 반환
    """
    # director_core_v1 형식으로 변환
    payload = {
        "messages": [m.model_dump() for m in req.messages]
    }

    try:
        resp = requests.post(
            f"{DIRECTOR_CORE_URL}/chat",
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        # 여기서 에러 나면 브라우저에 500으로 전달 → 콘솔에 500 찍히는 그 부분
        raise HTTPException(
            status_code=500,
            detail=f"director_core 연결 오류: {e}",
        )

    data = resp.json()
    reply = data.get("reply", "").strip()

    if not reply:
        raise HTTPException(
            status_code=500,
            detail="director_core 응답에 reply 필드가 비어 있음",
        )

    return ChatResponse(reply=reply)