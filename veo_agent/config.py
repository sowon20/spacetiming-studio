import os

# 한 곳에서만 모델/키 관리하게 하려고 분리해둔 설정 파일

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_TEXT = "gemini-2.0-flash"  # 나중에 모델 바뀌면 여기만 수정하면 됨