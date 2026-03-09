import asyncio
import logging
import os
import json
from datetime import time, timezone, timedelta
from anthropic import AsyncAnthropic

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
ANTHROPIC_KEY= os.environ.get("ANTHROPIC_API_KEY", "")
SEND_HOUR    = int(os.environ.get("SEND_HOUR", "9"))
SEND_MIN     = int(os.environ.get("SEND_MIN",  "0"))
UTC_OFFSET   = int(os.environ.get("UTC_OFFSET", "3"))

users_file = "users.txt"

def load_users():
    if not os.path.exists(users_file):
        return set()
    with open(users_file) as f:
        return set(l.strip() for l in f if l.strip())

def save_user(chat_id):
    users = load_users()
    users.add(str(chat_id))
    with open(users_file, "w") as f:
        f.write("\n".join(users))

def remove_user(chat_id):
    users = load_users()
    users.discard(str(chat_id))
    with open(users_file, "w") as f:
        f.write("\n".join(users))

async def ask_claude(prompt: str) -> str:
    try:
        client = AsyncAnthropic(api_key=ANTHROPIC_KEY)
        msg = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system="Отвечай только на русском языке. Будь кратким и конкретным.",
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except Exception as e:
        logger.error(f"Claude error: {e}")
        return ""

async def ask_claude_json(prompt: str):
    try:
        client = AsyncAnthropic(api_key=ANTHROPIC_KEY)
        msg = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system="Отвечай ТОЛЬКО валидным JSON. Без markdown, без пояснений.",
            messages=[{"role": "user", "content": prompt}]
        )
        text = msg.content[0].text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        logger.error(f"Claude JSON error: {e}")
        return None

async def build_daily_message() -> str:
    from datetime import date
    today = date.today()
    day = today.day

    topics = ['переменные и типы данных','if / elif / else','цикл for и range()','цикл while',
              'функции def и return','списки и методы','словари','методы строк',
              'ввод через input()','логические операторы']
    topic = topics[day % len(topics)]

    # Запускаем все запросы параллельно
    quote_task   = ask_claude_json('Цитата от известного человека. JSON: {"text":"цитата","author":"Имя Фамилия"}')
    motiv_task   = ask_claude('2 предложения мотивации для новичка в Python и английском B1. Вдохновляюще!')
    fact_task    = ask_claude_json('1 удивительный факт о науке или технологиях (2 предложения). JSON: {"fact":"текст"}')
    python_task  = ask_claude_json(f'Python задача для новичка тема: "{topic}". JSON: {{"topic":"тема","task":"задание 1-2 предл.","hint":"подсказка","code":"код 3-4 строки"}}')
    words_task   = ask_claude_json('4 слова английский B1. JSON: [{"en":"word","ru":"перевод","tr":"[транскр]"},...]')

    quote, motiv, fact, python, words = await asyncio.gather(
        quote_task, motiv_task, fact_task, python_task, words_task
    )

    msg = f"☀️ *Доброе утро! Твой план на сегодня:*\n\n"

    # Цитата
    if quote and quote.get("text"):
        msg += f"✦ *Цитата дня*\n_{quote['text']}_\n— {quote['author']}\n\n"

    # Мотивация
    if motiv:
        msg += f"💚 *Мотивация*\n{motiv}\n\n"

    # Факт
    if fact and fact.get("fact"):
        msg += f"💡 *Факт дня*\n{fact['fact']}\n\n"

    # Python
    if python and python.get("topic"):
        msg += f"🐍 *Python — задача дня*\n"
        msg += f"Тема: `{python['topic']}`\n"
        msg += f"📌 {python['task']}\n"
        msg += f"💡 {python['hint']}\n"
        msg += f"```python\n{python['code']}\n```\n\n"

    # Английский
    if words and isinstance(words, list):
        msg += f"🇬🇧 *English — слова дня*\n"
        for w in words:
            msg += f"• *{w.get('en','')}* {w.get('tr','')} — {w.get('ru','')}\n"
        msg += "\n"

    msg += "✅ Удачи! Отмечай выполненное: /done"
    return msg

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_chat.id)
    await update.message.reply_text(
        "👋 Привет! Я буду присылать тебе каждое утро:\n\n"
        "✦ Цитату дня\n"
        "💚 Мотивацию\n"
        "💡 Интересный факт\n"
        "🐍 Задачу по Python\n"
        "🇬🇧 Английские слова\n\n"
        f"⏰ Каждый день в {SEND_HOUR:02d}:{SEND_MIN:02d} МСК\n\n"
        "📌 Команды:\n"
        "/now — получить урок прямо сейчас\n"
        "/stop — отписаться\n\n"
        "Удачи в учёбе! 🐍🇬🇧",
        parse_mode="Markdown"
    )

# /stop
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remove_user(update.effective_chat.id)
    await update.message.reply_text("✅ Напоминания отключены. /start — включить снова.")

# /now
async def cmd_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Генерирую твой урок дня, подожди немного...")
    try:
        msg = await build_daily_message()
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"/now error: {e}")
        await update.message.reply_text("❌ Что-то пошло не так, попробуй ещё раз.")

# /done
async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎉 Молодец! Ещё один день учёбы позади.\n"
        "🔥 Продолжай в том же духе — маленькие шаги каждый день = большой результат!"
    )

# Ежедневная рассылка
async def send_daily(context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    if not users:
        return
    logger.info(f"Sending daily to {len(users)} users...")
    try:
        msg = await build_daily_message()
        for chat_id in users:
            try:
                await context.bot.send_message(
                    chat_id=int(chat_id),
                    text=msg,
                    parse_mode="Markdown"
                )
                logger.info(f"Sent to {chat_id}")
            except Exception as e:
                logger.warning(f"Failed {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Daily send error: {e}")

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан!")
    if not ANTHROPIC_KEY:
        raise ValueError("ANTHROPIC_API_KEY не задан!")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop",  stop))
    app.add_handler(CommandHandler("now",   cmd_now))
    app.add_handler(CommandHandler("done",  cmd_done))

    tz = timezone(timedelta(hours=UTC_OFFSET))
    app.job_queue.run_daily(
        send_daily,
        time=time(hour=SEND_HOUR, minute=SEND_MIN, tzinfo=tz),
        name="daily"
    )

    logger.info(f"Бот запущен. Рассылка в {SEND_HOUR:02d}:{SEND_MIN:02d} UTC+{UTC_OFFSET}")
    app.run_polling()

if __name__ == "__main__":
    main()
