#!/usr/bin/env python3
import asyncio
import sys
import os
import logging

sys.path.append(os.path.dirname(__file__))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_bot():
    try:
        from app.config import BOT_TOKEN
        from app.database import create_tables
        from app.handlers.main_handlers import router as main_router
        from app.handlers.anon_handlers import router as anon_router
        from app.handlers.payment_handlers import router as payment_router
        from app.handlers.admin_handlers import router as admin_router

        from aiogram import Bot, Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage

        # Создаем необходимые директории
        os.makedirs('data', exist_ok=True)
        os.makedirs('backups', exist_ok=True)
        os.makedirs('logs', exist_ok=True)

        # Создаем таблицы в БД
        create_tables()
        logger.info("✅ Database tables created")

        # ПРОСТАЯ инициализация бота с таймаутом
        bot = Bot(token=BOT_TOKEN, timeout=60)
        dp = Dispatcher(storage=MemoryStorage())

        # Регистрация роутеров
        dp.include_router(anon_router)
        dp.include_router(main_router)
        dp.include_router(payment_router)
        dp.include_router(admin_router)

        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"✅ Bot: @{bot_info.username} ({bot_info.first_name})")

        # Отправляем уведомление о запуске
        try:
            from app.config import ADMIN_IDS
            from datetime import datetime

            message = (
                "🚀 **Бот запущен**\n\n"
                f"• Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                "• Статус: ✅ Работает\n"
                "• Версия: Fixed"
            )
            for admin_id in ADMIN_IDS:
                await bot.send_message(admin_id, message, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"❌ Error sending startup notification: {e}")

        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("🚀 Bot started polling...")

        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped")