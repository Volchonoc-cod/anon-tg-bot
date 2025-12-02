#!/usr/bin/env python3
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp_socks import ProxyConnector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    try:
        from app.config import BOT_TOKEN
        from app.database import create_tables

        # Настройка прокси (опционально)
        # connector = ProxyConnector.from_url('socks5://user:pass@host:port')

        # Без прокси, но с увеличенными таймаутами
        bot = Bot(token=BOT_TOKEN, timeout=90)
        dp = Dispatcher(storage=MemoryStorage())

        # Базовая настройка
        os.makedirs('data', exist_ok=True)
        create_tables()

        # Простой хендлер
        from aiogram import F
        from aiogram.types import Message

        @dp.message(F.text == "/start")
        async def cmd_start(message: Message):
            await message.answer("✅ Бот работает!")

        # Запуск
        logger.info("🔄 Подключаемся к Telegram...")
        bot_info = await bot.get_me()
        logger.info(f"✅ Bot: @{bot_info.username}")

        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("🚀 Bot started polling...")
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())