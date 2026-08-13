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
# WEBHOOK SETUP
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

        print("🤖 Telegram AI Bot запущен!")
        print("================================")

    except Exception as e:
        print("❌ WEBHOOK SETUP ERROR:", repr(e))


# =========================
# STARTUP / SHUTDOWN
# =========================

@asynccontextmanager
async def lifespan(app: FastAPI):

    print("🚀 FastAPI запускается...")

    # Устанавливаем webhook ДО того,
    # как приложение полностью запустится
    await setup_webhook()

    print("🚀 FastAPI успешно запущен!")

    try:
        yield

    finally:
        print("🛑 FastAPI shutting down...")

        try:
            await bot.delete_webhook()
            print("Telegram webhook удалён.")
        except Exception as e:
            print("Webhook shutdown error:", repr(e))

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

    # В группах обычные сообщения игнорируем
    if message.chat.type != "private":
        return

    # Если это не текст — игнорируем
    if not message.text:
        return

    await ask_ai(message, message.text)


# =========================
# GEMINI ЧЕРЕЗ OPENROUTER
# =========================

async def ask_ai(message: Message, text: str):

    try:

        await bot.send_chat_action(
            chat_id=message.chat.id,
            action="typing"
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

    except Exception as e:

        print("❌ AI ERROR:", repr(e))

        try:
            await message.answer(
                "⚠️ Произошла ошибка при обращении к AI."
            )
        except Exception:
            pass


# =========================
# ГЛАВНАЯ СТРАНИЦА
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

    # Проверяем секрет Telegram
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
