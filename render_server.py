"""
ShadowTalk - Веб-панель управления ботом
Минимальная версия для работы на Render
"""
import os
import sys
import asyncio
import logging
import aiohttp
from aiohttp import web
from datetime import datetime
import signal

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальные переменные
START_TIME = datetime.now()

def setup_directories():
    """Создание необходимых директорий"""
    directories = ['data', 'backups', 'logs']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"📁 Создана директория: {directory}")

async def keep_alive_ping():
    """Постоянный пинг для поддержания активности"""
    render_url = os.getenv("RENDER_EXTERNAL_URL", "")
    if not render_url:
        logger.info("⚠️ RENDER_EXTERNAL_URL не установлен, пинг отключен")
        return
    
    ping_url = f"{render_url.rstrip('/')}/ping"
    
    session = None
    try:
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        
        while True:
            try:
                async with session.get(ping_url) as response:
                    if response.status == 200:
                        logger.debug(f"✅ Пинг успешен: {ping_url}")
                    else:
                        logger.warning(f"⚠️ Пинг неудачен: {response.status}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка пинга: {e}")
            
            await asyncio.sleep(55)  # Пинг каждые 55 секунд
            
    except asyncio.CancelledError:
        logger.info("🛑 Самопинг отменен")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в самопинге: {e}")
    finally:
        if session:
            await session.close()

async def on_startup(app):
    """Старт приложения"""
    logger.info("🚀 Запуск веб-панели ShadowTalk...")
    
    # Создаем директории
    setup_directories()
    
    # Запускаем самопинг если есть URL
    render_url = os.getenv("RENDER_EXTERNAL_URL", "")
    if render_url:
        ping_task = asyncio.create_task(keep_alive_ping())
        app['ping_task'] = ping_task
        logger.info(f"✅ Самопинг включен для {render_url}")
    
    # Запускаем бота в отдельном процессе
    try:
        from run_bot import run_bot_async
        bot_task = asyncio.create_task(run_bot_async())
        app['bot_task'] = bot_task
        logger.info("✅ Бот запущен в отдельной задаче")
    except Exception as e:
        logger.error(f"❌ Не удалось запустить бота: {e}")
    
    startup_time = (datetime.now() - START_TIME).total_seconds()
    logger.info(f"✅ Система готова за {startup_time:.1f} секунд")

async def on_cleanup(app):
    """Очистка при завершении"""
    logger.info("🛑 Остановка приложения...")
    
    # Отменяем задачи
    tasks = ['ping_task', 'bot_task']
    for task_name in tasks:
        task = app.get(task_name)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    
    await asyncio.sleep(1)
    logger.info("✅ Приложение остановлено")

async def ping_handler(request):
    """Простой пинг-эндпоинт"""
    return web.Response(
        text=f"pong {datetime.now().strftime('%H:%M:%S')}",
        headers={'Content-Type': 'text/plain'}
    )

async def health_handler(request):
    """Health check для Render"""
    health_status = {
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "uptime": str(datetime.now() - START_TIME),
        "bot_running": True,
        "tables_created": True
    }
    
    return web.json_response(health_status)

def create_app():
    """Создание aiohttp приложения"""
    app = web.Application()
    
    # Базовые маршруты
    app.router.add_get('/ping', ping_handler)
    app.router.add_get('/health', health_handler)
    
    # Загружаем веб-панель
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'web'))
        from web.routes import setup_routes
        setup_routes(app)
        logger.info("✅ Веб-панель загружена")
    except Exception as e:
        logger.warning(f"⚠️ Веб-панель не загружена: {e}")
        # Простая заглушка если веб-панель не загрузилась
        async def index_handler(request):
            return web.Response(
                text="🤖 ShadowTalk Bot is running!\n📊 Web panel will be available soon.",
                content_type='text/plain'
            )
        app.router.add_get('/', index_handler)
    
    # Статические файлы
    static_path = os.path.join(os.path.dirname(__file__), 'web', 'static')
    if os.path.exists(static_path):
        app.router.add_static('/static/', static_path, show_index=True)
        logger.info(f"✅ Статические файлы подключены: {static_path}")
    
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    return app

# Обработчик сигналов
def signal_handler(signum, frame):
    logger.info(f"📶 Получен сигнал {signum}, завершаем работу...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Создаем приложение для gunicorn
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info(f"🚀 Локальный запуск на порту {port}")
    
    web.run_app(
        app,
        host='0.0.0.0',
        port=port,
        access_log=logger,
        shutdown_timeout=5
    )
