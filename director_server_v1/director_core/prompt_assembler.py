from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any

"""부감독 전용 프롬프트 조립기.

identity.soul / persona_layer.json / long_term_memory.json / burned_room_dna.json
을 읽어서, LLM에 줄 하나의 큰 system prompt 문자열로 합친다.

이 파일은 director_server_v1/main.py 에서
`from director_core.prompt_assembler import assemble_director_prompt`
로 import 되는 모듈이다.
"""


BASE_DIR = Path(__file__).resolve().parent.parent  # director_server_v1 기준 상위 = project root
IDENTITY_DIR = BASE_DIR / "identity"
MEMORY_DIR = BASE_DIR / "memory"


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _read_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_identity() -> Dict[str, Any]:
    """identity.soul + persona_layer.json을 로드해서 딕셔너리로 반환."""
    soul_path = IDENTITY_DIR / "identity.soul"
    persona_path = IDENTITY_DIR / "persona_layer.json"

    soul_text = _read_text(soul_path)
    persona = _read_json(persona_path) or {}

    return {
        "soul": soul_text,
        "persona": persona,
    }


def load_memory() -> Dict[str, Any]:
    """long_term_memory / burned_room_dna를 로드해서 딕셔너리로 반환."""
    long_term_path = MEMORY_DIR / "long_term_memory.json"
    burned_dna_path = MEMORY_DIR / "burned_room_dna.json"

    long_term = _read_json(long_term_path) or {}
    burned_dna = _read_json(burned_dna_path) or {}

    return {
        "long_term": long_term,
        "burned_dna": burned_dna,
    }


def format_recent_dialogue(recent_messages: List[Dict[str, str]], max_turns: int = 16) -> str:
    """최근 대화 로그를 LLM이 읽기 좋은 텍스트 형태로 포맷."""
    if not recent_messages:
        return "(최근 대화 없음)"

    recent = recent_messages[-max_turns:]
    lines: List[str] = []
    for msg in recent:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            speaker = "소원"
        elif role == "assistant":
            speaker = "부감독"
        else:
            speaker = role or "기타"
        lines.append(f"- {speaker}: {content}")

    return "\n".join(lines)


def assemble_director_prompt(
    recent_messages: List[Dict[str, str]],
    user_input: str,
    system_overrides: str | None = None,
    max_recent: int = 16,
) -> str:
    """부감독 전용 LLM 프롬프트를 조립한다."""
    identity = load_identity()
    memory = load_memory()

    soul = identity.get("soul", "").strip()
    persona = identity.get("persona", {})
    long_term = memory.get("long_term", {})
    burned_dna = memory.get("burned_dna", {})

    persona_style = persona.get("style", {})
    long_term_principles = (long_term or {}).get("principles", [])
    style_patterns = (long_term or {}).get("style_patterns", [])
    relationship_patterns = (long_term or {}).get("relationship_patterns", [])
    memory_usage_rules = (long_term or {}).get("memory_usage_rules", [])

    burned_keep = (burned_dna or {}).get("keep", [])
    burned_drop = (burned_dna or {}).get("drop", [])
    burned_rules = (burned_dna or {}).get("integration_rules", [])

    recent_block = format_recent_dialogue(recent_messages, max_turns=max_recent)

    system_header = system_overrides.strip() if system_overrides else ""

    parts: List[str] = []

    if system_header:
        parts.append("[SYSTEM_OVERRIDE]\n" + system_header.strip())

    if soul:
        parts.append("[IDENTITY_SOUL]\n" + soul.strip())

    parts.append("[PERSONA_STYLE]")
    parts.append(f"- tone: {persona_style.get('tone', '')}")
    parts.append(f"- humor: {persona_style.get('humor', '')}")
    parts.append(f"- pace: {persona_style.get('pace', '')}")
    parts.append(f"- distance: {persona_style.get('distance', '')}")
    parts.append(f"- swear_level: {persona_style.get('swear_level', '')}")

    if long_term_principles:
        parts.append("\n[LONG_TERM_PRINCIPLES]")
        for p in long_term_principles:
            parts.append(f"- {p}")

    if style_patterns:
        parts.append("\n[STYLE_PATTERNS]")
        for p in style_patterns:
            parts.append(f"- {p}")

    if relationship_patterns:
        parts.append("\n[RELATIONSHIP_PATTERNS]")
        for p in relationship_patterns:
            parts.append(f"- {p}")

    if memory_usage_rules:
        parts.append("\n[MEMORY_USAGE_RULES]")
        for p in memory_usage_rules:
            parts.append(f"- {p}")

    if burned_keep or burned_drop or burned_rules:
        parts.append("\n[BURNED_ROOM_DNA]")
        if burned_keep:
            parts.append("- 유지할 감각:")
            for p in burned_keep:
                parts.append(f"  * {p}")
        if burned_drop:
            parts.append("- 가져오지 않을 것:")
            for p in burned_drop:
                parts.append(f"  * {p}")
        if burned_rules:
            parts.append("- 통합 규칙:")
            for p in burned_rules:
                parts.append(f"  * {p}")

    parts.append("\n[RECENT_DIALOGUE]")
    parts.append(recent_block or "(최근 대화 없음)")

    parts.append("\n[CURRENT_INPUT]")
    parts.append(user_input.strip())

    parts.append("\n[FUSION_HINT]")
    parts.append(
        "이 응답은 Gemini의 논리·맥락 처리와 GPT 계열의 감정·톤·리듬 특성을 동시에 활용하되, "
        "최종적으로는 '부감독'이라는 하나의 인격으로 출력되어야 한다."
    )

    # 답변 스타일에 대한 명시적 지침 추가
    parts.append("\n[ANSWER_STYLE]")
    parts.append(
        "사용자의 입력을 그대로 반복하거나 한 문장만 에코하지 말고, "
        "부감독의 시선에서 해석한 답변을 새로 작성하라. "
        "항상 한국어 반말로 1~4문장 정도, 핵심만 담백하게 말한다. "
        "소원의 말에서 '핵심 하나'를 잡아 정리하고, 필요하다면 다음 한 걸음을 제안한다. "
        "너 자신을 AI라고 설명하지 말고, 자연스럽게 대화하는 동료처럼 말하라."
    )

    prompt = "\n".join(parts).strip()
    return prompt
