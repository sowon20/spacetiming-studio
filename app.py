from __future__ import annotations

import os
import json
import urllib.request
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ─────────────────────────────────────
# 기본 경로 설정
# ─────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTAL_DIR = os.path.join(BASE_DIR, "portal")

# 부감독 뇌(director_server_v1) HTTP 엔드포인트
DIRECTOR_CORE_URL = os.getenv("DIRECTOR_CORE_URL", "http://127.0.0.1:8897").rstrip("/")

# ─────────────────────────────────────
# FastAPI 앱 생성 & CORS
# ─────────────────────────────────────
app = FastAPI()

# 아이폰 / 크롬 사이드바 등 어디서든 붙을 수 있게 느슨하게 풀어둠
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────
# 정적 파일: portal/chat.html, style.css, app.js 등
# nginx가 / 를 8000으로 프록시하면,
#   https://sowon.mooo.com/chat.html → portal/chat.html
# ─────────────────────────────────────
app.mount("/", StaticFiles(directory=PORTAL_DIR, html=True), name="portal")


# ─────────────────────────────────────
# 부감독 뇌로 넘길 요청 스키마
# ─────────────────────────────────────
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


# ─────────────────────────────────────
# /api/chat → 8897 /chat 으로 브릿지
#  - chat.html에서 이 주소로 POST하면 됨
# ─────────────────────────────────────
@app.post("/api/chat")
def portal_chat(req: ChatRequest) -> Dict[str, Any]:
    """포털 게이트웨이: 브라우저 → director_core(8897) 브릿지"""

    payload = {
        "messages": [m.dict() for m in req.messages]
    }

    url = f"{DIRECTOR_CORE_URL}/chat"
    data = json.dumps(payload).encode("utf-8")
    http_req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(http_req, timeout=60) as resp:
            resp_body = resp.read().decode("utf-8")
            return json.loads(resp_body)
    except Exception as e:
        # director_core가 죽어있거나 네트워크 문제면 여기로 옴
        raise HTTPException(
            status_code=500,
            detail=f"director_core(8897) 연결 중 오류: {e}",
        )