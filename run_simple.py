#!/usr/bin/env python3
import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    try:
        from aiogram import Bot, Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        from app.config import BOT_TOKEN
        from app.database import create_tables

        # Базовая настройка
        os.makedirs('data', exist_ok=True)
        create_tables()

        # Минимальная инициализация
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher(storage=MemoryStorage())

        # Простой хендлер для теста
        from aiogram import F
        from aiogram.types import Message

        @dp.message(F.text == "/start")
        async def cmd_start(message: Message):
            await message.answer("✅ Бот работает!")

        # Запуск
        bot_info = await bot.get_me()
        logger.info(f"✅ Bot: @{bot_info.username}")

        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())