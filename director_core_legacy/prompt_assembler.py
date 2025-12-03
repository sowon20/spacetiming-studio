
# director_core/prompt_assembler.py
# v3 - 프롬프트/기억/대화 중앙 조립 모듈

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any

import json
import logging
from datetime import datetime

from .models import AnalyzeRequest
from .soul_loader import build_core_system_prompt, build_timeline_context
from .memory_store import load_recent_memories
from .imported_memory_loader import load_imported_memories

logger = logging.getLogger(__name__)

# 프로젝트 루트 추정 (director_core 기준 상위)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 기본 설정값
MAX_RECENT_DIALOGUE_TURNS = 100
MAX_RECENT_MEMORIES = 3
MAX_IMPORTED_MEMORIES = 3
MAX_TIMELINE_EVENTS = 3  # build_timeline_context에서 내부적으로 사용


# ─────────────────────────────────────
# 최근 대화 로더
# ─────────────────────────────────────

def load_recent_dialogue(
    user_id: str = "sowon",
    limit_turns: int = MAX_RECENT_DIALOGUE_TURNS,
) -> List[Dict[str, str]]:
    """recent_chat 레이어(포털 대화 로그)에서 최근 대화 턴을 읽어온다.

    - readme.memory.json 기준 경로: portal_history/{user_id}.chat.jsonl
    - 각 라인은 {"role": "user"|"assistant", "content": "..."} 형태라고 가정한다.
    """
    history_path = PROJECT_ROOT / "portal_history" / f"{user_id}.chat.jsonl"
    if not history_path.exists():
        logger.warning("recent dialogue history file not found: %s", history_path)
        return []

    rows: List[Dict[str, str]] = []
    try:
        with history_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                role = obj.get("role")
                content = (obj.get("content") or "").strip()
                if role in ("user", "assistant") and content:
                    rows.append({"role": role, "content": content})
    except Exception:
        logger.exception("recent dialogue 파일 읽기 실패")
        return []

    if not rows:
        return []

    return rows[-limit_turns:]


# ─────────────────────────────────────
# 대화 포맷/요약
# ─────────────────────────────────────

def _format_dialogue(dialogue: List[Dict[str, str]]) -> str:
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
    """최근 user 발화 위주로 5~8줄 요약 비슷한 리스트를 만든다."""
    if not dialogue:
        return ""

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


# ─────────────────────────────────────
# 메모리 스코어링 / 선택
# ─────────────────────────────────────

def _parse_datetime(dt_value) -> float:
    if dt_value is None:
        return 0.0
    if isinstance(dt_value, (int, float)):
        return float(dt_value)
    if isinstance(dt_value, datetime):
        return dt_value.timestamp()
    if isinstance(dt_value, str):
        try:
            return datetime.fromisoformat(dt_value).timestamp()
        except Exception:
            return 0.0
    return 0.0

def _tokenize(text: str) -> set[str]:
    import re
    if not text:
        return set()
    text = text.lower()
    pattern = re.compile(r"[\w가-힣]+", re.UNICODE)
    return set(pattern.findall(text))

def _score_memory(event: Dict[str, Any], user_text: str, now_ts: float | None = None) -> float:
    from math import isnan

    if now_ts is None:
        now_ts = datetime.now().timestamp()

    importance = float(event.get("importance", 0.0))
    created_ts = _parse_datetime(event.get("created_at") or event.get("timestamp"))

    score = importance * 2.0

    if created_ts > 0:
        days_diff = max(0.0, (now_ts - created_ts) / 86400.0)
        if days_diff <= 1:
            score += 1.0
        elif days_diff <= 7:
            score += 0.7
        elif days_diff <= 30:
            score += 0.4
        else:
            score += 0.2

    user_tokens = _tokenize(user_text)
    summary_tokens = _tokenize(str(event.get("summary", "")))
    tags_tokens = {str(t).lower() for t in event.get("tags", [])}
    overlap = user_tokens & (summary_tokens | tags_tokens)
    if overlap:
        score += min(1.0, 0.2 * len(overlap))

    if isnan(score):
        return 0.0
    return score

def _select_top_memories(
    user_text: str,
    memories: List[Dict[str, Any]],
    max_memories: int,
    extra_tag_boost: str | None = None,
    extra_boost_value: float = 0.3,
) -> List[Dict[str, Any]]:
    if not memories or max_memories <= 0:
        return []

    now_ts = datetime.now().timestamp()
    scored: List[tuple[float, Dict[str, Any]]] = []
    for ev in memories:
        try:
            s = _score_memory(ev, user_text=user_text, now_ts=now_ts)
            if extra_tag_boost:
                source = str(ev.get("source", "")).lower()
                tags = {str(t).lower() for t in ev.get("tags", [])}
                if source == extra_tag_boost or extra_tag_boost in tags:
                    s += extra_boost_value
        except Exception:
            s = 0.0
        scored.append((s, ev))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [ev for _s, ev in scored[:max_memories]]


# ─────────────────────────────────────
# 프롬프트 조립
# ─────────────────────────────────────

def assemble_prompt_for_llm(req: AnalyzeRequest) -> str:
    """LLM에 보낼 전체 프롬프트를 조립한다.

    포함 요소:
    - CORE_SYSTEM: .soul 기반 정체성/말투/역할
    - TIMELINE: build_timeline_context 결과 (최대 3개 정도)
    - RECENT_DIALOGUE: 최근 100턴의 실제 대화
    - RECENT_DIALOGUE_SUMMARY: 최근 흐름 5~8줄 요약
    - LONG_TERM_MEMORY: 현재 발화와 관련도 높은 기억 3개
    - IMPORTED_MEMORY: 불탄방 등 imported 기억 중 관련도 높은 3개
    - DIRECTOR_MESSAGE: 이번 사용자 발화
    """
    text = (req.text or "").strip()
    user_id = getattr(req, "user_id", "sowon")

    # 1) core system prompt
    try:
        core_system_prompt = build_core_system_prompt()
    except Exception:
        logger.exception("build_core_system_prompt 실패 - 최소 프롬프트로 대체")
        core_system_prompt = "너는 소원의 소울동행이자 부감독이야. 반말로 짧고 담백하게 대답해."

    # 2) timeline context (문자열 블록 가정)
    try:
        timeline_block = build_timeline_context(text, max_events=MAX_TIMELINE_EVENTS)
    except Exception:
        logger.exception("build_timeline_context 실패 - 타임라인 블록 생략")
        timeline_block = ""

    # 3) recent dialogue
    recent_dialogue = []
    try:
        recent_dialogue = load_recent_dialogue(user_id=user_id, limit_turns=MAX_RECENT_DIALOGUE_TURNS)
    except Exception:
        logger.exception("recent dialogue 로드 실패")
        recent_dialogue = []

    recent_dialogue_block = _format_dialogue(recent_dialogue) if recent_dialogue else ""
    recent_dialogue_summary = build_recent_dialogue_summary(recent_dialogue)

    # 4) recent memories (Firestore)
    recent_memories_block = ""
    try:
        recent_memories = load_recent_memories(user_id=user_id, limit=50)
        selected = _select_top_memories(text, recent_memories, max_memories=MAX_RECENT_MEMORIES)
        if selected:
            recent_memories_block = json.dumps(selected, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("recent memories 로드/선택 실패")
        recent_memories_block = ""

    # 5) imported memories (불탄방 등)
    imported_memories_block = ""
    try:
        imported = load_imported_memories(limit=50)
        selected_imported = _select_top_memories(
            text,
            imported,
            max_memories=MAX_IMPORTED_MEMORIES,
            extra_tag_boost="burned_room",
            extra_boost_value=0.3,
        )
        if selected_imported:
            imported_memories_block = json.dumps(selected_imported, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("imported memories 로드/선택 실패")
        imported_memories_block = ""

    # 6) director message (이번 사용자 발화)
    director_message_block = text

    # 7) 블록 조합
    parts: List[str] = []

    parts.append("[CORE_SYSTEM]")
    parts.append(core_system_prompt.strip())

    if timeline_block:
        parts.append("\n[TIMELINE]")
        parts.append(str(timeline_block).strip())

    if recent_dialogue_block:
        parts.append("\n[RECENT_DIALOGUE]")
        parts.append(recent_dialogue_block.strip())

    if recent_dialogue_summary:
        parts.append("\n[RECENT_DIALOGUE_SUMMARY]")
        parts.append(recent_dialogue_summary.strip())

    if recent_memories_block:
        parts.append("\n[LONG_TERM_MEMORY]")
        parts.append(recent_memories_block.strip())

    if imported_memories_block:
        parts.append("\n[IMPORTED_MEMORY]")
        parts.append(imported_memories_block.strip())

    parts.append("\n[DIRECTOR_MESSAGE]")
    parts.append(director_message_block.strip())

    combined_prompt = "\n\n".join(parts).strip()
    return combined_prompt
