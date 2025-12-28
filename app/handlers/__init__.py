"""
Инициализация обработчиков
"""

from .admin_panel import router as admin_router
from .admin_handlers import router as admin_handlers_router
from .conversations_admin import router as conversations_router

# Экспортируем все роутеры
__all__ = ['admin_router', 'admin_handlers_router', 'conversations_router']
