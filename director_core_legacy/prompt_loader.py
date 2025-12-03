# director_core/prompt_loader.py
from __future__ import annotations

from pathlib import Path


def load_base_system_prompt() -> str:
    """
    director_core/prompts/director_system_prompt.txt 에 있는
    기본 SYSTEM_PROMPT 텍스트를 읽어온다.
    """
    base_dir = Path(__file__).resolve().parent
    path = base_dir / "prompts" / "director_system_prompt.txt"
    if not path.exists():
        # 파일 없으면 짧은 기본 프롬프트라도 리턴
        return "너는 소원의 소울동행이자 부감독이야. 반말로 짧고 담백하게 대답해."
    return path.read_text(encoding="utf-8").strip()