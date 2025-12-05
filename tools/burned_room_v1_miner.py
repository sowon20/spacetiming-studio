"""
burned_room_v1_miner.py

불탄방 기억을 지금 사용하는 v1 포맷에 맞는 조각들로 자동 변환하는 작은 툴.

지원 모드:
- v0: 기존 JSONL 요약(`burned_room_251128.memory.jsonl`)을 v1 포맷으로 재포장
- txt: 통짜 TXT(`burned_room_251128.txt`)를 잘게 쪼개서 v1 포맷의 episode 조각으로 변환

⚠️ 중요한 점
- 이 스크립트는 기존 v1 메모리 파일을 직접 수정하지 않는다.
- 기본값으로는 `assistant/memory/burned_room.v1.mined.jsonl` (v0 모드) 에 append 한다.
- txt 모드일 때는 --output 옵션으로 별도 파일을 지정하는 걸 추천한다.
  예: assistant/memory/burned_room.v1.txtmicro.jsonl

사용법 (맥/라즈베리 공통, venv 활성화 후):

    cd ~/spacetiming-studio

    # v0 JSONL 기반 후보 생성
    python tools/burned_room_v1_miner.py --mode v0 --limit 200 --min-importance 0.6

    # 통짜 TXT 기반 미세 조각 생성
    python tools/burned_room_v1_miner.py --mode txt --limit 100000 \
        --output assistant/memory/burned_room.v1.txtmicro.jsonl

"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# v0 / txt / v1 경로 (현재 레포 기준)
ROOT = Path(__file__).resolve().parents[1]
V0_PATH = ROOT / "akashic" / "raw" / "imports" / "burned_room_251128.memory.jsonl"
TXT_PATH = ROOT / "akashic" / "raw" / "imports" / "burned_room_251128.txt"
V1_MINED_PATH = ROOT / "assistant" / "memory" / "burned_room.v1.mined.jsonl"


# --------------------
# 공통 유틸
# --------------------
def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    """단순 JSONL 로더. 잘못된 줄은 건너뛴다."""
    if not path.exists():
        print(f"[warn] JSONL 파일이 없음: {path}")
        return

    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    yield obj
                else:
                    print(f"[warn] {path.name}:{lineno} dict가 아님, 건너뜀")
            except json.JSONDecodeError:
                print(f"[warn] {path.name}:{lineno} JSON 파싱 실패, 건너뜀")


def append_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> None:
    """JSONL 파일에 레코드들을 append 한다. 파일이 없으면 새로 만든다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for rec in records:
            line = json.dumps(rec, ensure_ascii=False)
            f.write(line + "\n")


# --------------------
# v0(JSONL) → v1 후보
# --------------------
def should_pick_v0(record: Dict[str, Any], min_importance: float) -> bool:
    """v0 기록을 v1 후보로 쓸지 여부를 간단히 결정하는 필터."""
    if record.get("type") == "meta":
        return False

    importance = record.get("importance")
    try:
        if importance is not None:
            importance = float(importance)
    except (TypeError, ValueError):
        importance = None

    if importance is not None and importance < min_importance:
        return False

    return True


def to_v1_candidate_from_v0(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    v0 레코드(dict)를 v1 포맷 후보(dict)로 변환한다.

    v0 스키마가 정확히 어떻게 되어 있는지 몰라도,
    최대한 안전하게 field 들을 추론해서 매핑한다.
    """
    r_type: str = str(record.get("type") or "note")
    importance = record.get("importance")
    try:
        importance_f = float(importance) if importance is not None else 0.5
    except (TypeError, ValueError):
        importance_f = 0.5

    tags = record.get("tags") or []
    if not isinstance(tags, list):
        tags = [str(tags)]
    # v1 후보임을 표시
    if "burned_room" not in tags:
        tags.append("burned_room")
    if "v1_candidate" not in tags:
        tags.append("v1_candidate")
    if "v0_source" not in tags:
        tags.append("v0_source")

    # summary 후보 찾기
    summary: Optional[str] = None
    for key in ("summary", "title", "topic", "headline"):
        val = record.get(key)
        if isinstance(val, str) and val.strip():
            summary = val.strip()
            break

    # raw 후보 찾기
    raw: Optional[str] = None
    for key in ("raw", "full_text", "original", "content"):
        val = record.get(key)
        if isinstance(val, str) and val.strip():
            raw = val.strip()
            break

    # 둘 다 없으면, 최소한 summary라도 만들기
    if summary is None and raw is not None:
        # 너무 길면 앞쪽만 잘라서 summary로
        summary = raw[:180] + ("…" if len(raw) > 180 else "")
    if summary is None:
        summary = f"[{r_type}] burned_room v0 레코드 자동 변환 (내용 없음)"

    if raw is None:
        raw = summary

    media_refs = record.get("media_refs")
    if not isinstance(media_refs, list):
        media_refs = []

    return {
        "type": r_type,
        "importance": round(importance_f, 3),
        "tags": tags,
        "summary": summary,
        "source": "burned_room.v1.mined",
        "media_refs": media_refs,
        "raw": raw,
    }


def mine_from_v0(
    limit: Optional[int] = None,
    min_importance: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    v0 파일에서 조건에 맞는 레코드를 골라,
    v1 포맷의 후보 레코드 리스트를 만든다.
    """
    results: List[Dict[str, Any]] = []
    count = 0

    for rec in iter_jsonl(V0_PATH):
        if not should_pick_v0(rec, min_importance=min_importance):
            continue

        v1_rec = to_v1_candidate_from_v0(rec)
        results.append(v1_rec)
        count += 1

        if limit is not None and count >= limit:
            break

    return results


# --------------------
# TXT 원본 → v1 episode 조각
# --------------------
def iter_txt_blocks(path: Path) -> Iterable[str]:
    """
    TXT 파일을 빈 줄 기준으로 문단 블록으로 나눈다.
    너무 짧은 줄들은 자연스럽게 윗/아랫줄과 합쳐진다.
    """
    if not path.exists():
        print(f"[warn] TXT 파일이 없음: {path}")
        return

    with path.open("r", encoding="utf-8") as f:
        buffer_lines: List[str] = []
        for line in f:
            # 개행 제거 (원문 느낌을 살리고 싶으면 나중에 조정 가능)
            stripped = line.rstrip("\n")
            if stripped.strip() == "":
                # 빈 줄 → 블록 경계
                if buffer_lines:
                    block = "\n".join(buffer_lines).strip()
                    if block:
                        yield block
                    buffer_lines = []
            else:
                buffer_lines.append(stripped)

        # 파일 끝에 남은 블록
        if buffer_lines:
            block = "\n".join(buffer_lines).strip()
            if block:
                yield block


def chunk_blocks(
    blocks: Iterable[str],
    max_chars: int = 800,
    min_chunk_chars: int = 200,
) -> Iterable[str]:
    """
    문단 블록들을 받아서, max_chars를 넘지 않는 선에서 적당히 합쳐 chunk를 만든다.
    너무 짧은 chunk는 다음 블록과 합쳐서 min_chunk_chars 이상이 되도록 시도한다.
    """
    current: List[str] = []
    current_len = 0

    for block in blocks:
        block_len = len(block)

        # 현재 chunk에 이 블록을 붙여도 크게 무리 없으면 그냥 붙이기
        if current and current_len + 1 + block_len <= max_chars:
            current.append(block)
            current_len += 1 + block_len  # 개행 포함
            continue

        # 현재 chunk가 비어있으면, 이 블록을 바로 chunk로 내보내거나 자를 수도 있음
        if not current:
            if block_len <= max_chars:
                current.append(block)
                current_len = block_len
            else:
                # 한 블록이 너무 긴 경우, 그냥 잘라서 보낸다.
                start = 0
                while start < block_len:
                    end = min(start + max_chars, block_len)
                    yield block[start:end].strip()
                    start = end
                current = []
                current_len = 0
            continue

        # 여기까지 왔으면, 현재 chunk를 먼저 내보내고 새로 시작
        if current_len >= min_chunk_chars:
            yield "\n\n".join(current).strip()
            current = [block]
            current_len = block_len
        else:
            # current가 너무 짧은데 새 블록까지 붙이면 너무 길어질 경우,
            # 그냥 합쳐서 하나의 chunk로 보낸다.
            current.append(block)
            current_len += 1 + block_len
            if current_len > max_chars:
                yield "\n\n".join(current).strip()
                current = []
                current_len = 0

    if current:
        yield "\n\n".join(current).strip()


def make_summary_from_chunk(chunk: str, max_len: int = 160) -> str:
    """
    chunk에서 요약용 한 줄을 만든다.
    - 첫 문장/첫 줄 위주로,
    - 너무 길면 잘라낸다.
    """
    text = chunk.strip()

    # 첫 줄 기준으로 자르기
    first_line = text.split("\n", 1)[0].strip()
    candidate = first_line if first_line else text

    if len(candidate) > max_len:
        return candidate[:max_len] + "…"
    return candidate


def to_v1_candidate_from_txt(chunk: str, index: int) -> Dict[str, Any]:
    """TXT에서 나온 chunk 문자열을 v1 episode 레코드로 변환한다."""
    summary = make_summary_from_chunk(chunk)
    tags = ["burned_room", "txt_slice", "v1_txt"]
    return {
        "type": "episode",
        "importance": 0.5,
        "tags": tags,
        "summary": summary,
        "source": "burned_room.v1.txtmicro",
        "media_refs": [],
        "raw": chunk,
    }


def mine_from_txt(
    limit: Optional[int] = None,
    max_chars: int = 800,
    min_chunk_chars: int = 200,
) -> List[Dict[str, Any]]:
    """
    TXT 원본에서 episode 조각들을 만들어 v1 포맷 리스트로 반환한다.
    """
    blocks = iter_txt_blocks(TXT_PATH)
    chunks = chunk_blocks(blocks, max_chars=max_chars, min_chunk_chars=min_chunk_chars)

    results: List[Dict[str, Any]] = []
    count = 0

    for idx, chunk in enumerate(chunks):
        v1_rec = to_v1_candidate_from_txt(chunk, index=idx)
        results.append(v1_rec)
        count += 1
        if limit is not None and count >= limit:
            break

    return results


# --------------------
# main
# --------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="불탄방 v0/텍스트를 v1 포맷 후보로 자동 변환하는 작은 툴",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["v0", "txt"],
        default="v0",
        help="변환 모드: v0(JSONL 기반) 또는 txt(통짜 TXT 기반)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="최대 생성 레코드 수 (기본: 50)",
    )
    parser.add_argument(
        "--min-importance",
        type=float,
        default=0.0,
        help="(v0 모드 전용) importance 최소값 필터 (기본: 0.0, 즉 전체)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(V1_MINED_PATH),
        help="결과를 쓸 JSONL 경로 (기본: assistant/memory/burned_room.v1.mined.jsonl)",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=800,
        help="(txt 모드 전용) 한 chunk 최대 문자 수 (기본: 800)",
    )
    parser.add_argument(
        "--min-chunk-chars",
        type=int,
        default=200,
        help="(txt 모드 전용) 한 chunk 최소 목표 문자 수 (기본: 200)",
    )

    args = parser.parse_args()
    out_path = Path(args.output)

    if args.mode == "v0":
        print(f"[info] mode=v0, v0 from: {V0_PATH}")
        print(f"[info] output to: {out_path}")
        print(f"[info] limit={args.limit}, min_importance={args.min_importance}")

        candidates = mine_from_v0(
            limit=args.limit,
            min_importance=args.min_importance,
        )
    else:
        print(f"[info] mode=txt, txt from: {TXT_PATH}")
        print(f"[info] output to: {out_path}")
        print(f"[info] limit={args.limit}, max_chars={args.max_chars}, min_chunk_chars={args.min_chunk_chars}")

        candidates = mine_from_txt(
            limit=args.limit,
            max_chars=args.max_chars,
            min_chunk_chars=args.min_chunk_chars,
        )

    if not candidates:
        print("[info] 조건에 맞는 레코드가 없습니다.")
        return

    append_jsonl(out_path, candidates)
    print(f"[done] {len(candidates)}개 레코드를 {out_path} 에 추가했습니다.")


if __name__ == "__main__":
    main()
