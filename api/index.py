import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Update, Message
from aiogram.filters.command import CommandObject
from openai import AsyncOpenAI


# =========================
# НАСТРОЙКИ
# =========================

BOT_TOKEN = os.environ["BOT_TOKEN"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]

MODEL = "google/gemini-3.1-flash-lite-preview"

WEBHOOK_PATH = "/telegram"


# =========================
# КЛИЕНТЫ
# =========================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)


# =========================
# WEBHOOK
# =========================

async def setup_webhook():
    try:
        render_url = os.environ["RENDER_EXTERNAL_URL"]
        webhook_url = render_url + WEBHOOK_PATH

        print("================================")
        print("🤖 Настройка Telegram webhook...")
        print("Webhook URL:", webhook_url)

        result = await bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET
        )

        print("set_webhook result:", result)

        info = await bot.get_webhook_info()

        print("--------------------------------")
        print("Telegram webhook info:")
        print("URL:", info.url)
        print("Pending updates:", info.pending_update_count)
        print("Last error:", info.last_error_message)
        print("--------------------------------")

        if info.last_error_message:
            print(
                "⚠️ Telegram сообщает об ошибке:",
                info.last_error_message
            )

        print("🤖 Telegram AI Bot запущен!")
        print("================================")

    except Exception as e:
        print("❌ WEBHOOK SETUP ERROR:", repr(e))


# =========================
# LIFESPAN
# =========================

@asynccontextmanager
async def lifespan(app: FastAPI):

    print("🚀 FastAPI запускается...")

    await setup_webhook()

    print("🚀 FastAPI успешно запущен!")

    yield

    # ВАЖНО:
    # webhook здесь НЕ удаляем.
    # Render может перезапускать процесс,
    # а Telegram должен продолжать знать URL webhook.

    print("🛑 FastAPI shutting down...")

    try:
        await bot.session.close()
        print("Telegram bot session closed.")
    except Exception as e:
        print("Bot shutdown error:", repr(e))

    try:
        await client.close()
        print("OpenRouter client closed.")
    except Exception as e:
        print("OpenRouter shutdown error:", repr(e))


app = FastAPI(lifespan=lifespan)


# =========================
# START
# =========================

@dp.message(CommandStart())
async def start(message: Message):

    await message.answer(
        "Привет! 🤖\n\n"
        "В личном чате просто напиши сообщение.\n"
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
            "❗ После /ask нужно написать вопрос.\n\n"
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

    if message.chat.type != "private":
        return

    if not message.text:
        return

    await ask_ai(message, message.text)


# =========================
# AI
# =========================

async def ask_ai(message: Message, text: str):

    try:

        await bot.send_chat_action(
            chat_id=message.chat.id,
            action="typing"
        )

        print(
            f"🤖 AI запрос от {message.from_user.id}: {text}"
        )

        response = await client.chat.completions.create(
            model=MODEL,
            max_tokens=2048,
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

        print("✅ Ответ AI отправлен.")

    except Exception as e:

        print("❌ AI ERROR:", repr(e))

        try:
            await message.answer(
                "⚠️ Произошла ошибка при обращении к AI."
            )
        except Exception as send_error:
            print(
                "❌ Ошибка отправки сообщения:",
                repr(send_error)
            )


# =========================
# ГЛАВНАЯ
# =========================

@app.get("/")
async def home():

    return {
        "status": "online",
        "bot": "Telegram AI Bot",
        "webhook": "active"
    }


# =========================
# TELEGRAM WEBHOOK
# =========================

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):

    secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token"
    )

    if secret != WEBHOOK_SECRET:

        print("❌ Invalid Telegram webhook secret")

        return {
            "ok": False,
            "error": "Invalid secret"
        }

    try:

        data = await request.json()

        update = Update.model_validate(
            data,
            context={"bot": bot}
        )

        print("📩 Telegram update получен.")

        await dp.feed_update(
            bot,
            update
        )

        return {
            "ok": True
        }

    except Exception as e:

        print(
            "❌ WEBHOOK ERROR:",
            repr(e)
        )

        return {
            "ok": False,
            "error": "Webhook processing error"
        }
