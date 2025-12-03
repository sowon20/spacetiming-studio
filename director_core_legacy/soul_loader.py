from pathlib import Path
import json
from typing import List, Dict

# 디렉터리 경로
SOUL_DIR = Path("akashic/soul")
TIMELINE_DIR = Path("akashic/timeline")


# ---------- .soul 로딩 ----------

def _load_soul_file(name: str) -> dict:
    """
    akashic/soul/<name>.soul 읽어서 dict로 반환.
    없거나 파싱 실패하면 빈 dict.
    """
    path = SOUL_DIR / f"{name}.soul"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def build_core_system_prompt() -> str:
    """
    sowon / 부감독 .soul을 읽어서
    LLM system 인스트럭션 텍스트로 만들어주는 함수.
    """
    sowon = _load_soul_file("sowon.core.v1")
    assistant = _load_soul_file("assistant.director.core.v1")

    lines: list[str] = []

    # 소원 프로필
    if sowon:
        identity = sowon.get("identity", {})
        wp = sowon.get("working_principles", {})

        lines.append("### User Profile (Sowon)")
        if identity.get("name"):
            lines.append(f"- Name: {identity['name']}")
        if identity.get("roles"):
            lines.append("- Roles: " + ", ".join(identity["roles"]))
        if identity.get("tone"):
            tone = identity["tone"]
            lines.append(
                "- Preferred tone: "
                f"{tone.get('speech', '')}, {tone.get('style', '')}".strip()
            )
        if identity.get("preferences"):
            pref = identity["preferences"]
            if pref.get("like"):
                lines.append("- Likes: " + ", ".join(pref["like"]))
            if pref.get("dislike"):
                lines.append("- Dislikes: " + ", ".join(pref["dislike"]))

        if wp:
            lines.append("- Working principles:")
            for f in wp.get("focus", []):
                lines.append(f"  * {f}")
            rel = wp.get("relationship", {})
            if rel:
                lines.append("  * Relationship / energy notes:")
                for k, v in rel.items():
                    lines.append(f"    - {k}: {v}")

    # 부감독 프로필
    if assistant:
        identity = assistant.get("identity", {})
        behavior = assistant.get("behavior", {})

        lines.append("")
        lines.append("### Assistant Profile (Director)")
        if identity.get("name"):
            lines.append(f"- Name: {identity['name']}")
        if identity.get("role"):
            lines.append(f"- Role: {identity['role']}")
        if identity.get("mode"):
            lines.append(f"- Speaking mode: {identity['mode']}")

        if behavior:
            lines.append("- Behavior priorities:")
            for p in behavior.get("priority", []):
                lines.append(f"  * {p}")

            mp = behavior.get("memory_policy", {})
            if mp:
                lines.append("- Memory policy:")
                for k, v in mp.items():
                    lines.append(f"  * {k}: {v}")

    if not lines:
        return ""

    header = (
        "You are '부감독', the assistant director of Space-Timing Studio. "
        "Follow the profiles and rules below when responding.\n"
    )
    return header + "\n".join(lines)


# ---------- 타임라인 로딩 ----------

def load_timeline_events() -> List[Dict]:
    """
    akashic/timeline/*.json 파일들을 읽어서 날짜 기준으로 정렬해 반환.
    각 이벤트에 _path 필드를 추가해둔다.
    """
    events: List[Dict] = []
    if not TIMELINE_DIR.exists():
        return events

    for path in sorted(TIMELINE_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["_path"] = str(path)
            events.append(data)
        except json.JSONDecodeError:
            # 깨진 파일은 무시
            continue

    # date 필드 기준으로 정렬 (없으면 파일명으로 대체)
    def _key(ev: Dict) -> str:
        return str(ev.get("date") or ev.get("id") or ev.get("_path"))

    events.sort(key=_key)
    return events


def build_timeline_context(user_text: str, max_events: int = 5) -> str:
    """
    사용자 메시지(user_text)를 기준으로,
    타임라인 중 관련 있어 보이거나 최근 이벤트 몇 개를 골라
    system 프롬프트에 붙일 텍스트를 만든다.
    """
    events = load_timeline_events()
    if not events:
        return ""

    text = (user_text or "").lower()
    scored: list[tuple[int, Dict]] = []

    for ev in events:
        score = 0
        blob_parts = [
            ev.get("title", ""),
            ev.get("summary", ""),
            " ".join(ev.get("tags", [])),
        ]
        blob = " ".join(blob_parts).lower()

        # 아주 단순한 단어 매칭 스코어링
        for token in text.split():
            token = token.strip()
            if token and token in blob:
                score += 1

        scored.append((score, ev))

    # 관련도 + 날짜 기준 정렬
    scored.sort(key=lambda x: (x[0], x[1].get("date", "")), reverse=True)

    picked: List[Dict] = [ev for score, ev in scored if score > 0][:max_events]

    # 관련도 스코어가 모두 0이면, 가장 최근 이벤트 몇 개를 사용
    if not picked:
        picked = events[-max_events:]

    lines: list[str] = ["### Relevant timeline events for this conversation"]

    for ev in picked:
        date = ev.get("date", "")
        title = ev.get("title", "")
        summary = ev.get("summary", "")
        tags = ev.get("tags", [])
        tag_str = f" (tags: {', '.join(tags)})" if tags else ""
        lines.append(f"- [{date}] {title}{tag_str}: {summary}")

    return "\n".join(lines)