
# director_core/prompt_loader_refactored.py
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any
import json

# 컨텍스트 기본 설정값
MAX_RECENT_DIALOGUE_TURNS = 100
MAX_RECENT_MEMORIES = 3
MAX_TIMELINE_EVENTS = 3


def load_base_system_prompt() -> str:
    """기본 SYSTEM_PROMPT 텍스트를 읽어온다.

    기존 director_core/prompts/director_system_prompt.txt 경로를 그대로 사용하되,
    파일이 없으면 짧은 기본 프롬프트를 리턴한다.
    """
    base_dir = Path(__file__).resolve().parent
    # 기존 구조 유지
    default_path = base_dir / "prompts" / "director_system_prompt.txt"

    if default_path.exists():
        return default_path.read_text(encoding="utf-8").strip()

    # fallback: 같은 디렉터리에 직접 둔 경우도 한 번 더 시도
    alt_path = base_dir / "director_system_prompt.txt"
    if alt_path.exists():
        return alt_path.read_text(encoding="utf-8").strip()

    # 그래도 없으면 최소 프롬프트
    return "너는 소원의 소울동행이자 부감독이야. 반말로 짧고 담백하게 대답해."


def trim_recent_dialogue(
    dialogue: List[Dict[str, str]],
    max_turns: int = MAX_RECENT_DIALOGUE_TURNS,
) -> List[Dict[str, str]]:
    """recent dialogue에서 뒤에서부터 max_turns개만 남긴다.

    - dialogue: [{"role": "user"|"assistant", "content": "..."}, ...]
    - max_turns: 기본 100턴 (설계 합의값)
    """
    if not dialogue:
        return []
    if max_turns <= 0:
        return []
    return dialogue[-max_turns:]


def _format_dialogue(dialogue: List[Dict[str, str]]) -> str:
    """LLM 프롬프트에 넣기 좋은 단순 텍스트 형식으로 변환한다."""
    lines: List[str] = []
    for msg in dialogue:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def build_recent_dialogue_summary(
    dialogue: List[Dict[str, str]],
    max_lines: int = 8,
    max_chars_per_line: int = 80,
) -> str:
    """최근 대화를 5~8줄 정도의 요약 비슷한 형태로 만든다.

    진짜 요약이라기보다는:
    - 마지막 몇 개의 user 발화 위주로
    - 각 줄은 앞부분만 잘라서
    LLM이 한눈에 "지금 무슨 흐름인지" 잡을 수 있게 도와주는 역할이다.
    """
    if not dialogue:
        return ""

    # user 메시지 위주로 뒤에서부터 모은다
    user_msgs = [m for m in dialogue if m.get("role") == "user"]
    if not user_msgs:
        user_msgs = dialogue

    selected = user_msgs[-max_lines:]
    lines: List[str] = []
    for msg in selected:
        content = (msg.get("content") or "").strip().replace("\n", " ")
        if not content:
            continue
        if len(content) > max_chars_per_line:
            content = content[: max_chars_per_line - 3] + "..."
        lines.append(f"- user: {content}")

    return "\n".join(lines)


def build_llm_prompt(
    core_system_prompt: str,
    recent_dialogue: List[Dict[str, str]],
    director_message: str,
    recent_memories: List[Dict[str, Any]] | None = None,
    timeline_events: List[Dict[str, Any]] | None = None,
    imported_memories: List[Dict[str, Any]] | None = None,
) -> str:
    """LLM에 전달할 전체 프롬프트 문자열을 조합한다.

    설계 원칙:
    - recent_dialogue 100턴을 최우선으로 사용한다.
    - recent_dialogue 요약(최대 8줄)을 추가해 흐름을 한 번 더 고정한다.
    - recent_memories는 최대 3개만 사용한다.
    - timeline_events는 최대 3개만 사용한다.
    - imported_memories는 보조 힌트로만 쓰고, 필요 없다면 생략해도 된다.

    인자는 이미 외부에서 로딩된 것을 받아 조합만 담당하며,
    이 모듈을 사용하는 쪽에서 load_recent_memories, build_timeline_context 등을 호출한 뒤
    그 결과를 넘겨주는 형태를 권장한다.
    """
    # 1) recent dialogue 정리
    trimmed_dialogue = trim_recent_dialogue(recent_dialogue, MAX_RECENT_DIALOGUE_TURNS)
    dialogue_block = _format_dialogue(trimmed_dialogue)
    dialogue_summary = build_recent_dialogue_summary(trimmed_dialogue)

    # 2) 메모리 레이어 제한 적용
    recent_memories = (recent_memories or [])[:MAX_RECENT_MEMORIES]
    timeline_events = (timeline_events or [])[:MAX_TIMELINE_EVENTS]
    imported_memories = imported_memories or []

    parts: List[str] = []

    # CORE SYSTEM PROMPT
    parts.append("[CORE_SYSTEM_PROMPT]")
    parts.append(core_system_prompt.strip())

    # RECENT DIALOGUE (원본)
    parts.append("\n[RECENT_DIALOGUE]")
    if dialogue_block:
        parts.append(dialogue_block)
    else:
        parts.append("(최근 대화 없음)")

    # RECENT DIALOGUE SUMMARY
    if dialogue_summary:
        parts.append("\n[RECENT_DIALOGUE_SUMMARY]")
        parts.append(dialogue_summary)

    # RECENT MEMORIES
    if recent_memories:
        parts.append("\n[RECENT_MEMORIES]")
        parts.append(json.dumps(recent_memories, ensure_ascii=False, indent=2))

    # TIMELINE CONTEXT
    if timeline_events:
        parts.append("\n[TIMELINE_CONTEXT]")
        parts.append(json.dumps(timeline_events, ensure_ascii=False, indent=2))

    # IMPORTED MEMORIES (예: 불탄방)
    if imported_memories:
        parts.append("\n[IMPORTED_MEMORIES]")
        parts.append(json.dumps(imported_memories, ensure_ascii=False, indent=2))

    # DIRECTOR MESSAGE (이번 사용자 발화)
    parts.append("\n[DIRECTOR_MESSAGE]")
    parts.append(director_message.strip())

    return "\n".join(parts)
