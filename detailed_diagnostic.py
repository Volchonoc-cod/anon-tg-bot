#!/usr/bin/env python3
import asyncio
import logging
import socket
import aiohttp
import time
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def detailed_diagnostic():
    print("🔍 Детальная диагностика подключения...")

    BOT_TOKEN = os.getenv("BOT_TOKEN")

    # Тест 1: Базовый DNS
    try:
        ip = socket.gethostbyname('api.telegram.org')
        print(f"✅ DNS: api.telegram.org -> {ip}")
    except Exception as e:
        print(f"❌ DNS Error: {e}")
        return False

    # Тест 2: HTTP подключение
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            start = time.time()
            async with session.get('https://api.telegram.org') as response:
                end = time.time()
                print(f"✅ HTTP: Status {response.status}, Time: {end - start:.2f}s")
    except Exception as e:
        print(f"❌ HTTP Error: {e}")
        return False

    # Тест 3: Проверка токена
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден в .env")
        return False

    if BOT_TOKEN == "your_actual_bot_token_here":
        print("❌ BOT_TOKEN не заменен на реальный токен!")
        return False

    print(f"✅ BOT_TOKEN: {BOT_TOKEN[:10]}... (длина: {len(BOT_TOKEN)})")

    # Тест 4: Подключение через aiogram
    from aiogram import Bot

    print("🔄 Тестируем подключение через aiogram...")

    # Пробуем разные таймауты
    for timeout_sec in [30, 60, 90]:
        try:
            print(f"  ⏱️  Пробуем timeout={timeout_sec}...")
            bot = Bot(token=BOT_TOKEN, timeout=timeout_sec)
            start = time.time()
            bot_info = await bot.get_me()
            end = time.time()
            print(f"  ✅ Успех! Бот: @{bot_info.username}, время: {end - start:.2f}s")
            await bot.session.close()
            return True
        except Exception as e:
            print(f"  ❌ Timeout {timeout_sec}: {e}")
            continue

    return False


async def test_local_network():
    """Тест локальной сети"""
    print("\n🌐 Тестируем локальную сеть...")

    # Проверяем доступ к другим сайтам для сравнения
    test_sites = [
        'google.com',
        'github.com',
        'yandex.ru'
    ]

    for site in test_sites:
        try:
            ip = socket.gethostbyname(site)
            print(f"✅ {site} -> {ip}")
        except Exception as e:
            print(f"❌ {site}: {e}")


if __name__ == "__main__":
    print("🚀 Запуск детальной диагностики...")

    # Тест локальной сети
    asyncio.run(test_local_network())

    # Основная диагностика
    success = asyncio.run(detailed_diagnostic())

    if success:
        print("\n🎉 Все тесты пройдены! Проблема в конфигурации бота.")
    else:
        print("\n💥 Обнаружены проблемы!")
        print("\n🔧 Возможные решения:")
        print("1. Проверьте .env файл - токен должен быть реальным")
        print("2. Попробуйте перезагрузить телефон/модем")
        print("3. Отключите и включите мобильные данные")
        print("4. Проверьте настройки APN вашего оператора")
        print("5. Попробуйте в другом месте (разная зона покрытия)")