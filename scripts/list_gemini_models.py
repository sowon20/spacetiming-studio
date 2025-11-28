import os
import google.generativeai as genai

# GEMINI_API_KEY 환경변수에서 키 가져오기
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되어 있지 않습니다!")

genai.configure(api_key=api_key)

print("--- 사용 가능한 모델 목록 ---")
for m in genai.list_models():
    if "generateContent" in getattr(m, "supported_generation_methods", []):
        print(f"모델 이름: {m.name}")