from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any


"""부감독용 최근 대화 맥락 엔진 (v1).

main.py 에서:

    from director_core.recent_context import RecentContext

로 import 해서 사용한다.

역할:
- 최근 대화  N 턴을 JSON 파일에 저장
- LLM 호출 전에 recent_messages 리스트로 건네주기
"""


BASE_DIR = Path(__file__).resolve().parent.parent  # project root (spacetiming-studio)
STORAGE_DIR = BASE_DIR / "director_server_v1" / "storage"
STORAGE_PATH = STORAGE_DIR / "recent_context.json"


class RecentContext:
    """최근 대화 컨텍스트 관리 클래스.

    messages: [{"role": "user"|"assistant", "content": "..."}]
    """

    def __init__(self, max_turns: int = 32) -> None:
        self.max_turns = max_turns
        self.messages: List[Dict[str, Any]] = []

    # ---- 로드 / 세이브 ----

    def load(self) -> None:
        """JSON 파일에서 최근 대화를 불러온다."""
        if not STORAGE_PATH.exists():
            self.messages = []
            return
        try:
            data = json.loads(STORAGE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self.messages = data
            else:
                self.messages = []
        except Exception:
            self.messages = []

    def save(self) -> None:
        """최근 대화를 JSON 파일로 저장한다."""
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            STORAGE_PATH.write_text(
                json.dumps(self.messages, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            # 저장 실패해도 서버가 죽지는 않게.
            pass

    # ---- 조작 메서드 ----

    def add(self, role: str, content: str) -> None:
        """새 메시지를 추가하고, max_turns만큼만 유지."""
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > self.max_turns:
            self.messages = self.messages[-self.max_turns :]

    def clear(self) -> None:
        """전체 로그 초기화 (이 순간부터 다시 시작용)."""
        self.messages = []
        try:
            if STORAGE_PATH.exists():
                STORAGE_PATH.unlink()
        except Exception:
            pass

    # ---- 조회 ----

    def to_list(self) -> List[Dict[str, Any]]:
        """LLM 프롬프트용 리스트 반환."""
        return list(self.messages)
