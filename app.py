from fastapi import FastAPI, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles      # ✅ 여기 추가
from fastapi.responses import RedirectResponse  # ✅ 여기 추가
from director_core.models import AnalyzeRequest
from director_core.main import analyze_text_with_llm

from pydantic import BaseModel
from typing import Optional
from pathlib import Path
from datetime import datetime
import json

import os
from dotenv import load_dotenv

load_dotenv()  # 🔑 여기서 .env 내용 환경변수로 올림

app = FastAPI()

# ✅ 포털 정적 파일 서빙 + 루트 리다이렉트
app.mount("/portal", StaticFiles(directory="portal", html=True), name="portal")

@app.get("/")
async def root():
    return RedirectResponse(url="/portal")

@app.get("/health")
async def health():
    return {
        "status": "ok",
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "null"],  # 포털 로컬 파일 접근까지 열어둠
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# 📌 포털 대화 히스토리 (로컬 파일 기반)
# -------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
HISTORY_DIR = BASE_DIR / "portal_history"
HISTORY_DIR.mkdir(exist_ok=True)
HISTORY_FILE = HISTORY_DIR / "sowon.chat.jsonl"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def append_history(user_id: str, role: str, text: str) -> None:
    """
    포털 대화를 로컬 파일에 한 줄씩 쌓는다.
    user / assistant 모두 여기로 기록.
    """
    ts = _now_iso()
    entry_id = f"{ts}_{role}"

    entry = {
        "id": entry_id,
        "user_id": user_id,
        "role": role,        # "user" or "assistant"
        "text": text,
        "timestamp": ts,
    }

    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_history(limit: int = 30, before: Optional[str] = None, user_id: str = "sowon"):
    """
    가장 최근 limit개 메시지를 반환.
    - before 가 있으면, 그 id 이전까지에서 limit개를 가져온다.
    - user_id 필터링 포함.
    """
    if not HISTORY_FILE.exists():
        return []

    lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
    entries = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        # 여러 사용자 생길 것을 대비한 필터 (현재는 sowon만 사용)
        if obj.get("user_id") != user_id:
            continue

        entries.append(obj)

    if not entries:
        return []

    # 기본적으로는 맨 끝(=가장 최신까지)를 기준으로 자른다.
    idx_end = len(entries)

    if before:
        for i, e in enumerate(entries):
            if e.get("id") == before:
                idx_end = i
                break

    # idx_end 바로 앞까지에서 limit개 가져오기
    start = max(0, idx_end - limit)
    slice_entries = entries[start:idx_end]

    # 오래된 → 최신 순으로 정렬해서 돌려준다.
    slice_entries.sort(key=lambda e: e.get("timestamp", ""))

    return slice_entries


# -------------------------------------------------------------------
# 📌 텍스트 + 이미지 메시지 처리 (포털 채팅 기본 엔드포인트)
# -------------------------------------------------------------------
@app.post("/director/analyze")
async def director_analyze(
    text: str = Form(""),
    user_id: str = Form("sowon"),
    file: UploadFile | None = File(None),
):
    try:
        # 메시지가 완전 비어있으면 안내
        if not text and not file:
            return {"reply": "지금은 완전 빈 메시지는 못 읽어. 한 줄만 적어줘."}

        # 이미지만 들어온 경우 — 이미지 분석 모드 준비 전이므로 안내
        if not text and file is not None:
            return {"reply": "이미지 분석 모드는 아직 준비 중이야. 같이 보고 싶은 한 줄 설명만 적어줘."}

        # 텍스트 분석
        req = AnalyzeRequest(text=text or "", user_id=user_id or "sowon")
        core_resp = analyze_text_with_llm(req)
        reply = core_resp.reply

        # ✅ 대화 히스토리 파일에 기록
        try:
            append_history(user_id or "sowon", "user", text or "")
            append_history(user_id or "sowon", "assistant", reply or "")
        except Exception as he:
            print("[history] append failed:", he)

        return {"reply": reply}

    except Exception as e:
        return {"reply": f"부감독 뇌 연결 중 오류가 있었어. ({e})"}


# -------------------------------------------------------------------
# 📌 포털 대화 히스토리 조회 엔드포인트
#    - 프론트에서 /director/history?limit=30
#      또는 /director/history?before=<id>&limit=30 형태로 호출
# -------------------------------------------------------------------
@app.get("/director/history")
async def director_history(
    limit: int = 30,
    before: Optional[str] = None,
    user_id: str = "sowon",
):
    entries = load_history(limit=limit, before=before, user_id=user_id)
    return entries


# -------------------------------------------------------------------
# 📌 WebRTC 시그널링 스켈레톤 (양방향 통화 준비용)
#
# 지금은 "전화선 설치" 수준만 완성.
# Native Audio 모델 붙으면 answer SDP를 여기서 생성하게 됨.
# 현재는 SDP를 내려주지 않으므로 setRemoteDescription을 타지 않음.
# -------------------------------------------------------------------
class WebRTCOffer(BaseModel):
    sdp: str
    type: str = "offer"


class WebRTCIceCandidate(BaseModel):
    candidate: str
    sdpMid: Optional[str] = None
    sdpMLineIndex: Optional[int] = None


@app.post("/webrtc/offer")
async def webrtc_offer(offer: WebRTCOffer):
    """
    WebRTC Offer 수신용 스켈레톤.
    지금은 answer SDP를 만들지 않고, 연결 준비 OK만 내려줌.
    (AI 통화는 아직 미연결)
    """
    print("[WebRTC] Received offer from client")
    return {
        "status": "ok",
        "note": "placeholder: 아직 실제 WebRTC answer SDP는 내려주지 않아.",
    }


@app.post("/webrtc/ice")
async def webrtc_ice(candidate: WebRTCIceCandidate):
    """
    ICE candidate 수신용 스켈레톤.
    현재는 값만 받고 OK만 내려줌.
    """
    print("[WebRTC] ICE candidate received:", candidate.candidate)
    return {"status": "ok"}