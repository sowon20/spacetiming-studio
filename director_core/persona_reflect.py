"""
부감독 자기 성격/정책을 점검하고 제안하는 스크립트 (스켈레톤).

TODO:
- portal_history/sowon.chat.jsonl 읽어서 최근 N일 / N줄 요약
- LLM에게 "최근 패턴/실수/좋았던 반응"을 분석하게 하기
- config_updates 형식으로 스타일/정책 변경 제안 받기
- zone A/B/C에 따라 실제 적용/보류/무시 로직 연결
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any


def load_chat_history(path: Path) -> List[Dict[str, Any]]:
    """
    나중에: 포털 chat jsonl 읽어오는 자리.
    지금은 스켈레톤만 남겨둔다.
    """
    # TODO: jsonl 파일 한 줄씩 읽어서 {timestamp, role, content, meta} 형식으로 파싱
    return []


def suggest_persona_updates(chats: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    나중에: LLM 호출해서 config_updates 제안 받는 자리.
    - summary: 최근 대화 패턴 요약
    - config_updates: 부감독이 제안하는 스타일/정책 변경 리스트
    """
    # TODO: director_core.soul_loader / get_gemini_model 재사용해서 호출
    return {
        "summary": "",
        "config_updates": [],
    }


if __name__ == "__main__":
    # 개발 편의를 위한 간단한 엔트리 포인트
    history_path = Path("portal_history/sowon.chat.jsonl")
    chats = load_chat_history(history_path)
    suggestions = suggest_persona_updates(chats)
    print("=== persona reflection suggestion ===")
    print(suggestions)