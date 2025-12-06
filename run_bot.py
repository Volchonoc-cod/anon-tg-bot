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

# Импортируем менеджер БД
from app.database_manager import db_manager, backup_on_exit, init_database_manager

async def run_bot():
    """Основная функция запуска бота"""
    try:
        logger.info("🔄 Инициализация бота...")
        
        # 1. Создаем папку data если не существует
        os.makedirs('data', exist_ok=True)
        os.makedirs('backups', exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        
        logger.info("📁 Папки созданы: data, backups, logs")
        
        # 2. Проверяем существует ли БД
        db_path = 'data/bot.db'
        if not os.path.exists(db_path):
            logger.info("📝 База данных не найдена, будет создана новая")
        else:
            size = os.path.getsize(db_path)
            logger.info(f"📊 Существующая БД найдена: {size} байт")
        
        # 3. Инициализируем менеджер БД (автовосстановление при запуске)
        logger.info("💾 Инициализация менеджера БД...")
        try:
            restored = init_database_manager()
            if restored:
                logger.info("✅ БД восстановлена из последнего бэкапа")
            else:
                logger.info("✅ Восстановление БД не требовалось")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации менеджера БД: {e}")
            # Продолжаем работу даже если менеджер БД упал
        
        # 4. Показываем информацию о БД
        try:
            db_info = db_manager.get_db_info()
            logger.info(f"📊 Информация о БД: {db_info.get('size_mb', 0):.2f} MB, таблиц: {len(db_info.get('tables', []))}")
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о БД: {e}")
            db_info = {"exists": False, "size_mb": 0, "tables": []}
        
        from app.config import BOT_TOKEN, ADMIN_IDS, IS_RENDER
        from app.database import create_tables
        from aiogram import Bot, Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        
        # Создаем таблицы БД
        logger.info("🔄 Создание таблиц БД...")
        try:
            create_tables()
            logger.info("✅ Таблицы БД созданы")
        except Exception as e:
            logger.error(f"❌ Ошибка создания таблиц БД: {e}")
            # Продолжаем работу, возможно таблицы уже существуют
        
        # Создаем начальный бэкап если это первый запуск
        try:
            backups = db_manager.list_backups()
            if len(backups) == 0:
                logger.info("📝 Создание начального бэкапа...")
                backup_result = db_manager.create_backup("initial_backup.db")
                if backup_result:
                    logger.info(f"✅ Начальный бэкап создан: {backup_result}")
                else:
                    logger.warning("⚠️ Не удалось создать начальный бэкап")
        except Exception as e:
            logger.error(f"❌ Ошибка создания начального бэкапа: {e}")
        
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
            # Получаем актуальную информацию о БД
            try:
                db_info = db_manager.get_db_info()
                backup_count = len(db_manager.list_backups())
            except:
                db_info = {"size_mb": 0}
                backup_count = 0
            
            message = (
                f"🚀 <b>Бот запущен!</b>\n\n"
                f"🤖 @{bot_info.username}\n"
                f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"🌐 Render: {'✅ Да' if IS_RENDER else '❌ Нет'}\n"
                f"👥 Админов: {len(ADMIN_IDS)}\n"
                f"💾 БД: {db_info.get('size_mb', 0):.2f} MB\n"
                f"📂 Бэкапов: {backup_count}\n"
                f"📝 /backup - создать бэкап\n"
                f"📋 /backups - список бэкапов"
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
                    f"Время: {datetime.now().strftime('%H:%M:%S')}\n"
                    f"💾 Автобэкап создан перед падением",
                    parse_mode="HTML"
                )
        except:
            pass
        
        # Создаем бэкап перед выходом при ошибке
        try:
            db_manager.create_backup_on_exit()
        except:
            pass
        
        sys.exit(1)

def handle_shutdown(signum, frame):
    """Обработчик завершения работы"""
    logger.info(f"🛑 Получен сигнал {signum}. Завершаю работу...")
    
    # Создаем бэкап перед выходом
    try:
        db_manager.create_backup_on_exit()
    except Exception as e:
        logger.error(f"❌ Ошибка создания бэкапа при выходе: {e}")
    
    sys.exit(0)

@backup_on_exit  # Декоратор для автоматического бэкапа
def main():
    """Точка входа - для запуска бота отдельно"""
    # Настройка обработчиков сигналов
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
        # Создаем бэкап при ручной остановке
        try:
            db_manager.create_backup_on_exit()
        except:
            pass
    except Exception as e:
        logger.error(f"❌ Бот аварийно завершил работу: {e}")
        try:
            db_manager.create_backup_on_exit()
        except:
            pass
        sys.exit(1)

async def run_bot_async():
    """
    Асинхронная версия для запуска из render_server.py
    """
    try:
        print("🤖 Запуск бота в асинхронном режиме...")
        
        # Сначала импортируем ВСЕ модели
        from app import models  # Это важно!
        
        from app.config import BOT_TOKEN, ADMIN_IDS, IS_RENDER
        from app.database import create_tables
        
        # 1. Создаем папки
        import os
        os.makedirs('data', exist_ok=True)
        os.makedirs('backups', exist_ok=True)
        
        # 2. Инициализируем менеджер БД
        print("💾 Инициализация менеджера БД...")
        try:
            restored = init_database_manager()
            if restored:
                print("✅ БД восстановлена из последнего бэкапа")
            else:
                print("✅ Восстановление БД не требовалось")
        except Exception as e:
            print(f"⚠️ Ошибка менеджера БД: {e}")
        
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
        from aiogram import Bot, Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        
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
        
        print("✅ Все роутеры зарегистрированы")
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        print(f"✅ Bot: @{bot_info.username}")
        
        # Уведомление админам о запуске
        try:
            try:
                db_info = db_manager.get_db_info()
                backup_count = len(db_manager.list_backups())
            except:
                db_info = {"size_mb": 0}
                backup_count = 0
            
            message = (
                f"🚀 <b>Бот запущен на Render!</b>\n\n"
                f"🤖 @{bot_info.username}\n"
                f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"✅ Авто-пинг включен\n"
                f"💾 БД: {db_info.get('size_mb', 0):.2f} MB\n"
                f"📂 Бэкапов: {backup_count}\n"
                f"📝 /backup - создать бэкап\n"
                f"📋 /backups - список бэкапов"
            )
            
            for admin_id in ADMIN_IDS:
                await bot.send_message(admin_id, message, parse_mode="HTML")
        except Exception as e:
            print(f"❌ Ошибка уведомления: {e}")
        
        # Запуск поллинга
        await bot.delete_webhook(drop_pending_updates=True)
        print("🚀 Бот начал работу (поллинг)...")
        
        # Запускаем поллинг
        await dp.start_polling(bot)
        
    except Exception as e:
        print(f"❌ Критическая ошибка в run_bot_async: {e}")
        
        # Создаем бэкап перед выходом при ошибке
        try:
            db_manager.create_backup_on_exit()
        except:
            pass
        
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
