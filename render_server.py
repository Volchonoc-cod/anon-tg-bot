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
import signal
import subprocess

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальные переменные
START_TIME = datetime.now()
BOT_PROCESS = None

def setup_directories():
    """Создание необходимых директорий"""
    directories = ['data', 'backups', 'logs']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"📁 Создана директория: {directory}")

def start_bot_process():
    """Запускает Telegram бота в отдельном процессе"""
    global BOT_PROCESS
    try:
        logger.info("🤖 Запуск Telegram бота в отдельном процессе...")
        
        # Определяем путь к скрипту бота
        bot_script = os.path.join(os.path.dirname(__file__), 'run_bot.py')
        
        # Запускаем бота в отдельном процессе
        BOT_PROCESS = subprocess.Popen(
            [sys.executable, bot_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        logger.info(f"✅ Бот запущен в процессе PID: {BOT_PROCESS.pid}")
        
        # Читаем вывод бота в фоне
        asyncio.create_task(read_bot_output())
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
        import traceback
        traceback.print_exc()
        return False

async def read_bot_output():
    """Чтение вывода бота"""
    if not BOT_PROCESS:
        return
    
    try:
        while BOT_PROCESS.poll() is None:
            line = await asyncio.get_event_loop().run_in_executor(
                None, BOT_PROCESS.stdout.readline
            )
            if line:
                logger.info(f"🤖 Бот: {line.strip()}")
            
            await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"❌ Ошибка чтения вывода бота: {e}")

async def keep_alive_ping():
    """Постоянный пинг для поддержания активности"""
    render_url = os.getenv("RENDER_EXTERNAL_URL", "")
    if not render_url:
        logger.info("⚠️ RENDER_EXTERNAL_URL не установлен, пинг отключен")
        return
    
    base_url = render_url.rstrip('/')
    ping_url = f"{base_url}/ping"
    
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
    
    # Даем время для запуска веб-сервера
    await asyncio.sleep(2)
    
    # Запускаем бота в отдельном процессе
    if start_bot_process():
        app['bot_process'] = BOT_PROCESS
    
    startup_time = (datetime.now() - START_TIME).total_seconds()
    logger.info(f"✅ Система готова за {startup_time:.1f} секунд")

async def on_cleanup(app):
    """Очистка при завершении"""
    logger.info("🛑 Остановка приложения...")
    
    global BOT_PROCESS
    
    # Останавливаем бота
    if BOT_PROCESS:
        logger.info(f"🛑 Остановка процесса бота PID: {BOT_PROCESS.pid}")
        BOT_PROCESS.terminate()
        try:
            BOT_PROCESS.wait(timeout=5)
        except subprocess.TimeoutExpired:
            BOT_PROCESS.kill()
        BOT_PROCESS = None
    
    # Отменяем задачи
    tasks = ['ping_task']
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
    global BOT_PROCESS
    
    health_status = {
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "uptime": str(datetime.now() - START_TIME),
        "bot_running": BOT_PROCESS is not None and BOT_PROCESS.poll() is None,
        "bot_pid": BOT_PROCESS.pid if BOT_PROCESS else None
    }
    
    return web.json_response(health_status)

async def index_handler(request):
    """Главная страница"""
    try:
        with open(os.path.join(os.path.dirname(__file__), 'web', 'templates', 'index.html'), 'r') as f:
            content = f.read()
        
        # Добавляем информацию о статусе
        status_info = ""
        if BOT_PROCESS and BOT_PROCESS.poll() is None:
            status_info = "<div class='alert alert-success'>🤖 Бот запущен</div>"
        else:
            status_info = "<div class='alert alert-warning'>⚠️ Бот не запущен</div>"
        
        content = content.replace('<!-- STATUS_PLACEHOLDER -->', status_info)
        
        return web.Response(text=content, content_type='text/html')
    except Exception as e:
        return web.Response(text=f"Ошибка загрузки страницы: {str(e)}", status=500)

async def api_stats_handler(request):
    """API для получения статистики"""
    stats = {
        "status": "online",
        "uptime": str(datetime.now() - START_TIME),
        "bot_status": "running" if BOT_PROCESS and BOT_PROCESS.poll() is None else "stopped",
        "timestamp": datetime.now().isoformat()
    }
    return web.json_response(stats)

def create_app():
    """Создание aiohttp приложения"""
    app = web.Application(client_max_size=10*1024*1024)  # 10MB max
    
    # Базовые маршруты
    app.router.add_get('/ping', ping_handler)
    app.router.add_get('/health', health_handler)
    app.router.add_get('/', index_handler)
    app.router.add_get('/api/stats', api_stats_handler)
    
    try:
        # Загружаем маршруты из модулей
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'web'))
        from web.routes import setup_routes
        setup_routes(app)
        
        # Статические файлы
        static_path = os.path.join(os.path.dirname(__file__), 'web', 'static')
        if os.path.exists(static_path):
            app.router.add_static('/static/', static_path, show_index=True)
            logger.info(f"✅ Статические файлы подключены: {static_path}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки маршрутов: {e}")
        # Продолжаем с базовыми маршрутами
    
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    return app

# Обработчик сигналов
def signal_handler(signum, frame):
    logger.info(f"📶 Получен сигнал {signum}, завершаем работу...")
    if BOT_PROCESS:
        BOT_PROCESS.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Создаем приложение для gunicorn
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info(f"🚀 Локальный запуск на порту {port}")
    
    # Настройка для разработки
    web.run_app(
        app,
        host='0.0.0.0',
        port=port,
        access_log=logger,
        shutdown_timeout=5
    )
