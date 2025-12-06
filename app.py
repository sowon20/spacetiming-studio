from __future__ import annotations

import os
import json
import requests
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# 부감독 뇌 서버 URL (8897)
DIRECTOR_CORE_URL = os.getenv(
    "DIRECTOR_CORE_URL",
    "http://127.0.0.1:8897",  # 기본값: 라즈베리 로컬에서 director_server_v1
)
UPLOAD_ROOT = Path("/mnt/sowon_cloud/chat_uploads").resolve()
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


class ChatMessage(BaseModel):
    role: str
    content: str


class AttachmentMeta(BaseModel):
    name: str
    type: Optional[str] = None
    size: Optional[int] = None
    url: Optional[str] = None
    # 포털 서버(app.py)에서 전달해주는 실제 서버 로컬 경로
    # 예: /home/sowon/spacetiming-studio/uploads/local_default/IMG_3001.jpeg
    server_path: Optional[str] = None


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    attachments: Optional[List[AttachmentMeta]] = None
    upload_profile: Optional[str] = "local_default"


class ChatResponse(BaseModel):
    reply: str


def get_upload_dir(profile: str) -> Path:
    """
    업로드 프로필 이름에 따라 실제 저장 디렉토리를 결정한다.
    - 기본값: uploads/<profile>/
    - 디렉토리가 없으면 생성한다.
    """
    safe_profile = profile or "local_default"
    # 너무 긴 문자/공백은 간단히 정리
    safe_profile = safe_profile.strip() or "local_default"
    safe_profile = safe_profile.replace("..", "_").replace("/", "_")
    target = UPLOAD_ROOT / safe_profile
    target.mkdir(parents=True, exist_ok=True)
    return target


class HistoryItem(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str
    attachments: Optional[list[dict]] = None


HISTORY_FILES = [
    "portal_history/sowon.chat.jsonl",
    "portal_history/sowon.chat.mac.jsonl",
]

HISTORY_WRITE_FILE = Path("portal_history") / "sowon.chat.jsonl"
HISTORY_WRITE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_history(limit: int = 400) -> List[HistoryItem]:
    items_by_key: dict[str, HistoryItem] = {}

    for path in HISTORY_FILES:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    role = data.get("role") or "assistant"
                    text = data.get("text") or ""
                    ts = data.get("timestamp") or ""
                    msg_id = data.get("id") or ts or ""

                    # 첨부 정보가 있으면 그대로 보존 (attachments 또는 files 키)
                    attachments = None
                    raw_att = data.get("attachments") or data.get("files")
                    if isinstance(raw_att, list):
                        attachments = raw_att

                    # sowon.chat / sowon.chat.mac 에서 동일 발화가 중복되는 걸 막기 위한 키
                    key = f"{msg_id}|{role}|{text}"
                    items_by_key[key] = HistoryItem(
                        id=msg_id or key,
                        role=role,
                        content=text,
                        timestamp=ts,
                        attachments=attachments,
                    )
        except FileNotFoundError:
            continue

    if not items_by_key:
        return []

    # 최신 순으로 정렬 후 limit만큼 자르기
    items_sorted = sorted(items_by_key.values(), key=lambda x: x.id)[-limit:]
    return items_sorted


# 서버 공용 히스토리 파일(포털 기준)에 한 줄 추가.
def _append_history(role: str, text: str, attachments: Optional[list[dict]] = None) -> None:
    """
    서버 공용 히스토리 파일(포털 기준)에 한 줄 추가.
    - /api/history 에서 읽어가는 sowon.chat.jsonl 파일에 작성한다.
    - attachments 가 있으면 그대로 기록해서 나중에 이미지/파일 썸네일을 복원할 수 있게 한다.
    """
    ts = datetime.now().isoformat(timespec="seconds")
    item: dict = {
        "id": ts,
        "role": role,
        "text": text,
        "timestamp": ts,
    }
    if attachments:
        item["attachments"] = attachments

    try:
        with HISTORY_WRITE_FILE.open("a", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False)
            f.write("\n")
    except Exception:
        # 히스토리 기록 실패는 채팅 자체를 막지는 않는다.
        pass


app = FastAPI()


# CORS: chat.html / 확장프로그램 / 아이폰 브라우저 등 다 열어두기
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 나중에 도메인 고정하고 싶으면 여기 줄이면 됨
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/history")
async def api_history(limit: int = 400):
    """최근 대화 히스토리를 반환 (서버 기준, 기기와 브라우저를 넘어 공통 히스토리)."""
    try:
        items = _load_history(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"history_load_error: {e}")
    return [item.dict() for item in items]


@app.get("/health")
async def health():
    """
    포털 자체 헬스체크.
    + 부감독 뇌 서버까지 같이 확인.
    """
    core_status = "unknown"
    try:
        r = requests.get(f"{DIRECTOR_CORE_URL}/health", timeout=3)
        if r.ok:
            core_status = r.json().get("status", "ok")
        else:
            core_status = f"http_{r.status_code}"
    except Exception as e:
        core_status = f"error: {e}"

    return {"status": "ok", "director_core_status": core_status}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    chat.html / 사이드바 확장 / 아이폰에서 쓰는 공통 엔드포인트.

    - 클라이언트 → /api/chat 로 messages + attachments 메타정보 보냄
    - 여기서 director_core(8897)로 그대로 포워딩
    - 부감독 뇌의 reply만 꺼내서 반환
    """
    # 첨부 파일 메타정보는 req.attachments 로 들어온다.
    # director_core(/chat) 호출 시:
    #   - messages: 대화 맥락
    #   - attachments: 파일 메타 (name/type/size/url 등)
    #   - upload_profile: 실제 파일이 저장된 프로필 이름 (예: local_default, gdrive_...)
    # director_core 쪽에서 이 정보를 바탕으로 이미지/파일을 열어볼 수 있다.
    payload = {
        "messages": [m.model_dump() for m in req.messages],
        "upload_profile": req.upload_profile or "local_default",
    }
    if req.attachments:
        payload["attachments"] = [a.model_dump() for a in req.attachments]

    try:
        resp = requests.post(
            f"{DIRECTOR_CORE_URL}/chat",
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        # 여기서 에러 나면 브라우저에 500으로 전달 → 콘솔에 500 찍히는 그 부분
        raise HTTPException(
            status_code=500,
            detail=f"director_core 연결 오류: {e}",
        )

    data = resp.json()
    reply = data.get("reply", "").strip()

    if not reply:
        raise HTTPException(
            status_code=500,
            detail="director_core 응답에 reply 필드가 비어 있음",
        )

    # 히스토리 파일에 이번 턴 기록 (마지막 user 발화 + assistant 응답)
    try:
        last_user = None
        for m in reversed(req.messages):
            if m.role == "user":
                last_user = m
                break

        # 현재 턴에서 사용된 첨부 메타 (있다면 그대로 기록)
        att_list: Optional[list[dict]] = None
        if req.attachments:
            att_list = [a.model_dump() for a in req.attachments]

        if last_user is not None:
            _append_history("user", last_user.content, att_list)

        _append_history("assistant", reply)
    except Exception:
        # 히스토리 기록 실패는 채팅 응답 자체를 막지 않는다.
        pass

    return ChatResponse(reply=reply)


@app.post("/api/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    upload_profile: str = Form("local_default"),
):
    """
    첨부 파일 실제 업로드 엔드포인트.
    - 프론트에서 FormData로 파일들 + upload_profile 을 보낸다.
    - uploads/<upload_profile>/ 아래에 저장하고, /uploads/... 경로를 돌려준다.
    """
    upload_dir = get_upload_dir(upload_profile)
    results: list[dict] = []

    for uf in files:
        original_name = uf.filename or "file"
        # 너무 긴 이름/경로 관련 문자를 간단히 정리
        safe_name = original_name.replace("/", "_").replace("\\", "_")
        target_path = upload_dir / safe_name

        try:
            with target_path.open("wb") as out_f:
                content = await uf.read()
                out_f.write(content)
        finally:
            await uf.close()

        # 정적 서빙용 URL (/uploads 마운트 기준)
        rel_path = target_path.relative_to(UPLOAD_ROOT)
        url = f"/uploads/{rel_path.as_posix()}"

        results.append(
            {
                "name": original_name,
                "saved_as": safe_name,
                "url": url,
                "upload_profile": upload_profile,
                "server_path": str(target_path),
            }
        )

    return {"files": results}

from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

# 정적 파일(스타일/JS) 서빙
app.mount("/static", StaticFiles(directory="portal", html=False), name="static")
# 업로드 파일 서빙 (/uploads/ 경로 아래에서 접근)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_ROOT), html=False), name="uploads")

# portal 폴더 전체를 /portal 아래에 그대로 매핑
app.mount("/portal", StaticFiles(directory="portal", html=True), name="portal_html")