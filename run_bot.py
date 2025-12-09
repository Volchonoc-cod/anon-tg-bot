"""
Главный файл запуска бота
"""
import asyncio
import sys
import os
import logging
from datetime import datetime
import signal

# Настройка пути
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

def setup_directories():
    """Создание необходимых директорий"""
    directories = ['data', 'backups', 'logs']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"📁 Создана директория: {directory}")

def create_database_tables():
    """Создает таблицы в базе данных"""
    try:
        from app.database import engine
        from app.models import Base
        
        Base.metadata.create_all(bind=engine)
        
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        logger.info(f"📊 Таблицы в БД созданы: {tables}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц БД: {e}")
        return False

async def initialize_bot():
    """Инициализация бота"""
    try:
        logger.info("🔄 Инициализация бота...")
        
        # Создаем папки
        setup_directories()
        
        # Загружаем конфигурацию
        from app.config import BOT_TOKEN, ADMIN_IDS
        
        if not BOT_TOKEN:
            raise ValueError("❌ BOT_TOKEN не найден в конфигурации")
        
        logger.info(f"✅ Конфигурация загружена: Bot Token = {BOT_TOKEN[:10]}...")
        logger.info(f"✅ Админы: {ADMIN_IDS}")
        
        # Создаем бота сразу, чтобы передать его в менеджер БД
        from aiogram import Bot
        bot = Bot(token=BOT_TOKEN)
        
        # Создаем таблицы БД
        logger.info("🔄 Создание таблиц БД...")
        if create_database_tables():
            logger.info("✅ Таблицы БД созданы успешно")
        else:
            logger.error("❌ Не удалось создать таблицы БД")
        
        # Инициализируем менеджер БД с ботом
        logger.info("💾 Инициализация менеджера БД...")
        try:
            from app.database_manager import init_database_manager
            init_database_manager(bot)  # Передаем бота для отправки уведомлений
            logger.info("✅ Менеджер БД инициализирован с ботом")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации менеджера БД: {e}")
        
        # Создаем диспетчер
        from aiogram import Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        
        # Регистрируем роутеры
        logger.info("📋 Регистрация роутеров...")
        
        from app.handlers.main_handlers import router as main_router
        from app.handlers.admin_panel import router as admin_router
        from app.handlers.payment_handlers import router as payment_router
        from app.handlers.anon_handlers import router as anon_router
        from app.handlers.debug_handlers import router as debug_router
        
        dp.include_router(main_router)
        dp.include_router(admin_router)
        dp.include_router(payment_router)
        dp.include_router(anon_router)
        dp.include_router(debug_router)
        
        logger.info("✅ Все роутеры зарегистрированы")
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"✅ Bot: @{bot_info.username} ({bot_info.first_name})")
        
        # Отправляем уведомление админам
        try:
            from app.database_manager import db_manager
            db_info = db_manager.get_db_info()
            backup_count = len(db_manager.list_backups())
            
            message = (
                f"🚀 <b>Бот запущен на Render!</b>\n\n"
                f"🤖 @{bot_info.username}\n"
                f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"👥 Админов: {len(ADMIN_IDS)}\n"
                f"💾 БД: {db_info.get('size_mb', 0):.2f} MB\n"
                f"📂 Бэкапов: {backup_count}\n\n"
                f"✅ Готов к работе!"
            )
            
            for admin_id in ADMIN_IDS:
                await bot.send_message(admin_id, message, parse_mode="HTML")
                logger.info(f"📨 Уведомление отправлено админу {admin_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления: {e}")
        
        return bot, dp
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка инициализации бота: {e}")
        import traceback
        traceback.print_exc()
        raise

async def run_bot():
    """Запуск бота"""
    try:
        bot, dp = await initialize_bot()
        
        # Удаляем вебхук если был (чтобы не было конфликтов)
        await bot.delete_webhook(drop_pending_updates=True)
        
        logger.info("🚀 Бот начал работу (поллинг)...")
        
        # Запускаем поллинг
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в работе бота: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

async def run_bot_async():
    """Асинхронная версия для запуска из render_server.py"""
    await run_bot()

def handle_shutdown(signum, frame):
    """Обработчик завершения работы"""
    logger.info(f"🛑 Получен сигнал {signum}. Завершаю работу...")
    sys.exit(0)

def main():
    """Точка входа"""
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Бот аварийно завершил работу: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
