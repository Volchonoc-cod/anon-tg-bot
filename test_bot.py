import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)


async def test_bot():
    from aiogram import Bot

    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден!")
        return

    bot = Bot(token=BOT_TOKEN, timeout=60)

    try:
        me = await bot.get_me()
        print(f"✅ Бот: @{me.username} ({me.first_name})")
        await bot.send_message(5784508611, "🤖 Бот запущен и работает!")
        print("✅ Тестовое сообщение отправлено")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(test_bot())