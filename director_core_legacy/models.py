from __future__ import annotations

from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field


ModeLiteral = Literal["chat", "vision"]  # vision 모드 추가
IntentLiteral = Literal[
    "veo_prompt",
    "casual_chat",
    "daily_log",
    "todo",
    "question",
    "unknown",
]


class AnalyzeContext(BaseModel):
    source: Optional[str] = Field(
        default=None,
        description="telegram | home | sidebar 등 입력 출처",
    )
    user_id: Optional[str] = None
    episode_id: Optional[str] = None
    tags: Optional[List[str]] = None


class EpisodeHint(BaseModel):
    should_create_episode: bool = False
    suggested_title: Optional[str] = None
    suggested_plan: Optional[str] = None
    priority: Optional[Literal["low", "normal", "high"]] = "normal"


class AnalyzeRequest(BaseModel):
    mode: ModeLiteral = "chat"
    text: Optional[str] = Field(
        default=None,
        description="사용자가 보낸 텍스트 또는 음성 STT 결과",
    )
    media_url: Optional[str] = Field(
        default=None,
        description="이미지/음성/영상 파일 URL (image/audio/video 모드에서 사용)",
    )
    media: Optional[List[Dict[str, Any]]] = None  # telegram image/video list
    context: Optional[AnalyzeContext] = None


class AnalyzeResponse(BaseModel):
    ok: bool = True
    mode: ModeLiteral
    summary: str
    intent: IntentLiteral
    reply: str
    episode_hint: EpisodeHint
    raw_model_output: Dict[str, Any] = Field(default_factory=dict)