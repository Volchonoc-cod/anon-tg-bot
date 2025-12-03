"""
Главный файл запуска бота с поддержкой Render
"""
import asyncio
import sys
import os
import logging
from datetime import datetime
import signal

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

async def run_bot():
    """Основная функция запуска бота"""
    try:
        logger.info("🔄 Инициализация бота...")
        
        from app.config import BOT_TOKEN, ADMIN_IDS, IS_RENDER
        from app.database import create_tables
        from aiogram import Bot, Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        
        # Создаем необходимые папки
        os.makedirs('data', exist_ok=True)
        os.makedirs('backups', exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        
        # Создаем таблицы БД
        create_tables()
        logger.info("✅ Таблицы БД созданы")
        
        # Инициализация бота
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher(storage=MemoryStorage())
        
        # Импорт роутеров
        from app.handlers.admin_panel import router as admin_router
        from app.handlers.payment_handlers import router as payment_router
        from app.handlers.anon_handlers import router as anon_router
        from app.handlers.main_handlers import router as main_router
        from app.handlers.debug_handlers import router as debug_router
        
        # Регистрация роутеров
        dp.include_router(admin_router)
        dp.include_router(payment_router)
        dp.include_router(anon_router)
        dp.include_router(main_router)
        dp.include_router(debug_router)
        
        logger.info("✅ Все роутеры зарегистрированы")
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"✅ Bot: @{bot_info.username} ({bot_info.first_name})")
        
        # Отправляем уведомление админам о запуске
        try:
            message = (
                f"🚀 <b>Бот запущен!</b>\n\n"
                f"🤖 @{bot_info.username}\n"
                f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"🌐 Render: {'✅ Да' if IS_RENDER else '❌ Нет'}\n"
                f"👥 Админов: {len(ADMIN_IDS)}"
            )
            
            for admin_id in ADMIN_IDS:
                await bot.send_message(admin_id, message, parse_mode="HTML")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления: {e}")
        
        # Запускаем поллинг
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("🚀 Бот начал работу...")
        
        # Для Render: также запускаем авто-пинг отдельно
        if IS_RENDER:
            logger.info("🌐 Режим Render: авто-пинг включен")
            
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в run_bot: {e}")
        import traceback
        traceback.print_exc()
        
        # Пытаемся уведомить админа об ошибке
        try:
            from app.config import BOT_TOKEN, ADMIN_IDS
            bot = Bot(token=BOT_TOKEN)
            for admin_id in ADMIN_IDS:
                await bot.send_message(
                    admin_id,
                    f"🚨 <b>Бот упал!</b>\n\n"
                    f"Ошибка: {str(e)[:200]}...\n"
                    f"Время: {datetime.now().strftime('%H:%M:%S')}",
                    parse_mode="HTML"
                )
        except:
            pass
        
        sys.exit(1)

def handle_shutdown(signum, frame):
    """Обработчик завершения работы"""
    logger.info(f"🛑 Получен сигнал {signum}. Завершаю работу...")
    sys.exit(0)

def main():
    """Точка входа - для запуска бота отдельно"""
    # Настройка обработчиков сигналов
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Бот аварийно завершил работу: {e}")
        sys.exit(1)

async def run_bot_async():
    """Асинхронная версия для запуска из render_server.py"""
    try:
        print("🤖 Запуск бота в асинхронном режиме...")
        
        # Сначала импортируем ВСЕ модели
        from app import models  # Это важно!
        
        from app.config import BOT_TOKEN, ADMIN_IDS, IS_RENDER
        from app.database import create_tables
        
        # Создаем папки
        import os
        os.makedirs('data', exist_ok=True)
        os.makedirs('backups', exist_ok=True)
        
        # Создаем таблицы - ТЕПЕРЬ модели загружены
        print("🔄 Создание таблиц БД...")
        create_tables()
        print("✅ Таблицы БД созданы")
        
        # Проверяем таблицы
        from sqlalchemy import inspect
        from app.database import engine
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"📊 Таблицы в БД: {tables}")
        # Инициализация бота
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher(storage=MemoryStorage())
        
        # Импорт роутеров
        from app.handlers.admin_panel import router as admin_router
        from app.handlers.payment_handlers import router as payment_router
        from app.handlers.anon_handlers import router as anon_router
        from app.handlers.main_handlers import router as main_router
        from app.handlers.debug_handlers import router as debug_router
        
        # Регистрация
        dp.include_router(admin_router)
        dp.include_router(payment_router)
        dp.include_router(anon_router)
        dp.include_router(main_router)
        dp.include_router(debug_router)
        
        logger.info("✅ Все роутеры зарегистрированы")
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"✅ Bot: @{bot_info.username}")
        
        # Уведомление админам о запуске
        try:
            message = (
                f"🚀 <b>Бот запущен на Render!</b>\n\n"
                f"🤖 @{bot_info.username}\n"
                f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"✅ Авто-пинг включен"
            )
            
            for admin_id in ADMIN_IDS:
                await bot.send_message(admin_id, message, parse_mode="HTML")
        except Exception as e:
            logger.error(f"❌ Ошибка уведомления: {e}")
        
        # Запуск поллинга
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("🚀 Бот начал работу (поллинг)...")
        
        # Запускаем поллинг
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в run_bot_async: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
