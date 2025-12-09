"""
ShadowTalk - Веб-панель управления ботом с поддержкой вебхуков
Оптимизировано для Render.com
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
WEBHOOK_URL = None
WEBHOOK_PATH = "/webhook"
APP = None

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

async def initialize_bot_for_webhooks():
    """Инициализирует бота для работы с вебхуками (без поллинга)"""
    try:
        logger.info("🤖 Инициализация бота для вебхуков...")
        
        # Добавляем путь к приложению
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, current_dir)
        
        # Инициализируем конфигурацию
        from app.config import BOT_TOKEN, ADMIN_IDS, IS_RENDER
        logger.info(f"✅ Конфигурация загружена: Bot Token = {BOT_TOKEN[:10]}...")
        
        # Создаем таблицы БД
        logger.info("🔄 Создание таблиц БД...")
        if create_database_tables():
            logger.info("✅ Таблицы БД созданы успешно")
        else:
            logger.error("❌ Не удалось создать таблицы БД, продолжаем работу...")
        
        # Настраиваем вебхук
        global WEBHOOK_URL
        WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", "")
        
        if not WEBHOOK_URL:
            logger.warning("⚠️ RENDER_EXTERNAL_URL не установлен, вебхуки отключены")
            return None
        
        # Инициализируем менеджер БД
        logger.info("💾 Инициализация менеджера БД...")
        try:
            from app.database_manager import init_database_manager
            restored = init_database_manager()
            if restored:
                logger.info("✅ БД восстановлена из последнего бэкапа")
            else:
                logger.info("✅ Восстановление БД не требовалось")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации менеджера БД: {e}")
        
        # Создаем бота и диспетчер
        from aiogram import Bot, Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher(storage=MemoryStorage())
        
        # Регистрируем роутеры
        logger.info("📋 Регистрация роутеров...")
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
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"✅ Bot: @{bot_info.username} ({bot_info.first_name})")
        
        # Устанавливаем вебхук
        webhook_url = f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"
        await bot.set_webhook(webhook_url)
        logger.info(f"✅ Вебхук установлен: {webhook_url}")
        
        # Отправляем уведомление админам
        try:
            from app.database_manager import db_manager
            db_info = db_manager.get_db_info()
            backup_count = len(db_manager.list_backups())
        except:
            db_info = {"size_mb": 0}
            backup_count = 0
        
        try:
            message = (
                f"🚀 <b>Бот запущен на Render через вебхуки!</b>\n\n"
                f"🤖 @{bot_info.username}\n"
                f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"🌐 Вебхук: {webhook_url}\n"
                f"👥 Админов: {len(ADMIN_IDS)}\n"
                f"💾 БД: {db_info.get('size_mb', 0):.2f} MB\n"
                f"📂 Бэкапов: {backup_count}\n"
                f"📝 /backup - создать бэкап"
            )
            
            for admin_id in ADMIN_IDS:
                await bot.send_message(admin_id, message, parse_mode="HTML")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления: {e}")
        
        return bot, dp
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации бота: {e}")
        import traceback
        traceback.print_exc()
        return None, None

async def keep_alive_ping():
    """Постоянный пинг для поддержания активности"""
    global WEBHOOK_URL
    
    if not WEBHOOK_URL:
        logger.info("⚠️ WEBHOOK_URL не установлен, пинг отключен")
        return
    
    ping_url = f"{WEBHOOK_URL.rstrip('/')}/ping"
    
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
    
    # Инициализируем бота для вебхуков
    bot, dp = await initialize_bot_for_webhooks()
    if bot and dp:
        app['bot'] = bot
        app['dp'] = dp
        logger.info("✅ Бот инициализирован для вебхуков")
    else:
        logger.error("❌ Не удалось инициализировать бота")
    
    # Запускаем самопинг если есть URL
    if WEBHOOK_URL:
        ping_task = asyncio.create_task(keep_alive_ping())
        app['ping_task'] = ping_task
        logger.info(f"✅ Самопинг включен для {WEBHOOK_URL}")
    
    startup_time = (datetime.now() - START_TIME).total_seconds()
    logger.info(f"✅ Система готова за {startup_time:.1f} секунд")

async def on_cleanup(app):
    """Очистка при завершении"""
    logger.info("🛑 Остановка приложения...")
    
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
    
    # Удаляем вебхук
    bot = app.get('bot')
    if bot:
        try:
            await bot.delete_webhook()
            logger.info("✅ Вебхук удален")
        except Exception as e:
            logger.error(f"❌ Ошибка удаления вебхука: {e}")
    
    await asyncio.sleep(1)
    logger.info("✅ Приложение остановлено")

async def webhook_handler(request):
    """Обработчик вебхуков от Telegram"""
    try:
        dp = request.app.get('dp')
        bot = request.app.get('bot')
        
        if not dp or not bot:
            return web.Response(status=500, text="Bot not initialized")
        
        # Получаем обновление от Telegram
        data = await request.json()
        
        # Обрабатываем обновление через aiogram
        update = await dp.feed_update(bot, data)
        
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"❌ Ошибка обработки вебхука: {e}")
        return web.Response(status=500, text=str(e))

async def ping_handler(request):
    """Простой пинг-эндпоинт"""
    return web.Response(
        text=f"pong {datetime.now().strftime('%H:%M:%S')}",
        headers={'Content-Type': 'text/plain'}
    )

async def health_handler(request):
    """Health check для Render"""
    bot = request.app.get('bot')
    health_status = {
        "status": "OK" if bot else "ERROR",
        "timestamp": datetime.now().isoformat(),
        "uptime": str(datetime.now() - START_TIME),
        "bot_running": bool(bot),
        "webhook_url": f"{WEBHOOK_URL}{WEBHOOK_PATH}" if WEBHOOK_URL else None
    }
    
    return web.json_response(health_status)

async def index_handler(request):
    """Главная страница"""
    try:
        # Создаем простую HTML страницу для дашборда
        bot = request.app.get('bot')
        
        html = f"""
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>ShadowTalk Bot Dashboard</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    margin: 0;
                    padding: 20px;
                    min-height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }}
                .container {{
                    background: rgba(255, 255, 255, 0.9);
                    backdrop-filter: blur(10px);
                    border-radius: 20px;
                    padding: 40px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    max-width: 800px;
                    width: 100%;
                }}
                h1 {{
                    color: #333;
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .status {{
                    background: {'#4CAF50' if bot else '#f44336'};
                    color: white;
                    padding: 15px;
                    border-radius: 10px;
                    text-align: center;
                    font-size: 18px;
                    margin-bottom: 30px;
                }}
                .stats {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .stat-card {{
                    background: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                .stat-card h3 {{
                    margin: 0;
                    color: #666;
                    font-size: 14px;
                }}
                .stat-card .value {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #333;
                    margin: 10px 0;
                }}
                .links {{
                    text-align: center;
                    margin-top: 30px;
                }}
                .links a {{
                    display: inline-block;
                    margin: 0 10px;
                    padding: 12px 30px;
                    background: #667eea;
                    color: white;
                    text-decoration: none;
                    border-radius: 25px;
                    transition: transform 0.3s, box-shadow 0.3s;
                }}
                .links a:hover {{
                    transform: translateY(-3px);
                    box-shadow: 0 10px 20px rgba(0,0,0,0.2);
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 ShadowTalk Bot Dashboard</h1>
                
                <div class="status">
                    {'✅ Бот запущен и работает через вебхуки' if bot else '❌ Бот не запущен'}
                </div>
                
                <div class="stats">
                    <div class="stat-card">
                        <h3>Аптайм</h3>
                        <div class="value" id="uptime">{str(datetime.now() - START_TIME).split('.')[0]}</div>
                    </div>
                    <div class="stat-card">
                        <h3>Вебхук</h3>
                        <div class="value">{'✅ Включен' if WEBHOOK_URL else '❌ Отключен'}</div>
                    </div>
                    <div class="stat-card">
                        <h3>Статус</h3>
                        <div class="value">{'🟢 Online' if bot else '🔴 Offline'}</div>
                    </div>
                </div>
                
                <div class="links">
                    <a href="/ping" target="_blank">Ping Test</a>
                    <a href="/health" target="_blank">Health Check</a>
                    {'<a href="/webhook" target="_blank">Webhook</a>' if WEBHOOK_URL else ''}
                </div>
            </div>
            
            <script>
                // Обновляем аптайм каждую секунду
                function updateUptime() {{
                    const startTime = new Date("{START_TIME.isoformat()}");
                    const now = new Date();
                    const diff = new Date(now - startTime);
                    
                    const hours = diff.getUTCHours().toString().padStart(2, '0');
                    const minutes = diff.getUTCMinutes().toString().padStart(2, '0');
                    const seconds = diff.getUTCSeconds().toString().padStart(2, '0');
                    
                    document.getElementById('uptime').textContent = `${hours}:${minutes}:${seconds}`;
                }}
                
                updateUptime();
                setInterval(updateUptime, 1000);
            </script>
        </body>
        </html>
        """
        
        return web.Response(text=html, content_type='text/html')
    except Exception as e:
        return web.Response(text=f"Ошибка загрузки страницы: {str(e)}", status=500)

async def api_stats_handler(request):
    """API для получения статистики"""
    bot = request.app.get('bot')
    stats = {
        "status": "online" if bot else "offline",
        "uptime": str(datetime.now() - START_TIME),
        "bot_status": "running" if bot else "stopped",
        "webhook": "enabled" if WEBHOOK_URL else "disabled",
        "timestamp": datetime.now().isoformat()
    }
    return web.json_response(stats)

def create_app():
    """Создание aiohttp приложения"""
    app = web.Application(client_max_size=10*1024*1024)  # 10MB max
    
    # Базовые маршруты
    app.router.add_post(WEBHOOK_PATH, webhook_handler)  # ОБРАБОТЧИК ВЕБХУКОВ
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
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Создаем приложение для gunicorn
app = create_app()

# Сохраняем глобальную ссылку
APP = app

if __name__ == "__main__":
    # Это для локального запуска (только для отладки)
    port = int(os.getenv("PORT", 8080))
    logger.warning("⚠️ ЛОКАЛЬНЫЙ ЗАПУСК - вебхуки не будут работать корректно!")
    logger.info(f"🚀 Локальный запуск на порту {port}")
    
    # Настройка для разработки
    web.run_app(
        app,
        host='0.0.0.0',
        port=port,
        access_log=logger,
        shutdown_timeout=5
    )
