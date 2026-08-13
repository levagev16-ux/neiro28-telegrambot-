import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Update, Message
from aiogram.filters.command import CommandObject
from openai import AsyncOpenAI


# ==========================================
# НАСТРОЙКИ
# ==========================================

BOT_TOKEN = os.environ["BOT_TOKEN"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]

# Модель Gemini через OpenRouter
MODEL = "google/gemini-3.1-flash-lite-preview"

# Путь webhook
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
# WEBHOOK
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

            # Проверяем webhook
            info = await bot.get_webhook_info()

            print("----------------------------------------")
            print("Telegram webhook info:")
            print("URL:", info.url)
            print("Pending updates:", info.pending_update_count)
            print("Last error:", info.last_error_message)
            print("----------------------------------------")
            print("========================================")

        except Exception as e:

            print("❌ WEBHOOK ERROR:")
            print(repr(e))

    yield

    # При остановке Render удаляем webhook
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
# START
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

    # Проверяем наличие текста после /ask
    if not command.args:

        await message.answer(
            "❗ После /ask нужно написать вопрос.\n\n"
            "Пример:\n"
            "/ask Что такое Python?"
        )

        return

    # Отправляем вопрос AI
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

    # В личке отвечаем без /ask
    await ask_ai(
        message,
        message.text
    )


# ==========================================
# AI
# ==========================================

async def ask_ai(
    message: Message,
    text: str
):

    try:

        # Показываем "печатает..."
        await bot.send_chat_action(
            chat_id=message.chat.id,
            action="typing"
        )

        # Запрос к OpenRouter
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

        # Получаем ответ Gemini
        answer = response.choices[0].message.content

        if not answer:

            answer = (
                "⚠️ Gemini не вернула текстовый ответ."
            )

        # Отправляем ответ
        await message.answer(
            answer
        )

    except Exception as e:

        print("================================")
        print("❌ AI ERROR")
        print(repr(e))
        print("================================")

        await message.answer(
            "⚠️ Произошла ошибка при обращении к AI."
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
# TELEGRAM WEBHOOK ENDPOINT
# ==========================================

@app.post(WEBHOOK_PATH)
async def telegram_webhook(
    request: Request
):

    # Проверяем секрет Telegram
    secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token"
    )

    if secret != WEBHOOK_SECRET:

        print("❌ Неверный webhook secret")

        return {
            "ok": False
        }

    try:

        # Получаем JSON от Telegram
        data = await request.json()

        # Создаём Update aiogram
        update = Update.model_validate(
            data,
            context={
                "bot": bot
            }
        )

        # Передаём update в Dispatcher
        await dp.feed_update(
            bot,
            update
        )

        return {
            "ok": True
        }

    except Exception as e:

        print("❌ TELEGRAM UPDATE ERROR:")
        print(repr(e))

        return {
            "ok": False
        }
