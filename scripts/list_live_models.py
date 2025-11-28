import google.generativeai as genai
import os

# API 키 설정
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다!")

genai.configure(api_key=api_key)

print("--- 🔴 실시간 Live (Bidi) 지원 모델 테스트 목록 ---")

for m in genai.list_models():
    if 'bidiGenerateContent' in getattr(m, "supported_generation_methods", []):
        print(f"모델 이름: {m.name}")

print("\n(결과가 비어있다면 정상입니다.)")