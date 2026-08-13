import os
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.filters.command import CommandObject
from openai import AsyncOpenAI


# =========================
# НАСТРОЙКИ
# =========================

BOT_TOKEN = os.environ["BOT_TOKEN"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

MODEL = "google/gemini-3.1-flash-lite-preview"


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
# /ASK ДЛЯ ГРУПП И КАНАЛОВ
# =========================

@dp.message(Command("ask"))
async def ask_command(
    message: Message,
    command: CommandObject
):

    # Если /ask используется в личке,
    # тоже разрешаем его
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

    # Только личные сообщения
    if message.chat.type != "private":
        return

    # Если сообщение не текстовое
    if not message.text:
        return

    await ask_ai(message, message.text)


# =========================
# ЗАПРОС К GEMINI
# =========================

async def ask_ai(message: Message, text: str):

    try:

        # Показываем пользователю, что бот думает
        await message.bot.send_chat_action(
            chat_id=message.chat.id,
            action="typing"
        )

        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты дружелюбный и полезный AI-ассистент "
                        "в Telegram."
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
            answer = "Не удалось получить ответ от модели."

        await message.answer(answer)

    except Exception as e:

        print("ERROR:", repr(e))

        await message.answer(
            "⚠️ Произошла ошибка при обращении к AI."
        )


# =========================
# ЗАПУСК
# =========================

async def main():

    print("🤖 Бот запущен!")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())