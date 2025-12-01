from pathlib import Path
from datetime import datetime, timedelta
import re
import json

# 프로젝트 루트 기준
BASE_DIR = Path(__file__).resolve().parent

# 불탄방 정리본 위치 (맥)
IMPORT_FILE = BASE_DIR / "akashic" / "raw" / "imports" / "burned_room_251128.txt"

# 포털 히스토리 위치
HISTORY_DIR = BASE_DIR / "portal_history"
HISTORY_FILE = HISTORY_DIR / "sowon.chat.jsonl"
BACKUP_FILE = HISTORY_DIR / "sowon.chat.backup.before_import.jsonl"


def parse_segments(text: str):
    """
    [소원] / [부감독] 기준으로 블록 나누기.
    """
    pattern = re.compile(r"\[(소원|부감독)\]\s*")
    segments = []

    matches = list(pattern.finditer(text))
    for idx, match in enumerate(matches):
        role_kr = match.group(1)
        start = match.end()
        if idx + 1 < len(matches):
            end = matches[idx + 1].start()
        else:
            end = len(text)
        body = text[start:end].strip()
        if not body:
            continue
        segments.append((role_kr, body))

    return segments


def main():
    if not IMPORT_FILE.exists():
        print(f"[import] 불탄방 파일을 찾을 수 없음: {IMPORT_FILE}")
        return

    HISTORY_DIR.mkdir(exist_ok=True)

    print(f"[import] 소스 파일: {IMPORT_FILE}")
    text = IMPORT_FILE.read_text(encoding="utf-8")

    segments = parse_segments(text)
    print(f"[import] 대화 블록 개수: {len(segments)}")

    # 기존 포털 히스토리 백업
    existing_lines = []
    if HISTORY_FILE.exists():
        existing_lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
        HISTORY_FILE.rename(BACKUP_FILE)
        print(f"[import] 기존 히스토리 백업: {BACKUP_FILE.name}")
    else:
        print("[import] 기존 히스토리 없음 (새로 생성)")

    # 불탄방 대화를 과거 날짜로 쌓기 (예: 2025-11-26 기준)
    base_dt = datetime(2025, 11, 26, 0, 0, 0)

    with HISTORY_FILE.open("w", encoding="utf-8") as f:
        for i, (role_kr, body) in enumerate(segments):
            ts = base_dt + timedelta(seconds=i)
            ts_str = ts.isoformat(timespec="seconds")

            role = "user" if role_kr == "소원" else "assistant"

            entry = {
                "id": f"{ts_str}_{role}",
                "user_id": "sowon",
                "role": role,
                "text": body,
                "timestamp": ts_str,
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # 불탄방 뒤에, 지금까지 포털에서 쌓인 대화들도 이어붙이기
        for line in existing_lines:
            f.write(line.rstrip("\n") + "\n")

    print(f"[import] 이식 완료.")
    print(f"[import] 새 히스토리 파일: {HISTORY_FILE}")
    print(f"[import] 총 이식된 메시지 수: {len(segments)}")


if __name__ == "__main__":
    main()