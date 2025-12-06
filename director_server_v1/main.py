from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from director_core.prompt_assembler import assemble_director_prompt
from director_core.recent_context import RecentContext

import os
from pathlib import Path
import google.generativeai as genai
from PIL import Image as PILImage

UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT", "/mnt/sowon_cloud/chat_uploads")).resolve()
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")  # 실제 모델 이름에 맞게 수정 가능
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY env가 필요해요.")

genai.configure(api_key=GEMINI_API_KEY)
_model = genai.GenerativeModel(GEMINI_MODEL)


def call_model(system_prompt: str) -> str:
    """Gemini Flash 2.0 한 번 호출해서 텍스트만 꺼내오는 자리."""
    resp = _model.generate_content(system_prompt)
    # resp.text 있으면 그거, 아니면 파트들 합쳐서 반환
    if getattr(resp, "text", None):
        return resp.text
    try:
        return "".join(
            part.text
            for part in resp.candidates[0].content.parts
            if hasattr(part, "text")
        )
    except Exception:
        return "부감독: 응답 파싱 중 에러가 나서 원문을 보여주진 못했어."


app = FastAPI(title="Spacetime Director Core")


class ChatMessage(BaseModel):
    role: str
    content: str


class AttachmentMeta(BaseModel):
    name: str
    type: Optional[str] = None
    size: Optional[int] = None
    url: Optional[str] = None
    server_path: Optional[str] = None


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    attachments: Optional[List[AttachmentMeta]] = None
    upload_profile: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str


@app.post("/chat")
async def chat(req: "ChatRequest"):
    """
    director_core recent_context + 부감독 프롬프트 + Gemini 호출
    """
    # 첨부 파일 메타정보는 req.attachments 로 들어온다.
    # assemble_director_prompt 호출 시 attachments 인자로 넘겨서,
    # 프롬프트 상단에 [첨부 파일 정보] 블럭으로 간단히 요약해 준다.
    # 1) 최근 대화 컨텍스트 로드/업데이트
    ctx = RecentContext()
    ctx.load()

    for m in req.messages:
        ctx.add(m.role, m.content)

    ctx.save()

    # 2) 프롬프트에 넣을 최근 대화 뽑기
    recent_for_prompt = ctx.extract_for_prompt(max_turns=32)
    user_input = req.messages[-1].content if req.messages else ""

    # 3) 부감독 인격 프롬프트 조립
    final_prompt = assemble_director_prompt(
        recent_messages=recent_for_prompt,
        user_input=user_input,
        max_recent=32,
        attachments=[a.model_dump() for a in (req.attachments or [])] or None,
    )

    # 4) Gemini 호출 (이미지가 있으면 함께 넘김)
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)

        image_parts = []
        for att in req.attachments or []:
            # 1) 이 첨부가 이미지인지 판별 (MIME type 또는 확장자 기반)
            name_lower = (att.name or "").lower()
            is_ext_image = name_lower.endswith(
                (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".bmp")
            )
            is_type_image = bool(att.type and att.type.startswith("image/"))
            if not (is_type_image or is_ext_image):
                continue

            candidate_paths = []

            # (a) url 기반 경로 추출
            if att.url:
                rel = att.url.lstrip("/")  # "/uploads/..." 또는 "uploads/..."
                img_rel = Path(rel)

                if str(img_rel).startswith("uploads/"):
                    try:
                        img_rel = img_rel.relative_to("uploads")  # "local_default/IMG_3001.jpeg"
                    except ValueError:
                        img_rel = Path(str(img_rel)[len("uploads/"):])
                    candidate_paths.append(UPLOAD_ROOT / img_rel)
                else:
                    if img_rel.is_absolute():
                        candidate_paths.append(img_rel)
                    else:
                        candidate_paths.append(UPLOAD_ROOT / img_rel)

            # (b) server_path 가 있으면 그쪽도 후보에 추가
            if att.server_path:
                sp = Path(att.server_path)
                if sp.is_absolute():
                    candidate_paths.append(sp)
                else:
                    candidate_paths.append(UPLOAD_ROOT / sp)

            # (c) 이름만 있을 때는 업로드 프로필 기준으로 추론
            if att.name:
                profile = req.upload_profile or "local_default"
                candidate_paths.append(UPLOAD_ROOT / profile / att.name)

            # 후보 경로들 중에서 실제 존재하는 첫 번째 파일을 연다
            img_obj = None
            for p in candidate_paths:
                try:
                    if p.is_file():
                        img_obj = PILImage.open(p)
                        break
                except Exception:
                    continue

            if img_obj is not None:
                image_parts.append(img_obj)

        if image_parts:
            contents = image_parts + [final_prompt]
            resp = model.generate_content(contents)
        else:
            resp = model.generate_content(final_prompt)

        reply_text = resp.text.strip() if hasattr(resp, "text") else str(resp)
    except Exception as e:
        reply_text = f"부감독 뇌 연결 중 오류가 있었어. (세부: {e})"

    return {"reply": reply_text}

@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "role": "director_core"}
