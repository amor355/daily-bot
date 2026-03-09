import asyncio
import logging
import os
from datetime import time, timezone, timedelta

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SEND_HOUR = int(os.environ.get("SEND_HOUR", "9"))   # час отправки (по умолчанию 9:00)
SEND_MIN  = int(os.environ.get("SEND_MIN",  "0"))   # минута
UTC_OFFSET = int(os.environ.get("UTC_OFFSET", "3"))  # +3 для Москвы

MESSAGES = [
    "🌅 Доброе утро! Пора открыть дашборд и заняться делом.\n\n🐍 Задача по Python ждёт тебя\n🇬🇧 Новые английские слова готовы\n📰 Свежие новости дня\n\nОткрывай и вперёд — маленький шаг каждый день = большой результат! 💪",
    "☀️ Привет! Не забудь про свой ежедневный дашборд.\n\n✅ Python — практика сегодня\n✅ English — слова B1 уровня\n✅ Цитата дня уже тебя ждёт\n\nКаждый день учёбы — это инвестиция в себя! 🚀",
    "📚 Новый день — новые знания!\n\n Открой дашборд:\n🐍 Сегодняшняя задача Python\n🇬🇧 6 новых английских слов\n💬 Фраза дня для разговорного English\n\nТы уже лучше, чем вчера! ⭐",
    "🎯 Время учиться!\n\nТвой дашборд готов к работе:\n• Задача Python для новичка\n• Слова и фраза на английском\n• Мотивация и новости\n\nПоследовательность — ключ к успеху! 🔑",
    "💡 Доброе утро, будущий разработчик!\n\nОткрой дашборд и сделай это:\n🐍 Реши задачу по Python\n🇬🇧 Выучи 6 слов на английском\n🔥 Не прерывай свой стрик!\n\nВперёд — сегодня ты станешь чуть лучше 🌱",
    "⚡ Привет! Твой ежедневный урок ждёт.\n\n🐍 Python: новая тема сегодня\n🇬🇧 English B1: свежие слова\n📰 Что происходит в мире\n\nМаленькие шаги каждый день — вот секрет! 🏆",
    "🌟 Утро — лучшее время для учёбы!\n\nЗаходи в дашборд:\n✔️ Python задача дня\n✔️ Английские слова\n✔️ Цитата от великих людей\n\nТы на правильном пути — продолжай! 💫",
]

# Хранилище chat_id пользователей
users_file = "users.txt"

def load_users():
    if not os.path.exists(users_file):
        return set()
    with open(users_file, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_user(chat_id: str):
    users = load_users()
    users.add(chat_id)
    with open(users_file, "w") as f:
        f.write("\n".join(users))

def get_daily_message(day_of_year: int) -> str:
    return MESSAGES[day_of_year % len(MESSAGES)]

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    save_user(chat_id)
    await update.message.reply_text(
        "👋 Привет! Я буду напоминать тебе каждое утро открыть дашборд и заняться учёбой.\n\n"
        f"⏰ Напоминание будет приходить каждый день в {SEND_HOUR:02d}:{SEND_MIN:02d} (МСК).\n\n"
        "📌 Команды:\n"
        "/start — подписаться на напоминания\n"
        "/stop — отписаться\n"
        "/now — получить напоминание прямо сейчас\n\n"
        "Удачи в учёбе! 🐍🇬🇧"
    )

# /stop
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    users = load_users()
    users.discard(chat_id)
    with open(users_file, "w") as f:
        f.write("\n".join(users))
    await update.message.reply_text("✅ Напоминания отключены. Напиши /start чтобы включить снова.")

# /now
async def now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime
    msg = get_daily_message(datetime.now().timetuple().tm_yday)
    await update.message.reply_text(msg)

# Ежедневная рассылка
async def send_daily(context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime
    users = load_users()
    msg = get_daily_message(datetime.now().timetuple().tm_yday)
    for chat_id in users:
        try:
            await context.bot.send_message(chat_id=int(chat_id), text=msg)
            logger.info(f"Sent to {chat_id}")
        except Exception as e:
            logger.warning(f"Failed to send to {chat_id}: {e}")

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан! Добавь его в переменные окружения.")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("now", now))

    # Планировщик ежедневной рассылки
    tz = timezone(timedelta(hours=UTC_OFFSET))
    app.job_queue.run_daily(
        send_daily,
        time=time(hour=SEND_HOUR, minute=SEND_MIN, tzinfo=tz),
        name="daily_reminder"
    )

    logger.info(f"Бот запущен. Напоминания в {SEND_HOUR:02d}:{SEND_MIN:02d} UTC+{UTC_OFFSET}")
    app.run_polling()

if __name__ == "__main__":
    main()
