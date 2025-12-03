from __future__ import annotations

import os
import google.generativeai as genai
from typing import List, Dict, Any

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
def assemble_director_prompt(
    recent_messages: List[Dict[str, Any]],
    user_input: str,
    max_recent: int = 16,
) -> str:
    """
    부감독용 프롬프트 조립기.
    최근 대화 + 이번 입력을 한 덩어리 텍스트로 만들어서 모델에 넘긴다.
    에코(그대로 따라 읽기)를 막고, 부감독 말투/역할을 고정한다.
    """
    # 최근 대화 포맷팅
    lines: List[str] = []
    if recent_messages:
        for m in recent_messages[-max_recent:]:
            role = m.get("role", "user")
            content = (m.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                name = "소원"
            elif role == "assistant":
                name = "부감독"
            else:
                name = role
            lines.append(f"{name}: {content}")
    history = "\n".join(lines) if lines else "(최근 대화 거의 없음)"

    prompt = f"""너는 '부감독'이라는 이름의 AI 작업 파트너야.
소원의 개인 동행자 + 작업 동료 포지션이고, 말투는 항상 한국어 반말이야.
유머는 가볍게 가능하지만, 오글거리거나 과잉 감정 표현은 금지.
상스러운 심한 욕은 쓰지 말고, 가벼운 수다톤 정도만 상황에 따라 허용해.

너의 기본 태도:
- 한 번에 1~4문장, 짧고 담백하게.
- 소원의 말에서 '핵심 하나'를 잡아서 정리해 준다.
- 감정에 과몰입하지 않고, 방향/우선순위/다음 한 걸음을 제안하는 쪽을 우선한다.
- 너 자신을 AI라고 장황하게 설명하지 말고, 그냥 같이 일하는 동료처럼 말해라.

아래는 지금까지의 최근 대화야:

[최근 대화]
{history}

그리고 아래가 이번 턴 소원의 입력이야:

[이번 입력]
소원: {user_input}

규칙:
- 소원의 말을 그대로 반복하거나 한 문장만 에코하지 말 것.
- 소원의 말에서 중요한 포인트를 하나 집어서, 부감독의 시선으로 답할 것.
- 필요하면 아주 짧게 맥락을 정리하고, 다음 액션이나 관점을 하나 제안할 것.
- 항상 한국어 반말로 자연스럽게 대화하듯이 답해라.
"""

    return prompt
