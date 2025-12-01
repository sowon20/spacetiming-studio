
# director_core/memory_selection_v2.py
"""기억 선택/정렬 전용 로직 v2

- 기존 Firestore/JSONL 로딩 로직은 건드리지 않고,
  이 모듈은 **이미 로드된 메모리 리스트를 어떻게 골라 쓸지**만 책임진다.
- user_text(이번 사용자 발화)를 기준으로:
  importance / 최근성 / 키워드 겹침 정도를 종합해서 점수를 매긴다.
- 최종적으로 상위 N개만 반환한다.
"""

from __future__ import annotations

from typing import List, Dict, Any
from datetime import datetime
import math
import re


def _parse_datetime(dt_value) -> float:
    """datetime 혹은 문자열을 UNIX timestamp(float)로 변환한다.

    실패하면 0.0을 반환한다.
    """
    if dt_value is None:
        return 0.0

    if isinstance(dt_value, (int, float)):
        return float(dt_value)

    if isinstance(dt_value, datetime):
        return dt_value.timestamp()

    if isinstance(dt_value, str):
        # ISO8601 비슷한 형태들을 대충 처리
        try:
            return datetime.fromisoformat(dt_value).timestamp()
        except Exception:
            pass

    return 0.0


_token_pattern = re.compile(r"[\w가-힣]+", re.UNICODE)


def _tokenize(text: str) -> set[str]:
    if not text:
        return set()
    text = text.lower()
    return set(_token_pattern.findall(text))


def score_memory(event: Dict[str, Any], user_text: str, now_ts: float | None = None) -> float:
    """단일 메모리에 점수를 매긴다.

    - importance: 0.0 ~ 1.0 정도라고 가정하고 가중치 2배
    - recency: 최근일수록 가산점
    - keyword overlap: user_text와 summary/tags 겹치는 정도
    """
    if now_ts is None:
        now_ts = datetime.now().timestamp()

    importance = float(event.get("importance", 0.0))
    created_ts = _parse_datetime(event.get("created_at") or event.get("timestamp"))

    # base: importance
    score = importance * 2.0

    # recency: 최대 +1.0 정도
    if created_ts > 0:
        # 최근 7일 이내면 큰 가산점, 그 이후로는 천천히 감소
        days_diff = max(0.0, (now_ts - created_ts) / 86400.0)
        if days_diff <= 1:
            score += 1.0
        elif days_diff <= 7:
            score += 0.7
        elif days_diff <= 30:
            score += 0.4
        else:
            score += 0.2

    # keyword overlap
    user_tokens = _tokenize(user_text)
    summary_tokens = _tokenize(str(event.get("summary", "")))
    tags_tokens = {str(t).lower() for t in event.get("tags", [])}

    overlap_tokens = user_tokens & (summary_tokens | tags_tokens)
    if overlap_tokens:
        # 겹치는 토큰 수에 따라 0.2 ~ 1.0 정도 가산
        score += min(1.0, 0.2 * len(overlap_tokens))

    return score


def select_top_memories(
    user_text: str,
    memories: List[Dict[str, Any]],
    max_memories: int = 3,
) -> List[Dict[str, Any]]:
    """일반 메모리 리스트에서 상위 N개를 고른다."""
    if not memories or max_memories <= 0:
        return []

    now_ts = datetime.now().timestamp()

    scored = []
    for ev in memories:
        try:
            s = score_memory(ev, user_text=user_text, now_ts=now_ts)
        except Exception:
            s = 0.0
        scored.append((s, ev))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [ev for _score, ev in scored[:max_memories]]


def select_top_imported_memories(
    user_text: str,
    memories: List[Dict[str, Any]],
    max_memories: int = 3,
) -> List[Dict[str, Any]]:
    """불탄방 등 imported memories 중에서 상위 N개를 고른다.

    - 기본 score_memory를 사용하되,
      source == "burned_room" 이거나 "burned_room" 태그가 있는 경우
      약간 더 가산점(+0.3) 부여.
    """
    if not memories or max_memories <= 0:
        return []

    now_ts = datetime.now().timestamp()

    scored = []
    for ev in memories:
        try:
            s = score_memory(ev, user_text=user_text, now_ts=now_ts)
            source = str(ev.get("source", "")).lower()
            tags = {str(t).lower() for t in ev.get("tags", [])}
            if source == "burned_room" or "burned_room" in tags:
                s += 0.3
        except Exception:
            s = 0.0
        scored.append((s, ev))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [ev for _score, ev in scored[:max_memories]]
