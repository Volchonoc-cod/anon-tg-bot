"""
Веб-сервер для Render, который держит бота живым
"""
import os
import sys
import asyncio
import logging
import aiohttp
from aiohttp import web
from datetime import datetime
import threading
import time

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальные переменные
bot_task = None
keep_alive_task = None
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "")

# ============================================
# 1. ФУНКЦИЯ САМОПИНГА (держит Render активным)
# ============================================
async def keep_alive_ping():
    """Постоянный пинг самого себя каждые 20 секунд"""
    # Определяем URL для пинга
    if RENDER_URL:
        base_url = RENDER_URL
    else:
        port = os.getenv("PORT", "8080")
        base_url = f"http://localhost:{port}"
    
    ping_url = f"{base_url}/ping"
    logger.info(f"🚀 Запуск самопинга на {ping_url}")
    
    ping_count = 0
    
    while True:
        try:
            # Используем aiohttp для асинхронного запроса
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(ping_url, timeout=10) as response:
                        if response.status == 200:
                            ping_count += 1
                            if ping_count % 10 == 0:  # Логируем каждые 10 пингов
                                logger.info(f"✅ Самопинг #{ping_count} успешен")
                        else:
                            logger.warning(f"⚠️ Самопинг #{ping_count} вернул {response.status}")
                except asyncio.TimeoutError:
                    logger.warning(f"⏰ Таймаут самопинга #{ping_count}")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка самопинга #{ping_count}: {e}")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка самопинга: {e}")
        
        # Ждем 20 секунд до следующего пинга
        await asyncio.sleep(20)

# ============================================
# 2. ФУНКЦИЯ ПИНГА АДМИНУ (каждые 13 минут)
# ============================================
async def admin_ping():
    """Пинг админу каждые 13 минут о статусе бота"""
    if not BOT_TOKEN or not ADMIN_IDS:
        logger.warning("⚠️ BOT_TOKEN или ADMIN_IDS не установлены, пропускаю админ-пинг")
        return
    
    start_time = datetime.now()
    
    while True:
        try:
            # Ждем 13 минут
            await asyncio.sleep(13 * 60)
            
            # Рассчитываем аптайм
            uptime = datetime.now() - start_time
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            
            # Формируем сообщение
            message = (
                f"🔄 <b>Авто-пинг бота</b>\n\n"
                f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n"
                f"⏱ Аптайм: {hours}ч {minutes}м\n"
                f"🌐 Статус: <code>Активен на Render</code>\n\n"
                f"✅ Бот работает 24/7"
            )
            
            # Отправляем всем админам
            async with aiohttp.ClientSession() as session:
                for admin_id in ADMIN_IDS:
                    if not admin_id.strip():
                        continue
                    
                    try:
                        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                        payload = {
                            "chat_id": int(admin_id.strip()),
                            "text": message,
                            "parse_mode": "HTML"
                        }
                        
                        async with session.post(url, json=payload, timeout=10) as resp:
                            if resp.status == 200:
                                logger.info(f"✅ Пинг отправлен админу {admin_id}")
                            else:
                                text = await resp.text()
                                logger.error(f"❌ Ошибка пинга админу {admin_id}: {text}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки админу {admin_id}: {e}")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка в админ-пинге: {e}")
            await asyncio.sleep(60)  # Ждем минуту при ошибке

# ============================================
# 3. ФУНКЦИЯ ЗАПУСКА ТВОЕГО БОТА
# ============================================
async def start_your_bot():
    """Запускает твоего оригинального бота"""
    try:
        logger.info("🤖 Запуск Telegram бота...")
        
        # Импортируем твой оригинальный run_bot
        import run_bot
        
        # Запускаем твоего бота
        await run_bot.run_bot_async()
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
        # Пытаемся перезапустить через 30 секунд
        await asyncio.sleep(30)
        asyncio.create_task(start_your_bot())

# ============================================
# 4. HTTP ХЕНДЛЕРЫ (для Render)
# ============================================
async def health_handler(request):
    """Health check для Render"""
    return web.Response(text="OK")

async def ping_handler(request):
    """Простой пинг-эндпоинт"""
    return web.Response(text=f"pong {datetime.now().strftime('%H:%M:%S')}")

async def status_handler(request):
    """Статус сервера"""
    status = {
        "status": "running",
        "time": datetime.now().isoformat(),
        "service": "anon-tg-bot",
        "environment": "render" if os.getenv("RENDER") else "local"
    }
    return web.json_response(status)

# ============================================
# 5. СОЗДАНИЕ И ЗАПУСК ПРИЛОЖЕНИЯ
# ============================================
async def on_startup(app):
    """Запуск при старте приложения"""
    logger.info("🚀 Запуск приложения...")
    
    # Запускаем самопинг (удерживает Render активным)
    global keep_alive_task
    keep_alive_task = asyncio.create_task(keep_alive_ping())
    
    # Запускаем пинг админу
    asyncio.create_task(admin_ping())
    
    # Запускаем твоего бота в фоне
    global bot_task
    bot_task = asyncio.create_task(start_your_bot())
    
    logger.info("✅ Все задачи запущены")

async def on_cleanup(app):
    """Очистка при завершении"""
    logger.info("🛑 Остановка приложения...")
    
    if keep_alive_task:
        keep_alive_task.cancel()
    if bot_task:
        bot_task.cancel()

def create_app():
    """Создание aiohttp приложения"""
    app = web.Application()
    
    # Регистрируем роуты
    app.router.add_get('/', health_handler)
    app.router.add_get('/health', health_handler)
    app.router.add_get('/ping', ping_handler)
    app.router.add_get('/status', status_handler)
    
    # Регистрируем события
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    return app

# Создаем приложение
app = create_app()

# Запуск напрямую (для тестов)
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    web.run_app(app, host='0.0.0.0', port=port)
