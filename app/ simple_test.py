#!/usr/bin/env python3
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()


async def simple_test():
    """Простой тест базовой функциональности"""
    logging.basicConfig(level=logging.INFO)

    try:
        from aiogram import Bot, Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        from app.config import BOT_TOKEN

        print("🔧 Инициализация бота...")
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher(storage=MemoryStorage())

        print("🔧 Получение информации о боте...")
        bot_info = await bot.get_me()
        print(f"✅ Бот: @{bot_info.username} ({bot_info.first_name})")

        print("🔧 Тест отправки сообщения...")
        await bot.send_message(5784508611, "🤖 Бот работает! Простой тест пройден.")

        await bot.session.close()
        print("🎉 Простой тест завершен успешно!")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(simple_test())