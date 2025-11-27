import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# -----------------------------
# 기본 설정 / 경로
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent
EPISODES_DIR = BASE_DIR / "episodes"

EPISODES_DIR.mkdir(exist_ok=True, parents=True)

# -----------------------------
# Gemini 세팅 (google-generativeai)
# -----------------------------
try:
    import google.generativeai as genai
except Exception:
    genai = None


def is_gemini_available() -> bool:
    api_key = os.getenv("GEMINI_API_KEY")
    return bool(api_key and genai is not None)

GEMINI_MODEL_NAME = "gemini-2.5-flash"  # 필요시 변경


# -----------------------------
# Pydantic 모델
# -----------------------------
class PromptRequest(BaseModel):
    title: str
    plan: Optional[str] = None


class FeedbackRequest(BaseModel):
    episode_id: str
    verdict: Literal["approved", "revise", "discard"]
    note: Optional[str] = None


class EpisodeFeedback(BaseModel):
    verdict: Literal["approved", "revise", "discard"]
    note: Optional[str] = None
    updated_at: str


class Episode(BaseModel):
    id: str
    created_at: str
    title: str
    plan: Optional[str] = None
    main_prompt: str
    teaser_prompt: Optional[str] = None
    veo_status: str = "pending"
    feedback: Optional[EpisodeFeedback] = None


class EpisodeSummary(BaseModel):
    id: str
    created_at: str
    title: str
    plan: Optional[str] = None
    veo_status: str
    feedback: Optional[EpisodeFeedback] = None


# -----------------------------
# FastAPI 앱 생성
# -----------------------------
app = FastAPI(title="Veo Prompt Agent – Episode Logger")

# CORS (개발 편의를 위해 전체 허용, 필요시 도메인 제한)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# 유틸 함수
# -----------------------------
def generate_episode_id() -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    short = uuid.uuid4().hex[:6]
    return f"{ts}-{short}"


def episode_path(episode_id: str) -> Path:
    return EPISODES_DIR / f"{episode_id}.json"


def load_episode(episode_id: str) -> Episode:
    path = episode_path(episode_id)
    if not path.exists():
        raise FileNotFoundError("episode_not_found")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return Episode(**data)


def save_episode(ep: Episode) -> None:
    path = episode_path(ep.id)
    with path.open("w", encoding="utf-8") as f:
        json.dump(ep.dict(), f, ensure_ascii=False, indent=2)


def call_gemini_for_prompts(title: str, plan: Optional[str]) -> dict:
    """
    Gemini에 요청해서 main_prompt, teaser_prompt 생성.
    - 기본적으로 JSON 응답을 기대
    - 실패 시 전체 텍스트를 main_prompt로 사용
    """
    if not is_gemini_available():
        raise RuntimeError(
            "부감독에게 맡기기를 눌렀을 때 GEMINI_API_KEY 환경변수가 설정되어 있지 않아. 로컬 환경변수 설정을 확인해줘."
        )

    system_prompt = """
You are the Veo prompt-writing assistant for Space-Timing Studio.
Your job: given a video title and a short plan/mood, output JSON for two fields:
- main_prompt: a detailed English prompt for Google Veo (cinematic, spiritual, cosmic tone).
- teaser_prompt: a short English prompt for a 10–20s teaser version.

Respond ONLY in valid JSON, with this exact shape:
{
  "main_prompt": "...",
  "teaser_prompt": "..."
}
"""

    user_prompt = f"""
Video title: {title}
Plan / mood / intent: {plan or "(none provided)"}

Write cinematic prompts that match this director's style:
- Spiritual, cosmic, dreamlike
- Emotional but not cheesy
- Clear visual progression
"""

    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    response = model.generate_content(
        [{"role": "user", "parts": [system_prompt + "\n\n" + user_prompt]}]
    )

    text = response.text if hasattr(response, "text") else str(response)

    # JSON 파싱 시도
    main_prompt = text
    teaser_prompt = None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            main_prompt = parsed.get("main_prompt") or text
            teaser_prompt = parsed.get("teaser_prompt")
    except Exception:
        # 그냥 텍스트 전체를 main_prompt로 사용
        main_prompt = text
        teaser_prompt = None

    return {
        "main_prompt": main_prompt.strip(),
        "teaser_prompt": teaser_prompt.strip() if isinstance(teaser_prompt, str) else None,
    }


# -----------------------------
# 엔드포인트들
# -----------------------------
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "episodes_dir": str(EPISODES_DIR),
        "gemini_available": is_gemini_available(),
    }


@app.post("/veo/prompt")
def create_prompt(req: PromptRequest):
    try:
        prompts = call_gemini_for_prompts(req.title, req.plan)
    except Exception as e:
        return {
            "ok": False,
            "error": f"Gemini 호출 중 오류: {e}",
        }

    episode_id = generate_episode_id()
    created_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    episode = Episode(
        id=episode_id,
        created_at=created_at,
        title=req.title,
        plan=req.plan,
        main_prompt=prompts["main_prompt"],
        teaser_prompt=prompts.get("teaser_prompt"),
        veo_status="pending",
        feedback=None,
    )

    save_episode(episode)

    return {
        "ok": True,
        "episode_id": episode_id,
        "main_prompt": episode.main_prompt,
        "teaser_prompt": episode.teaser_prompt,
    }


@app.post("/veo/feedback")
def attach_feedback(req: FeedbackRequest):
    try:
        episode = load_episode(req.episode_id)
    except FileNotFoundError:
        return {"ok": False, "error": "episode_not_found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # verdict 검증은 Pydantic Literal이 이미 해줌
    updated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    feedback = EpisodeFeedback(
        verdict=req.verdict,
        note=req.note,
        updated_at=updated_at,
    )
    episode.feedback = feedback

    if req.verdict == "approved":
        episode.veo_status = "approved"
    elif req.verdict == "revise":
        episode.veo_status = "needs_revision"
    elif req.verdict == "discard":
        episode.veo_status = "discarded"

    save_episode(episode)

    return {"ok": True}


@app.get("/veo/episodes/recent")
def list_recent_episodes(limit: int = Query(5, ge=1, le=50)):
    files: List[Path] = sorted(
        EPISODES_DIR.glob("*.json"),
        key=lambda p: p.stem,
        reverse=True,
    )

    items: List[EpisodeSummary] = []
    for path in files[:limit]:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            ep = Episode(**data)
            summary = EpisodeSummary(
                id=ep.id,
                created_at=ep.created_at,
                title=ep.title,
                plan=ep.plan,
                veo_status=ep.veo_status,
                feedback=ep.feedback,
            )
            items.append(summary)
        except Exception:
            # 깨진 파일은 그냥 스킵
            continue

    return {
        "ok": True,
        "items": [item.dict() for item in items],
    }