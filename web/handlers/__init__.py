
"""
Инициализация пакета обработчиков
"""
from .main import index_handler
from .backups import backups_handler
from .monitor import monitor_handler
from .users import users_handler
from .settings import settings_handler
from .logs import logs_handler
from .api import (
    api_stats_handler,
    api_system_stats_handler,
    api_create_backup,
    api_send_backup
)

__all__ = [
    'index_handler',
    'backups_handler', 
    'monitor_handler',
    'users_handler',
    'settings_handler',
    'logs_handler',
    'api_stats_handler',
    'api_system_stats_handler',
    'api_create_backup',
    'api_send_backup'
]
