"""
ShadowTalk - Веб-панель управления ботом
Модульная архитектура для быстрого запуска
"""
import os
import sys
import asyncio
import logging
import aiohttp
from aiohttp import web
from datetime import datetime

# Добавляем папку web в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'web'))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальные переменные
START_TIME = datetime.now()

async def start_bot_background():
    """Запускает Telegram бота в фоновом режиме"""
    try:
        logger.info("🤖 Фоновый запуск Telegram бота...")
        
        from run_bot import run_bot_async as run_bot_optimized
        await run_bot_optimized()
        
    except Exception as e:
        logger.error(f"❌ Бот упал: {e}")
        import traceback
        traceback.print_exc()
        return

async def keep_alive_ping():
    """Постоянный пинг для поддержания активности"""
    render_url = os.getenv("RENDER_EXTERNAL_URL", "")
    if not render_url:
        return
    
    base_url = render_url.rstrip('/')
    ping_url = f"{base_url}/ping"
    
    session = None
    try:
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5))
        
        while True:
            try:
                async with session.get(ping_url) as response:
                    if response.status == 200:
                        pass  # Успешный пинг
            except:
                pass  # Игнорируем ошибки
            
            await asyncio.sleep(25)
            
    except asyncio.CancelledError:
        pass
    finally:
        if session:
            await session.close()

async def on_startup_fast(app):
    """Быстрый старт приложения"""
    logger.info("🚀 Быстрый старт веб-панели...")
    
    # Запускаем бота в фоне
    bot_task = asyncio.create_task(start_bot_background())
    app['bot_task'] = bot_task
    logger.info("✅ Бот запущен в фоновом режиме")
    
    # Ждем 1 секунду
    await asyncio.sleep(1)
    
    # Запускаем самопинг если есть URL
    render_url = os.getenv("RENDER_EXTERNAL_URL", "")
    if render_url:
        ping_task = asyncio.create_task(keep_alive_ping())
        app['ping_task'] = ping_task
    
    logger.info(f"✅ Система готова за {(datetime.now() - START_TIME).total_seconds():.1f} секунд")

async def on_cleanup(app):
    """Очистка при завершении"""
    logger.info("🛑 Остановка приложения...")
    
    # Отменяем задачи
    tasks = ['bot_task', 'ping_task']
    for task_name in tasks:
        task = app.get(task_name)
        if task:
            task.cancel()

async def ping_handler(request):
    """Простой пинг-эндпоинт"""
    return web.Response(text=f"pong {datetime.now().strftime('%H:%M:%S')}")

async def health_handler(request):
    """Health check для Render"""
    return web.Response(text="OK")

def create_app():
    """Создание aiohttp приложения с модульной структурой"""
    app = web.Application()
    
    # Базовые маршруты
    app.router.add_get('/ping', ping_handler)
    app.router.add_get('/health', health_handler)
    
    # Загружаем маршруты из модулей
    from web.routes import setup_routes
    setup_routes(app)
    
    # Статические файлы
    static_path = os.path.join(os.path.dirname(__file__), 'web', 'static')
    if os.path.exists(static_path):
        app.router.add_static('/static/', static_path)
    
    app.on_startup.append(on_startup_fast)
    app.on_cleanup.append(on_cleanup)
    
    return app

# Создаем приложение для gunicorn
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info(f"🚀 Локальный запуск на порту {port}")
    web.run_app(app, host='0.0.0.0', port=port)
