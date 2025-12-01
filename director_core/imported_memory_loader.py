from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)

# 프로젝트 루트 기준: akashic/raw/imports/...
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BURNED_ROOM_MEMORY_PATH = PROJECT_ROOT / "akashic" / "raw" / "imports" / "burned_room_251128.memory.jsonl"


def load_imported_memories(limit: int = 30) -> List[Dict[str, Any]]:
    """
    불탄 chatGPT 방에서 추출한 memory_events jsonl 파일을 읽어서
    importance 높은 것부터 최대 limit개까지 반환한다.
    파일이 없거나 에러 나면 그냥 빈 리스트.
    """
    try:
        path = BURNED_ROOM_MEMORY_PATH
        if not path.exists():
            return []

        events: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    # 한 줄 깨져 있으면 조용히 버리고 계속 진행
                    logger.exception("불탄방 memory_events jsonl 한 줄 파싱 실패, 무시하고 계속 진행")
                    continue
                # 최소 summary 없는 건 버린다
                if "summary" not in obj:
                    continue
                events.append(obj)

        # importance 기준으로 정렬 (없으면 0으로 간주)
        events.sort(key=lambda e: float(e.get("importance", 0.0)), reverse=True)

        # type / source 기본값 보정
        trimmed: List[Dict[str, Any]] = []
        for ev in events[:limit]:
            ev = dict(ev)
            ev.setdefault("type", "observation")
            ev.setdefault("source", "burned_room")
            trimmed.append(ev)

        return trimmed

    except Exception:
        logger.exception("불탄방 imported memories 로드 중 에러, 빈 리스트 반환")
        return []