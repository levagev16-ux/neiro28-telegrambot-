import os
import httpx
import logging
from fastapi import FastAPI, Request, Header
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Update, Message
from aiogram.filters.command import CommandObject
from openai import AsyncOpenAI

logging.basicConfig(level=logging.INFO)

# Безопасное чтение переменных окружения через .get()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

MODEL = "google/gemini-2.0-flash-exp:free"
WEBHOOK_PATH = "/telegram"

app = FastAPI()

# Инициализируем только если есть ключи
bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
dp = Dispatcher()

# Создаём кастомный HTTP-клиент для фикса ошибки 'proxies' в httpx на Vercel
custom_http_client = httpx.AsyncClient()

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    http_client=custom_http_client
) if OPENROUTER_API_KEY else None


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Привет! 🤖\n\n"
        "В личном чате просто напиши мне сообщение.\n"
        "В группе используй:\n"
        "/ask твой вопрос"
    )


@dp.message(Command("ask"))
async def ask_command(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("❗️ После /ask напиши вопрос.\nПример: /ask Что такое Python?", parse_mode="Markdown")
        return
    await ask_ai(message, command.args)


@dp.message()
async def normal_message(message: Message):
    if message.chat.type != "private" or not message.text:
        return
    await ask_ai(message, message.text)


async def ask_ai(message: Message, text: str):
    if not client or not bot:
        await message.answer("⚠️ Сервер не настроен (отсутствуют API ключи в Vercel).")
        return

    try:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")

        response = await client.chat.completions.create(
            model=MODEL,
            max_tokens=2048,
            messages=[
                {"role": "system", "content": "Ты дружелюбный и полезный AI-ассистент в Telegram."},
                {"role": "user", "content": text}
            ]
        )

        answer = response.choices[0].message.content or "Не удалось получить ответ от AI."
        await message.answer(answer)

    except Exception as e:
        logging.error(f"AI ERROR: {e}")
        try:
            await message.answer("⚠️ Произошла ошибка при обращении к AI.")
        except Exception as send_error:
            logging.error(f"Send Error: {send_error}")


@app.get("/")
async def home():
    return {
        "status": "online",
        "bot": "Telegram AI Bot",
        "bot_token_set": bool(BOT_TOKEN),
        "openrouter_key_set": bool(OPENROUTER_API_KEY)
    }


@app.get("/set_webhook")
async def set_webhook_endpoint(request: Request):
    if not bot:
        return {"ok": False, "error": "BOT_TOKEN is missing in Environment Variables"}
    
    host = request.headers.get("host")
    webhook_url = f"https://{host}{WEBHOOK_PATH}"
    
    try:
        result = await bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET if WEBHOOK_SECRET else None
        )
        return {"ok": result, "webhook_url": webhook_url}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post(WEBHOOK_PATH)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None)
):
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        return {"ok": False, "error": "Invalid secret"}

    if not bot:
        return {"ok": False, "error": "Bot not configured"}

    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as e:
        logging.error(f"WEBHOOK ERROR: {e}")
        return {"ok": False, "error": "Processing error"}

