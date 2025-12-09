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
        api_restore_backup,
        api_cleanup_backups,
        api_dbinfo,
        api_download_backup,
        api_get_backup_info,
        api_get_db_detailed_info,
        api_send_to_admins,
        api_send_current_db_to_admins,
        api_upload_db,
        api_send_backup,
        api_restart_bot,      # НОВЫЙ
        api_bot_status        # НОВЫЙ
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
    
    # Новые API endpoints для менеджера БД
    app.router.add_get('/api/restore_backup', api_restore_backup)
    app.router.add_get('/api/cleanup_backups', api_cleanup_backups)
    app.router.add_get('/api/dbinfo', api_dbinfo)
    app.router.add_get('/api/download_backup', api_download_backup)
    app.router.add_get('/api/get_backup_info', api_get_backup_info)
    app.router.add_get('/api/get_db_detailed_info', api_get_db_detailed_info)
    app.router.add_get('/api/send_to_admins', api_send_to_admins)
    app.router.add_get('/api/send_current_db_to_admins', api_send_current_db_to_admins)
    app.router.add_post('/api/upload_db', api_upload_db)
    
    # API для управления ботом
    app.router.add_get('/api/restart_bot', api_restart_bot)
    app.router.add_get('/api/bot_status', api_bot_status)
    
    # Legacy endpoints для совместимости
    app.router.add_get('/create_backup', api_create_backup)
    app.router.add_get('/send_backup', api_send_backup)
    
    logger.info("✅ Все маршруты зарегистрированы")
