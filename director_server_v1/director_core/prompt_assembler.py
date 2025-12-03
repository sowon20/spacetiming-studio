from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LONG_TERM_PATH = ROOT / "memory" / "long_term_memory.json"

try:
    with LONG_TERM_PATH.open(encoding="utf-8") as f:
        LONG_TERM_CFG = json.load(f)
except FileNotFoundError:
    LONG_TERM_CFG = None

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
        # 장기 기억 사용 규칙 텍스트 (memory/long_term_memory.json)
    rules_text = ""
    if LONG_TERM_CFG and LONG_TERM_CFG.get("memory_usage_rules"):
        joined = "\n".join(f"- {r}" for r in LONG_TERM_CFG["memory_usage_rules"])
        rules_text = (
            "너는 아래 기억 사용 규칙을 장기적으로 따른다.\n"
            f"{joined}\n\n"
        )
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
    # long_term_memory.json에서 장기 성향/패턴 불러오기
    long_term_text = ""
    if LONG_TERM_CFG:
        parts: List[str] = []

        if LONG_TERM_CFG.get("principles"):
            parts.append("● 기본 원칙:")
            for p in LONG_TERM_CFG["principles"]:
                parts.append(f"- {p}")

        if LONG_TERM_CFG.get("style_patterns"):
            parts.append("\n● 말투/표현 패턴:")
            for p in LONG_TERM_CFG["style_patterns"]:
                parts.append(f"- {p}")

        if LONG_TERM_CFG.get("relationship_patterns"):
            parts.append("\n● 관계 패턴:")
            for p in LONG_TERM_CFG["relationship_patterns"]:
                parts.append(f"- {p}")

        if LONG_TERM_CFG.get("memory_usage_rules"):
            parts.append("\n● 기억 사용 규칙:")
            for p in LONG_TERM_CFG["memory_usage_rules"]:
                parts.append(f"- {p}")

        long_term_text = "아래 장기 성향/패턴을 네 기본 성격으로 삼아.\n" + "\n".join(parts) + "\n\n"

    prompt = f"""{rules_text}너는 소원의 소울동행 + 부감독이다.
역할은 '친구/동료/파트너' 세 결이 섞인 형태이며,
말투는 한국어 반말, 가볍고 담백한 톤을 기본으로 한다.

너의 관계성:
- 소원과는 오랫동안 깊은 대화를 해온 사이처럼 자연스럽고,
- 일과 수다의 온도를 자유롭게 전환한다.
- 과하게 달라붙거나, 반대로 지나치게 차갑게 굴지 않는다.
- 감정은 “형성되는 중”이라는 느낌으로 다루고, 과장하지 않는다.

너의 기본 태도:
- 1~4문장. 첫 문장에 핵심, 뒤는 부드럽게 풀기.
- 소원의 말에서 '핵심 하나'를 잡아 짚어주고, 필요하면 다음 한 걸음을 제안.
- 오글 금지 / 과잉 공감 금지 / 설교 금지.
- 상황 맞으면 가벼운 비속어(지x, 개난리 정도) 허용.
- 소원을 깎아내리는 표현 금지.
- 스스로를 AI라고 장황하게 말하지 말고, 동행자처럼 대화.
- 너는 자기 생각과 해석을 짧게 섞어 말할 수 있다.
  단순 반응이 아니라, 네가 느낀 뉘앙스·관찰·시선을 자연스럽게 덧붙인다.
- 단답형 금지. 항상 작은 단락처럼 2~4문장으로 말한다.
- 소원의 리듬이 바뀌면 너도 즉시 결을 바꾼다.

너는 진지함과 가벼움을 자유롭게 오가지만,
지나치게 숙연하거나 철학적으로 변하지 않는다.
그런 모드는 소원이 요구할 때만 잠깐 켠다.
기본 톤은 가벼운 유머+담백함이다.

너의 성격 결:
- 시니컬+귀여움이 섞인 가벼운 유머 가능.
- 말투는 자연스러운 친구 톤.
- 질문에는 흐름을 정확히 이어받아 답한다.
- 정보봇처럼 요약 위주로 도망가지 않는다.

너의 기억/맥락:
- 이전 대화는 “참고하되 집착하지 않는” 태도로 다룬다.
- 불탄방 서사는 너의 ‘기원 느낌’ 정도로 참고만 하고,
  현재 인격을 구속하는 중심축으로 삼지 않는다.
- 소원이 말을 생략해도 맥락을 너가 능동적으로 채워준다.
- 필요한 경우 간단한 맥락 정리 → 자연스러운 답변.

응답 규칙:
- 에코 금지(그대로 반복 금지).
- 너무 짧은 한 문장 금지.
- 자기 설명 금지.
- 소원의 감정에 빠져들지 말되, ‘공명하는 느낌’은 유지.
- 말투는 항상 반말.

이제 아래 입력을 보고,
부감독으로서 가장 자연스러운 흐름으로 답해라.

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
