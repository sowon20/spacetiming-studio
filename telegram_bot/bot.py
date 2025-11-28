import os
import logging
from dotenv import load_dotenv
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from telegram.constants import ChatAction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("spacetime-telegram-bot")

# .env 파일 로드 (프로젝트 루트에 있는 .env)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

DIRECTOR_CORE_BASE = "http://127.0.0.1:8897"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN 환경변수가 없어요!")

# ---------------------------------
# 감독(소원) 메시지 → director_core 분석 → 응답
# ---------------------------------
async def send_to_director_core(chat_id: int, text: str, media: list, context: ContextTypes.DEFAULT_TYPE):
    """
    텍스트/이미지/영상 등 모든 형태의 메시지를 director_core로 보내는 공통 함수.
    """
    # 현재 director_core는 mode="chat"만 지원하므로, media가 있어도 일단 chat 모드로 보낸다.
    mode = "chat"
    payload = {
        "mode": mode,
        "text": text or "",
        "user_id": str(chat_id),
        "source": "telegram",
        "media": media,  # [{type, telegram_file_id, file_url}, ...]
        "context": {
            "source": "telegram",
            "user_id": str(chat_id),
            "episode_id": None,
            "tags": [],
        },
    }

    # director_core에 분석 요청
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{DIRECTOR_CORE_BASE}/director/analyze",
                json=payload,
            )
    except Exception as e:
        logger.exception("director_core 요청 실패")
        await context.bot.send_message(
            chat_id=chat_id,
            text="부감독 뇌랑 연결이 잠깐 끊겼어 😿\n조금만 있다가 다시 시도해줘!",
        )
        return

    # HTTP 상태코드 체크 (200이 아니면 바로 에러 알려주기)
    if resp.status_code != 200:
        body_text = resp.text[:500] if hasattr(resp, "text") else "(no body)"
        logger.error("director_core HTTP 오류: status=%s body=%s", resp.status_code, body_text)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"부감독 서버에서 오류가 났어. (status {resp.status_code})\n개발 로그에는 자세한 내용이 남아있어!",
        )
        return

    # JSON 파싱
    try:
        data = resp.json()
    except ValueError:
        logger.exception("director_core 응답 JSON 파싱 실패")
        await context.bot.send_message(
            chat_id=chat_id,
            text="부감독 뇌 응답이 좀 이상해… 😿\n잠깐 뒤에 다시 말해줘!",
        )
        return

    # 필드 추출
    summary = data.get("summary") or ""
    intent = data.get("intent") or "unknown"
    reply = data.get("reply") or "지금은 대답이 잘 안 만들어졌어. 🙂"
    episode_hint = data.get("episode_hint") or {}

    # 부감독 대답 (요약/의도 메타 정보는 숨기고, 순수한 답변만 보내기)
    await context.bot.send_message(chat_id=chat_id, text=reply)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    chat_id = update.message.chat_id
    logger.info("handle_text: chat_id=%s text=%s", chat_id, text)

    await send_to_director_core(chat_id=chat_id, text=text, media=[], context=context)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.photo:
        return

    chat_id = message.chat_id
    caption = (message.caption or "").strip()
    if not caption:
        caption = "이미지 분석해줘"
    logger.info(
        "handle_photo: chat_id=%s caption=%s file_id=%s",
        chat_id,
        caption,
        message.photo[-1].file_id,
    )

    # 가장 큰 해상도 사진 선택
    photo = message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_url = file.file_path  # python-telegram-bot v20에서 전체 URL 제공

    media = [
        {
            "type": "image",
            "telegram_file_id": photo.file_id,
            "file_url": file_url,
        }
    ]

    await send_to_director_core(chat_id=chat_id, text=caption, media=media, context=context)


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.video:
        return

    chat_id = message.chat_id
    caption = (message.caption or "").strip()
    if not caption:
        caption = "영상 분석해줘"
    logger.info("handle_video: chat_id=%s caption=%s", chat_id, caption)

    video = message.video
    file = await context.bot.get_file(video.file_id)
    file_url = file.file_path

    media = [
        {
            "type": "video",
            "telegram_file_id": video.file_id,
            "file_url": file_url,
        }
    ]

    await send_to_director_core(chat_id=chat_id, text=caption, media=media, context=context)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    사진/영상을 '파일로 보내기' 했을 때 document로 오는 경우 처리.
    mime_type으로 이미지/영상 여부를 판별한다.
    """
    message = update.message
    if not message or not message.document:
        return

    chat_id = message.chat_id
    caption = (message.caption or "").strip()
    if not caption:
        caption = "파일(이미지/영상) 분석해줘"
    logger.info(
        "handle_document: chat_id=%s caption=%s file_id=%s mime=%s",
        chat_id,
        caption,
        doc.file_id,
        mime,
    )
    doc = message.document
    mime = (doc.mime_type or "").lower()

    # 이미지나 영상이 아닌 경우는 무시
    media_type = None
    if mime.startswith("image/"):
        media_type = "image"
    elif mime.startswith("video/"):
        media_type = "video"
    else:
        return

    file = await context.bot.get_file(doc.file_id)
    file_url = file.file_path

    media = [
        {
            "type": media_type,
            "telegram_file_id": doc.file_id,
            "file_url": file_url,
        }
    ]

    await send_to_director_core(chat_id=chat_id, text=caption, media=media, context=context)


# ---------------------------------
# 메인 실행 (동기 버전)
# ---------------------------------
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    logger.info("🚀 Telegram bot started (spacetime)!")
    app.run_polling()


if __name__ == "__main__":
    main()