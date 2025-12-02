#!/usr/bin/env python3
import os
import sys
import logging
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def check_environment():
    """Проверка окружения"""
    print("🔍 Проверка окружения...")

    # Проверяем .env
    if not os.path.exists('.env'):
        print("❌ Файл .env не найден!")
        return False

    load_dotenv()

    # Проверяем токен
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("❌ BOT_TOKEN не найден")
        return False

    if token == "your_actual_bot_token_here":
        print("❌ Замените BOT_TOKEN на реальный токен!")
        return False

    print(f"✅ BOT_TOKEN: {token[:10]}...")
    print(f"✅ ADMIN_IDS: {os.getenv('ADMIN_IDS')}")
    return True


def check_imports():
    """Проверка импортов"""
    print("\n🔍 Проверка импортов...")

    try:
        from app.config import BOT_TOKEN, ADMIN_IDS
        print("✅ config.py - OK")
    except Exception as e:
        print(f"❌ config.py: {e}")
        return False

    try:
        from app.database import create_tables, get_db
        print("✅ database.py - OK")
    except Exception as e:
        print(f"❌ database.py: {e}")
        return False

    try:
        from app.models import User, AnonMessage, Payment
        print("✅ models.py - OK")
    except Exception as e:
        print(f"❌ models.py: {e}")
        return False

    return True


def check_handlers():
    """Проверка хендлеров"""
    print("\n🔍 Проверка хендлеров...")

    try:
        from app.handlers.main_handlers import router as main_router
        print("✅ main_handlers.py - OK")
    except Exception as e:
        print(f"❌ main_handlers.py: {e}")
        return False

    try:
        from app.handlers.anon_handlers import router as anon_router
        print("✅ anon_handlers.py - OK")
    except Exception as e:
        print(f"❌ anon_handlers.py: {e}")
        return False

    try:
        from app.handlers.payment_handlers import router as payment_router
        print("✅ payment_handlers.py - OK")
    except Exception as e:
        print(f"❌ payment_handlers.py: {e}")
        return False

    try:
        from app.handlers.admin_handlers import router as admin_router
        print("✅ admin_handlers.py - OK")
    except Exception as e:
        print(f"❌ admin_handlers.py: {e}")
        return False

    return True


def check_database():
    """Проверка базы данных"""
    print("\n🔍 Проверка базы данных...")

    try:
        from app.database import create_tables
        from app.models import Base

        # Создаем папку data если нет
        os.makedirs('data', exist_ok=True)

        # Пробуем создать таблицы
        create_tables()
        print("✅ База данных - OK")
        return True
    except Exception as e:
        print(f"❌ База данных: {e}")
        return False


def main():
    """Основная диагностика"""
    print("🚀 Запуск диагностики бота...")

    checks = [
        check_environment,
        check_imports,
        check_handlers,
        check_database
    ]

    all_ok = True
    for check in checks:
        if not check():
            all_ok = False

    if all_ok:
        print("\n🎉 Все проверки пройдены! Бот должен работать.")
        print("\n📝 Дальнейшие действия:")
        print("1. Убедитесь что BOT_TOKEN в .env правильный")
        print("2. Запустите: python run_bot.py")
        print("3. Проверьте логи на ошибки")
    else:
        print("\n💥 Обнаружены проблемы! Смотрите выше.")

    return all_ok


if __name__ == "__main__":
    main()