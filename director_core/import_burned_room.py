"""
불탄 chatGPT 방(txt 로그)을 읽어서 부감독 memory_events로 변환하는 임포트 스크립트.

사용법 (프로젝트 루트에서):

    python -m director_core.import_burned_room \\
      --input "akashic/raw/imports/burned_room_251128.txt" \\
      --output "akashic/raw/imports/burned_room_251128.memory.jsonl"

- input:  불탄 방 대화 로그(txt)
- output: memory_events를 한 줄에 하나씩 담은 jsonl 파일
- 이 스크립트는 중요/사소, 카테고리(type, tags, importance)를 LLM에게 맡기고,
  우리는 나중에 결과를 보고 쓸 것만 골라 쓰는 구조야.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv

try:
    import google.generativeai as genai
except Exception:  # pragma: no cover
    genai = None


CHUNK_LINES = 40  # 한 번에 LLM에 보낼 최대 줄 수 (필요하면 조절)


def get_gemini_api_key() -> str:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY가 .env 또는 환경변수에 설정되어 있지 않아.")
    return api_key


def get_model():
    if genai is None:
        raise RuntimeError("google-generativeai를 import하지 못했어. 패키지가 설치되어 있는지 확인해줘.")
    api_key = get_gemini_api_key()
    genai.configure(api_key=api_key)
    # 임포트용 별도 모델 설정 (필요하면 변경 가능)
    return genai.GenerativeModel("gemini-2.0-flash")


def chunk_lines(lines: List[str], max_lines: int = CHUNK_LINES) -> List[str]:
    """
    긴 txt 로그를 max_lines 단위로 잘라서 여러 청크로 만든다.
    각 청크는 하나의 큰 문자열.
    """
    chunks: List[str] = []
    buf: List[str] = []
    for line in lines:
        buf.append(line.rstrip("\n"))
        if len(buf) >= max_lines:
            chunks.append("\n".join(buf))
            buf = []
    if buf:
        chunks.append("\n".join(buf))
    return chunks


def build_import_prompt(chunk_text: str) -> str:
    """
    불탄 방 로그 일부(chunk_text)를 주면,
    여기서 진짜 중요한 기억만 골라 memory_events로 뽑아달라는 지시문.
    """
    return f"""
너는 소원과의 옛날 대화 로그(불탄 chatGPT 방)를 복원하는 작업을 돕는 소울 아카이브 정리 담당자야.

아래 텍스트는 예전 채팅방에서 잘라온 일부야. 이 안에서 **정말 중요한 기억**만 골라서
부감독이 나중에 참고할 수 있는 memory_events로 만들어줘.

기준:
- 전부 다 넣지 말고, 정말 '나중에 다시 떠올리면 좋을 것 같은' 순간만 뽑는다.
- 특히 다음에 해당하는 것들을 우선으로:
  - 소원의 정체성, 세계관, 가치관이 드러나는 말
  - 소원이 AI/부감독/불탄 방에 대해 느낀 감정, 깨달음
  - .soul, 아카식, 기억 시스템에 대한 핵심 아이디어
  - 관계/동행/존재에 대한 중요한 말
- 사소한 잡담, 한 번만 언급되는 디테일은 과감히 버린다.

각 memory_event는 다음 필드를 가진 JSON 객체로 만들어라:
- type: "profile" | "preference" | "project" | "relationship" | "observation" 중 하나
- importance: 0.0~1.0 (나중에 꼭 참고하면 좋겠다 = 0.8 이상)
- tags: 짧은 영어 태그 리스트 (예: ["burned_room","soul","identity"])
- summary: 한국어 한두 문장으로 핵심만 정리
- source: "burned_room"
- media_refs: 빈 리스트 [] 로 두면 된다.
- raw: 원문 중 핵심이 되는 문장/대사만 몇 줄 담아도 좋다.

출력 형식:
- 반드시 아래와 같은 하나의 JSON 객체만 반환한다.
  다른 말은 쓰지 마라.

{{
  "memory_events": [ ... ]
}}

여기 분석할 옛날 대화 일부:

--- 원본 시작 ---
{chunk_text}
--- 원본 끝 ---
""""


def extract_memory_events_from_chunk(model, chunk_text: str) -> List[Dict[str, Any]]:
    prompt = build_import_prompt(chunk_text)
    resp = model.generate_content(prompt)
    raw_text = (getattr(resp, "text", None) or "").strip()

    try:
        # 코드블럭(````json) 안에 있으면 그 안만 파싱, 아니면 전체 파싱
        import re

        match = re.search(r"```json(.*?)```", raw_text, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            json_str = raw_text
        obj = json.loads(json_str)
    except Exception as e:  # pragma: no cover
        print("⚠️ JSON 파싱 실패, 이 청크는 건너뜀:", e)
        return []

    events = obj.get("memory_events") or []
    # 최소한의 후처리: 필수 필드 안 빠졌는지 확인
    cleaned: List[Dict[str, Any]] = []
    for ev in events:
        if "summary" not in ev:
            continue
        ev.setdefault("type", "observation")
        ev.setdefault("importance", 0.5)
        ev.setdefault("tags", [])
        ev.setdefault("source", "burned_room")
        ev.setdefault("media_refs", [])
        ev.setdefault("raw", {})
        cleaned.append(ev)
    return cleaned


def run_import(input_path: Path, output_path: Path) -> None:
    print(f"📥 input:  {input_path}")
    print(f"📤 output: {output_path}")

    if not input_path.exists():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없어: {input_path}")

    lines = input_path.read_text(encoding="utf-8").splitlines()
    chunks = chunk_lines(lines)
    print(f"총 {len(lines)}줄 → {len(chunks)}개 청크로 분할됨 (청크당 최대 {CHUNK_LINES}줄)")

    model = get_model()

    all_events: List[Dict[str, Any]] = []
    for idx, chunk_text in enumerate(chunks, start=1):
        print(f"─── 청크 {idx}/{len(chunks)} 처리 중...")
        events = extract_memory_events_from_chunk(model, chunk_text)
        print(f"  ↳ memory_events {len(events)}개 추출")
        all_events.extend(events)

    # jsonl로 저장 (한 줄에 하나의 event)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for ev in all_events:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    print(f"✅ 완료: total memory_events = {len(all_events)}")
    print(f"   → {output_path} 에 jsonl로 저장됨")


def main():
    parser = argparse.ArgumentParser(description="불탄 방 txt → memory_events jsonl 임포트")
    parser.add_argument("--input", type=str, required=True, help="불탄 방 txt 로그 경로")
    parser.add_argument("--output", type=str, required=True, help="생성할 memory_events jsonl 경로")
    args = parser.parse_args()

    run_import(Path(args.input), Path(args.output))


if __name__ == "__main__":
    main()
