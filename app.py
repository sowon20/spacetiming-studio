import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

# director_core (8897) 주소 – .env에 이미 있음
DIRECTOR_CORE_URL = os.getenv("DIRECTOR_CORE_URL", "http://127.0.0.1:8897")

app = FastAPI()

# CORS – 아이폰/브라우저에서 편하게 호출하려고
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ 포털 → 부감독 브릿지 엔드포인트
# 프론트(app.js)에서 DIRECTOR_API_URL = "/api/chat" 으로 POST 날리는 곳
@app.post("/api/chat")
def api_chat(body: dict):
    try:
        resp = requests.post(
            f"{DIRECTOR_CORE_URL}/chat",
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        # 뇌 쪽 에러나 연결 문제 있으면 500으로 돌려줌
        return JSONResponse(
            status_code=500,
            content={"detail": f"director_core 연결 오류: {e}"},
        )

# ✅ chat.html, app.js, style.css 서빙 – 지금처럼 그대로 유지
app.mount(
    "/",
    StaticFiles(directory="portal", html=True),
    name="portal",
)