#!/usr/bin/env python3
import asyncio
import sys
import os
import logging
from datetime import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_bot():
    try:
        logger.info("🔄 Инициализация бота...")
        
        from app.config import BOT_TOKEN, ADMIN_IDS
        from app.database import create_tables
        from aiogram import Bot, Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage

        os.makedirs('data', exist_ok=True)
        os.makedirs('backups', exist_ok=True)

        create_tables()
        logger.info("✅ Database tables created")

        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher(storage=MemoryStorage())

        # ПРАВИЛЬНЫЕ ИМПОРТЫ ИЗ ПАПКИ handlers
        from app.handlers.admin_panel import router as admin_router
        from app.handlers.payment_handlers import router as payment_router
        from app.handlers.anon_handlers import router as anon_router
        from app.handlers.main_handlers import router as main_router
        from app.handlers.debug_handlers import router as debug_router

        dp.include_router(admin_router)
        dp.include_router(payment_router)
        dp.include_router(anon_router)
        dp.include_router(main_router)
        dp.include_router(debug_router)
        
        logger.info("✅ Все роутеры зарегистрированы")

        bot_info = await bot.get_me()
        logger.info(f"✅ Bot: @{bot_info.username} ({bot_info.first_name})")

        try:
            message = f"✅ Бот @{bot_info.username} запущен!\nВремя: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            for admin_id in ADMIN_IDS:
                await bot.send_message(admin_id, message)
        except Exception as e:
            logger.error(f"❌ Error sending startup notification: {e}")

        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("🚀 Bot started polling...")

        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"❌ Critical error in run_bot: {e}")
        import traceback
        traceback.print_exc()

def main():
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
