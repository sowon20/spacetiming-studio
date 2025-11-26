import os

# ===== 공통 설정 =====

# Veo 프롬프트 에이전트(지금 만든 서버) 주소
VEO_AGENT_URL = os.getenv(
    "VEO_AGENT_URL",
    "http://127.0.0.1:8899/veo/prompt",
)

# Gemini API 키 (veo_agent와 같이 씀)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# 나중에 Flow 자동화에서 쓸 기본 모델 이름
GEMINI_MODEL_TEXT = os.getenv("GEMINI_MODEL_TEXT", "gemini-2.0-flash")