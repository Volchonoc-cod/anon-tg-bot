#!/usr/bin/env python3
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    # Прямой токен в коде (убедитесь что он правильный!)
    BOT_TOKEN = "8502318494:AAF4g7zbHMY-wePB37EnasDaZi5Qe8nNk6o"

    if not BOT_TOKEN or BOT_TOKEN == "8502318494:AAF4g7zbHMY-wePB37EnasDaZi5Qe8nNk6o":
        logger.error("❌ ЗАМЕНИТЕ BOT_TOKEN на реальный токен от @BotFather!")
        return

    try:
        # Используем session-based подход
        bot = Bot(
            token=BOT_TOKEN,
            session=None,  # Будет создана автоматически
            default=DefaultBotProperties(
                parse_mode="HTML",
                link_preview_is_disabled=True
            )
        )

        dp = Dispatcher(storage=MemoryStorage())

        # Простой хендлер
        @dp.message(types.Message)
        async def echo(message: types.Message):
            await message.answer(f"✅ Бот работает! Вы написали: {message.text}")

        # Тестируем подключение
        logger.info("🔄 Тестируем базовое подключение...")

        # Пробуем разные методы
        methods = [
            lambda: bot.get_me(),
            lambda: bot.send_message(5784508611, "🤖 Тест подключения"),
        ]

        for i, method in enumerate(methods):
            try:
                result = await method()
                logger.info(f"✅ Метод {i + 1} работает: {result}")
            except Exception as e:
                logger.error(f"❌ Метод {i + 1} не работает: {e}")
                continue

        # Если дошли сюда, запускаем бота
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("🚀 Запускаем бота...")
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        logger.info("\n🎯 РЕШЕНИЯ:")
        logger.info("1. ИСПОЛЬЗУЙТЕ VPN - это 100% решение")
        logger.info("2. Запустите на VPS (DigitalOcean, Hetzner)")
        logger.info("3. Используйте облачный хостинг (Railway, Heroku)")
        logger.info("4. Создайте нового бота с новым токеном")


if __name__ == "__main__":
    asyncio.run(main())
