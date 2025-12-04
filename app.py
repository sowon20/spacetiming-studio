from __future__ import annotations

import os
import json
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


class HistoryItem(BaseModel):
    id: str
    role: str
    content: str
    time: str


HISTORY_FILES = [
    "portal_history/sowon.chat.jsonl",
    "portal_history/sowon.chat.mac.jsonl",
]


def _load_history(limit: int = 400) -> List[HistoryItem]:
    items_by_key: dict[str, HistoryItem] = {}

    for path in HISTORY_FILES:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    role = data.get("role") or "assistant"
                    text = data.get("text") or ""
                    ts = data.get("timestamp") or ""
                    msg_id = data.get("id") or ts or ""
                    # 시간 포맷에서 HH:MM만 뽑기
                    t_display = ""
                    if isinstance(ts, str) and ts:
                        # 예: 2025-11-26T00:17:09
                        parts = ts.split("T")
                        if len(parts) == 2 and ":" in parts[1]:
                            t_display = parts[1][:5]

                    # sowon.chat / sowon.chat.mac 에서 동일 발화가 중복되는 걸 막기 위한 키
                    key = f"{msg_id}|{role}|{text}"
                    items_by_key[key] = HistoryItem(
                        id=msg_id or key,
                        role=role,
                        content=text,
                        time=t_display,
                    )
        except FileNotFoundError:
            continue

    if not items_by_key:
        return []

    # 최신 순으로 정렬 후 limit만큼 자르기
    items_sorted = sorted(items_by_key.values(), key=lambda x: x.id)[-limit:]
    return items_sorted


app = FastAPI()


# CORS: chat.html / 확장프로그램 / 아이폰 브라우저 등 다 열어두기
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 나중에 도메인 고정하고 싶으면 여기 줄이면 됨
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/history")
async def api_history(limit: int = 400):
    """최근 대화 히스토리를 반환 (서버 기준, 기기와 브라우저를 넘어 공통 히스토리)."""
    try:
        items = _load_history(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"history_load_error: {e}")
    return [item.dict() for item in items]


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

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# 정적 파일(스타일/JS) 서빙
app.mount("/static", StaticFiles(directory="portal", html=False), name="static")

# chat.html 직접 서빙
@app.get("/chat.html")
async def chat_page():
    return FileResponse("portal/chat.html")