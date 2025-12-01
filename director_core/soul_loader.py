from pathlib import Path
import json

SOUL_DIR = Path("akashic/soul")


def _load_soul_file(name: str) -> dict:
    """
    akashic/soul/<name>.soul 읽어서 dict로 반환.
    없으면 빈 dict.
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