import os
import logging
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("spacetime-telegram-bot")

DIRECTOR_CORE_BASE = "http://127.0.0.1:8897"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN 환경변수가 없어요!")

# ---------------------------------
# 감독(소원) 메시지 → director_core 분석 → 응답
# ---------------------------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    chat_id = update.message.chat_id

    # director_core에 분석 요청
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{DIRECTOR_CORE_BASE}/director/analyze",
                json={
                    "mode": "chat",
                    "text": text,
                    "context": {
                        "source": "telegram",
                        "user_id": str(chat_id),
                        "episode_id": None,
                        "tags": [],
                    },
                },
            )
    except Exception as e:
        logger.exception("director_core 요청 실패")
        await context.bot.send_message(
            chat_id=chat_id,
            text="부감독 뇌랑 연결이 잠깐 끊겼어 😿\n조금만 있다가 다시 시도해줘!",
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


# ---------------------------------
# 메인 실행 (동기 버전)
# ---------------------------------
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("🚀 Telegram bot started (spacetime)!")
    app.run_polling()


if __name__ == "__main__":
    main()