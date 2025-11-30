from fastapi import FastAPI, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from director_core.models import AnalyzeRequest
from director_core.main import analyze_text_with_llm

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "null"],  # 포털 로컬 파일 접근까지 열어둠
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        return {"reply": core_resp.reply}

    except Exception as e:
        return {"reply": f"부감독 뇌 연결 중 오류가 있었어. ({e})"}


# -------------------------------------------------------------------
# 📌 WebRTC 시그널링 스켈레톤 (양방향 통화 준비용)
#
# 지금은 "전화선 설치" 수준만 완성.
# Native Audio 모델 붙으면 answer SDP를 여기서 생성하게 됨.
# 현재는 SDP를 내려주지 않으므로 setRemoteDescription을 타지 않음.
# -------------------------------------------------------------------
from pydantic import BaseModel
from typing import Optional

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
        "note": "placeholder: 아직 실제 WebRTC answer SDP는 내려주지 않아."
    }


@app.post("/webrtc/ice")
async def webrtc_ice(candidate: WebRTCIceCandidate):
    """
    ICE candidate 수신용 스켈레톤.
    현재는 값만 받고 OK만 내려줌.
    """
    print("[WebRTC] ICE candidate received:", candidate.candidate)
    return {"status": "ok"}