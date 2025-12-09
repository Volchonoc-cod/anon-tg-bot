"""
Главный файл запуска бота с поддержкой вебхуков и поллинга
"""
import asyncio
import sys
import os
import logging
from datetime import datetime
import signal

# Определяем, запущен ли бот отдельно или из render_server.py
STANDALONE_BOT = __name__ == "__main__"

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
    ] if STANDALONE_BOT else [logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Флаг для отслеживания запуска
_bot_initialized = False
_bot_instance = None
_dp_instance = None

def setup_directories():
    """Создание необходимых директорий"""
    directories = ['data', 'backups', 'logs']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"📁 Создана директория: {directory}")

def create_database_tables():
    """Создает таблицы в базе данных (исправлено для избежания циклических импортов)"""
    try:
        # Импортируем engine из database
        from app.database import engine
        from app.models import Base
        
        # Создаем все таблицы
        Base.metadata.create_all(bind=engine)
        
        # Проверяем таблицы
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        logger.info(f"📊 Таблицы в БД созданы: {tables}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц БД: {e}")
        import traceback
        traceback.print_exc()
        return False

async def initialize_bot():
    """Инициализация бота - вызывается только один раз"""
    global _bot_initialized, _bot_instance, _dp_instance
    
    if _bot_initialized:
        logger.warning("⚠️ Бот уже инициализирован, возвращаем существующие экземпляры")
        return _bot_instance, _dp_instance
    
    _bot_initialized = True
    
    try:
        logger.info("🔄 Инициализация бота...")
        
        # 1. Создаем папки
        setup_directories()
        
        # 2. Инициализируем конфигурацию
        from app.config import BOT_TOKEN, ADMIN_IDS, IS_RENDER
        
        if not BOT_TOKEN:
            raise ValueError("❌ BOT_TOKEN не найден в конфигурации")
        
        logger.info(f"✅ Конфигурация загружена: Bot Token = {BOT_TOKEN[:10]}...")
        logger.info(f"✅ Админы: {ADMIN_IDS}")
        logger.info(f"✅ Render: {IS_RENDER}")
        
        # 3. Создаем таблицы БД
        logger.info("🔄 Создание таблиц БД...")
        if create_database_tables():
            logger.info("✅ Таблицы БД созданы успешно")
        else:
            logger.error("❌ Не удалось создать таблицы БД, продолжаем работу...")
        
        # 4. Инициализируем менеджер БД ПОСЛЕ создания таблиц
        logger.info("💾 Инициализация менеджера БД...")
        try:
            # Импортируем здесь, чтобы избежать циклических импортов
            from app.database_manager import init_database_manager
            restored = init_database_manager()
            if restored:
                logger.info("✅ БД восстановлена из последнего бэкапа")
            else:
                logger.info("✅ Восстановление БД не требовалось")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации менеджера БД: {e}")
            # Продолжаем работу
        
        # 5. Инициализируем самого бота
        from aiogram import Bot, Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher(storage=MemoryStorage())
        
        # Сохраняем экземпляры
        _bot_instance = bot
        _dp_instance = dp
        
        # 6. Регистрируем роутеры
        logger.info("📋 Регистрация роутеров...")
        
        # Импорт роутеров
        try:
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
        except Exception as e:
            logger.error(f"❌ Ошибка регистрации роутеров: {e}")
            raise
        
        # 7. Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"✅ Bot: @{bot_info.username} ({bot_info.first_name})")
        
        return bot, dp
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка инициализации бота: {e}")
        import traceback
        traceback.print_exc()
        raise

async def notify_admins_on_startup(bot, is_webhook=False):
    """Отправляет уведомление администраторам о запуске"""
    try:
        from app.config import ADMIN_IDS
        
        mode = "вебхуки" if is_webhook else "поллинг"
        bot_info = await bot.get_me()
        
        # Получаем информацию о БД
        db_size = 0
        backup_count = 0
        try:
            from app.database_manager import db_manager
            db_info = db_manager.get_db_info()
            db_size = db_info.get('size_mb', 0)
            backup_count = len(db_manager.list_backups())
        except:
            pass
        
        message = (
            f"🚀 <b>Бот запущен ({mode})!</b>\n\n"
            f"🤖 @{bot_info.username}\n"
            f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"🌐 Режим: {mode}\n"
            f"👥 Админов: {len(ADMIN_IDS)}\n"
            f"💾 БД: {db_size:.2f} MB\n"
            f"📂 Бэкапов: {backup_count}\n"
            f"📝 /backup - создать бэкап\n"
            f"📋 /backups - список бэкапов"
        )
        
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, message, parse_mode="HTML")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомления: {e}")

async def run_polling():
    """Запуск бота в режиме поллинга (для локальной разработки)"""
    try:
        bot, dp = await initialize_bot()
        
        # Отправляем уведомление о запуске
        await notify_admins_on_startup(bot, is_webhook=False)
        
        # Удаляем вебхук если был
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("🚀 Бот начал работу (поллинг)...")
        
        # Запускаем поллинг
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в режиме поллинга: {e}")
        import traceback
        traceback.print_exc()
        
        # Пытаемся уведомить админа об ошибке
        try:
            from app.config import BOT_TOKEN, ADMIN_IDS
            from aiogram import Bot
            
            bot = Bot(token=BOT_TOKEN)
            for admin_id in ADMIN_IDS:
                await bot.send_message(
                    admin_id,
                    f"🚨 <b>Бот упал (поллинг)!</b>\n\n"
                    f"Ошибка: {str(e)[:200]}...\n"
                    f"Время: {datetime.now().strftime('%H:%M:%S')}",
                    parse_mode="HTML"
                )
        except:
            pass
        
        sys.exit(1)

async def run_webhook_mode():
    """Запуск бота в режиме ожидания вебхуков (для Render)"""
    try:
        logger.info("🌐 Запуск в режиме ожидания вебхуков...")
        
        bot, dp = await initialize_bot()
        
        # Отправляем уведомление о запуске
        await notify_admins_on_startup(bot, is_webhook=True)
        
        logger.info("✅ Бот инициализирован для вебхуков")
        logger.info("📡 Ожидаю обновления через вебхуки...")
        
        # Бесконечное ожидание (вебхуки будут обрабатываться render_server.py)
        while True:
            await asyncio.sleep(3600)  # Спим по часу
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в режиме вебхуков: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

async def run_bot():
    """Основная функция запуска бота - определяет режим работы"""
    # Проверяем, запущен ли бот на Render
    is_render = os.getenv('RENDER', '').lower() == 'true'
    
    if is_render:
        # На Render используем режим ожидания вебхуков
        logger.info("🌐 Обнаружен Render, использую режим вебхуков")
        await run_webhook_mode()
    else:
        # Локально используем поллинг
        logger.info("💻 Локальный запуск, использую поллинг")
        await run_polling()

async def run_bot_async():
    """
    Асинхронная версия для запуска из других модулей
    Используется render_server.py
    """
    logger.info("🤖 Запуск бота в асинхронном режиме...")
    await run_bot()

def handle_shutdown(signum, frame):
    """Обработчик завершения работы"""
    logger.info(f"🛑 Получен сигнал {signum}. Завершаю работу...")
    
    # Создаем бэкап перед выходом
    try:
        from app.database_manager import db_manager
        db_manager.create_backup_on_exit()
    except Exception as e:
        logger.error(f"❌ Ошибка создания бэкапа при выходе: {e}")
    
    sys.exit(0)

def get_bot_instances():
    """Возвращает экземпляры бота и диспетчера (для render_server.py)"""
    return _bot_instance, _dp_instance

def main():
    """Точка входа - для запуска бота отдельно (не из Render)"""
    # Настройка обработчиков сигналов
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, signal_handler=handle_shutdown)
    
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
        # Создаем бэкап при ручной остановке
        try:
            from app.database_manager import db_manager
            db_manager.create_backup_on_exit()
        except:
            pass
    except Exception as e:
        logger.error(f"❌ Бот аварийно завершил работу: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
