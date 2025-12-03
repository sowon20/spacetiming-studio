from __future__ import annotations

import os
import google.generativeai as genai

# Gemini Flash 2.5 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY 환경 변수가 설정되어 있지 않습니다.")

genai.configure(api_key=GEMINI_API_KEY)


def call_model(system_prompt: str) -> str:
    """
    실제 Gemini Flash 2.5를 호출해서 답변을 생성하는 함수.

    system_prompt에는 이미:
      - 부감독 정체성(.soul)
      - 퍼소나 스타일(persona_layer)
      - 장기 기억(long_term_memory)
      - 불탄방 DNA(burned_room_dna)
      - 최근 대화 로그
      - 현재 입력
    이 모두가 하나의 텍스트로 합쳐져 있다.
    이 문자열을 그대로 모델에 전달해서 "한 번에" 답변을 받는다.
    """
    model = genai.GenerativeModel(GEMINI_MODEL)

    try:
        response = model.generate_content(
            system_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                top_p=0.9,
                max_output_tokens=512,
            ),
        )
    except Exception as e:
        # 서버 로그에만 에러를 남기고, 사용자에게는 부드럽게 설명
        print(f"[call_model] Gemini error: {e}")
        return "지금 모델 쪽에서 에러가 났어. 잠깐 숨 고르고 다시 시도하자."

    text = getattr(response, "text", "") or ""
    return text.strip()
