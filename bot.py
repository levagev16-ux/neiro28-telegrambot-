import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject
from aiogram.types import Update, Message
from openai import AsyncOpenAI


# ==========================================
# НАСТРОЙКИ
# ==========================================

BOT_TOKEN = os.environ["BOT_TOKEN"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]

# Gemini через OpenRouter
MODEL = "google/gemini-3.1-flash-lite-preview"

WEBHOOK_PATH = "/telegram"


# ==========================================
# TELEGRAM
# ==========================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ==========================================
# OPENROUTER
# ==========================================

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)


# ==========================================
# WEBHOOK STARTUP
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    render_url = os.environ.get("RENDER_EXTERNAL_URL")

    if not render_url:
        print("❌ RENDER_EXTERNAL_URL не найдена!")

    else:

        webhook_url = render_url + WEBHOOK_PATH

        try:

            result = await bot.set_webhook(
                url=webhook_url,
                secret_token=WEBHOOK_SECRET
            )

            print("========================================")
            print("🤖 Telegram AI Bot запущен!")
            print("Webhook URL:", webhook_url)
            print("set_webhook result:", result)

            info = await bot.get_webhook_info()

            print("----------------------------------------")
            print("Telegram webhook info:")
            print("URL:", info.url)
            print("Pending updates:", info.pending_update_count)
            print("Last error:", info.last_error_message)
            print("----------------------------------------")
            print("========================================")

        except Exception as e:

            print("❌ WEBHOOK ERROR")
            print(type(e).__name__)
            print(str(e))
            print(repr(e))

    yield

    try:

        await bot.delete_webhook()

        await bot.session.close()
        await client.close()

        print("🛑 Бот остановлен.")

    except Exception as e:

        print("Shutdown error:", repr(e))


# ==========================================
# FASTAPI
# ==========================================

app = FastAPI(
    lifespan=lifespan
)


# ==========================================
# /START
# ==========================================

@dp.message(CommandStart())
async def start(message: Message):

    await message.answer(
        "Привет! 🤖\n\n"
        "Я AI-бот на Gemini.\n\n"
        "💬 В личном чате просто напиши сообщение.\n"
        "👥 В группе используй:\n"
        "/ask твой вопрос"
    )


# ==========================================
# /ASK
# ==========================================

@dp.message(Command("ask"))
async def ask_command(
    message: Message,
    command: CommandObject
):

    if not command.args:

        await message.answer(
            "❗ После /ask нужно написать вопрос.\n\n"
            "Пример:\n"
            "/ask Что такое Python?"
        )

        return

    # Передаём текст после /ask в AI
    await ask_ai(
        message,
        command.args
    )


# ==========================================
# ОБЫЧНЫЕ СООБЩЕНИЯ
# ==========================================

@dp.message()
async def normal_message(message: Message):

    # В группах обычные сообщения игнорируем
    if message.chat.type != "private":
        return

    # Игнорируем сообщения без текста
    if not message.text:
        return

    # В личке /ask НЕ нужен
    await ask_ai(
        message,
        message.text
    )


# ==========================================
# AI / OPENROUTER / GEMINI
# ==========================================

async def ask_ai(
    message: Message,
    text: str
):

    try:

        print("========================================")
        print("🤖 Новый AI-запрос")
        print("Текст:", text)
        print("Модель:", MODEL)
        print("Отправляем запрос в OpenRouter...")

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

        print("✅ OpenRouter ответил!")

        answer = response.choices[0].message.content

        if not answer:

            answer = (
                "⚠️ Gemini не вернула текстовый ответ."
            )

        await message.answer(answer)

        print("✅ Ответ отправлен в Telegram")
        print("========================================")

    except Exception as e:

        print("========================================")
        print("❌❌❌ AI ERROR ❌❌❌")
        print("Тип ошибки:", type(e).__name__)
        print("Ошибка:", str(e))
        print("Полная ошибка:", repr(e))
        print("❌❌❌ END ERROR ❌❌❌")
        print("========================================")

        # ВРЕМЕННО показываем ошибку,
        # чтобы найти проблему
        error_text = str(e)

        if not error_text:
            error_text = "Неизвестная ошибка"

        await message.answer(
            "⚠️ Ошибка AI:\n\n"
            f"{type(e).__name__}: "
            f"{error_text[:1500]}"
        )


# ==========================================
# ПРОВЕРКА RENDER
# ==========================================

@app.get("/")
async def home():

    return {
        "status": "online",
        "bot": "Telegram AI Bot",
        "webhook": "active"
    }


# ==========================================
# TELEGRAM WEBHOOK
# ==========================================

@app.post(WEBHOOK_PATH)
async def telegram_webhook(
    request: Request
):

    # Проверяем секретный токен
    secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token"
    )

    if secret != WEBHOOK_SECRET:

        print("❌ Неверный webhook secret")

        return {
            "ok": False
        }

    try:

        # Получаем данные от Telegram
        data = await request.json()

        # Превращаем JSON в Update
        update = Update.model_validate(
            data,
            context={
                "bot": bot
            }
        )

        # Передаём сообщение aiogram
        await dp.feed_update(
            bot,
            update
        )

        return {
            "ok": True
        }

    except Exception as e:

        print("❌ TELEGRAM UPDATE ERROR")
        print(type(e).__name__)
        print(str(e))
        print(repr(e))

        return {
            "ok": False
        }
