"""
Регистрация всех маршрутов веб-панели
"""
from aiohttp import web
import logging

logger = logging.getLogger(__name__)

def setup_routes(app: web.Application):
    """Настройка всех маршрутов"""
    
    # Импортируем обработчики
    from web.handlers.main import index_handler
    from web.handlers.backups import backups_handler
    from web.handlers.monitor import monitor_handler
    from web.handlers.users import users_handler
    from web.handlers.settings import settings_handler
    from web.handlers.logs import logs_handler
    
    # API маршруты
    from web.handlers.api import (
        api_stats_handler,
        api_system_stats_handler,
        api_create_backup,
        api_send_backup
    )
    
    logger.info("📋 Регистрация маршрутов веб-панели...")
    
    # Основные страницы
    app.router.add_get('/', index_handler)
    app.router.add_get('/dashboard', index_handler)
    app.router.add_get('/backups', backups_handler)
    app.router.add_get('/monitor', monitor_handler)
    app.router.add_get('/users', users_handler)
    app.router.add_get('/settings', settings_handler)
    app.router.add_get('/logs', logs_handler)
    
    # API endpoints
    app.router.add_get('/api/stats', api_stats_handler)
    app.router.add_get('/api/system_stats', api_system_stats_handler)
    app.router.add_get('/api/create_backup', api_create_backup)
    app.router.add_get('/api/send_backup', api_send_backup)
    
    # Legacy endpoints для совместимости
    app.router.add_get('/download_backup', backups_handler)
    app.router.add_get('/send_backup_to_telegram', backups_handler)
    app.router.add_get('/create_backup', backups_handler)
    
    logger.info("✅ Все маршруты зарегистрированы")
