import os

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Update, Message
from aiogram.filters.command import CommandObject
from openai import AsyncOpenAI


BOT_TOKEN = os.environ["BOT_TOKEN"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

MODEL = "google/gemini-3.1-flash-lite-preview"

WEBHOOK_PATH = "/telegram"
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

app = FastAPI()


# =========================
# START
# =========================

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Привет! 🤖\n\n"
        "В личке просто напиши сообщение.\n"
        "В группе используй:\n"
        "/ask твой вопрос"
    )


# =========================
# /ASK
# =========================

@dp.message(Command("ask"))
async def ask_command(
    message: Message,
    command: CommandObject
):
    if not command.args:
        await message.answer(
            "❗ Напиши вопрос после /ask\n\n"
            "Например:\n"
            "/ask Что такое Python?"
        )
        return

    await ask_ai(message, command.args)


# =========================
# ОБЫЧНЫЕ СООБЩЕНИЯ
# =========================

@dp.message()
async def normal_message(message: Message):

    # В группах обычные сообщения игнорируем
    if message.chat.type != "private":
        return

    if not message.text:
        return

    await ask_ai(message, message.text)


# =========================
# GEMINI
# =========================

async def ask_ai(message: Message, text: str):

    try:

        await bot.send_chat_action(
            chat_id=message.chat.id,
            action="typing"
        )

        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты дружелюбный и полезный "
                        "AI-ассистент в Telegram."
                    )
                },
                {
                    "role": "user",
                    "content": text
                }
            ]
        )

        answer = response.choices[0].message.content

        if not answer:
            answer = "Не удалось получить ответ от Gemini."

        await message.answer(answer)

    except Exception as e:

        print("ERROR:", repr(e))

        await message.answer(
            "⚠️ Произошла ошибка при обращении к AI."
        )


# =========================
# WEBHOOK
# =========================

@app.get("/")
async def home():
    return {
        "status": "online",
        "bot": "Telegram AI Bot"
    }


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):

    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")

    if secret != WEBHOOK_SECRET:
        return {"ok": False}

    data = await request.json()

    update = Update.model_validate(data, context={"bot": bot})

    await dp.feed_update(bot, update)

    return {"ok": True}
