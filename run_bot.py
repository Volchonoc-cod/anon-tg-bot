"""
Главный файл запуска бота
"""
import asyncio
import sys
import os
import logging
from datetime import datetime
import signal
import time


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

# ============ НОВОЕ: Функции для предотвращения дублирования бота ============

def check_if_bot_already_running():
    """
    Проверить, не запущен ли уже бот.
    
    Проблема: На Render иногда запускается несколько экземпляров бота,
    что приводит к ошибке: TelegramConflictError: terminated by other getUpdates request
    
    Решение: Создаем файл блокировки (lock file) с PID процесса.
    """
    try:
        # Простая проверка по наличию файла блокировки
        lock_file = os.path.join(current_dir, 'data', 'bot.lock')
        if os.path.exists(lock_file):
            # Проверяем, жив ли процесс
            with open(lock_file, 'r') as f:
                pid = f.read().strip()
                try:
                    os.kill(int(pid), 0)  # Проверяем существование процесса (сигнал 0)
                    logger.warning(f"⚠️ Бот уже запущен (PID: {pid}). Завершаем этот экземпляр...")
                    return True  # Процесс еще работает
                except OSError:
                    # Процесс не существует, удаляем старый lock файл
                    logger.info(f"🗑️ Старый lock файл найден для несуществующего PID {pid}. Удаляю...")
                    os.remove(lock_file)
                    return False
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке lock файла: {e}")
        return False

def create_lock_file():
    """
    Создать файл блокировки с PID текущего процесса.
    
    Это предотвратит запуск второго экземпляра бота.
    """
    try:
        lock_file = os.path.join(current_dir, 'data', 'bot.lock')
        os.makedirs(os.path.dirname(lock_file), exist_ok=True)
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"🔒 Создан lock файл (PID: {os.getpid()})")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка создания lock файла: {e}")
        return False

def remove_lock_file():
    """
    Удалить файл блокировки при завершении работы.
    
    Важно: Если бот завершается аварийно, lock файл должен быть удален,
    иначе новый экземпляр не сможет запуститься.
    """
    try:
        lock_file = os.path.join(current_dir, 'data', 'bot.lock')
        if os.path.exists(lock_file):
            # Проверяем, наш ли это PID
            with open(lock_file, 'r') as f:
                stored_pid = f.read().strip()
                if stored_pid == str(os.getpid()):
                    os.remove(lock_file)
                    logger.info(f"🔓 Удален lock файл (PID: {os.getpid()})")
                else:
                    logger.warning(f"⚠️ Lock файл принадлежит другому процессу (PID: {stored_pid}). Не удаляю.")
    except Exception as e:
        logger.error(f"❌ Ошибка удаления lock файла: {e}")

# ============ КОНЕЦ НОВЫХ ФУНКЦИЙ ============

def setup_directories():
    """Создание необходимых директорий"""
    directories = ['data', 'backups', 'logs', 'uploads']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"📁 Создана директория: {directory}")

async def initialize_bot():
    """Инициализация бота"""
    try:
        logger.info("🔄 Инициализация бота...")
        
        # ============ НОВОЕ: Проверка на уже запущенный бот ============
        if check_if_bot_already_running():
            # Ждем немного, чтобы другой процесс мог корректно запуститься
            await asyncio.sleep(5)
            logger.error("❌ Бот уже запущен! Завершаем этот экземпляр...")
            return None, None
        # ============ КОНЕЦ НОВОГО КОДА ============
        
        # Создаем папки
        setup_directories()
        
        # ============ НОВОЕ: Создаем lock файл ============
        if not create_lock_file():
            logger.error("❌ Не удалось создать lock файл. Завершаем...")
            return None, None
        # ============ КОНЕЦ НОВОГО КОДА ============
        
        # ============ КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ: ИНИЦИАЛИЗАЦИЯ БД ПЕРВОЙ ============
        logger.info("🚀 ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ...")
        try:
            from app.database import init_db
            if not init_db():
                logger.error("❌ Не удалось инициализировать базу данных!")
                # НЕ ЗАВЕРШАЕМ, пробуем продолжить, возможно таблицы уже есть
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")
            import traceback
            traceback.print_exc()
        # ============ КОНЕЦ КРИТИЧЕСКОГО ИЗМЕНЕНИЯ ============
        
        # Загружаем конфигурацию
        from app.config import BOT_TOKEN, ADMIN_IDS
        
        if not BOT_TOKEN:
            raise ValueError("❌ BOT_TOKEN не найден в конфигурации")
        
        logger.info(f"✅ Конфигурация загружена: Bot Token = {BOT_TOKEN[:10]}...")
        logger.info(f"✅ Админы: {ADMIN_IDS}")
        
        # Создаем бота
        from aiogram import Bot
        bot = Bot(token=BOT_TOKEN)
        
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
        from app.handlers.conversations_admin import router as conversations_router

        
        dp.include_router(conversations_router)        
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
        
        # ============ НОВОЕ: Проверяем, был ли бот успешно инициализирован ============
        if bot is None or dp is None:
            logger.error("❌ Бот не был инициализирован. Завершаем...")
            return
        # ============ КОНЕЦ НОВОГО КОДА ============
        
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
    
    # ============ НОВОЕ: Удаляем lock файл при завершении ============
    remove_lock_file()
    # ============ КОНЕЦ НОВОГО КОДА ============
    
    sys.exit(0)

def main():
    """Точка входа"""
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
        # ============ НОВОЕ: Удаляем lock файл ============
        remove_lock_file()
        # ============ КОНЕЦ НОВОГО КОДА ============
    except Exception as e:
        logger.error(f"❌ Бот аварийно завершил работу: {e}")
        # ============ НОВОЕ: Удаляем lock файл ============
        remove_lock_file()
        # ============ КОНЕЦ НОВОГО КОДА ============
        sys.exit(1)

if __name__ == "__main__":
    main()
