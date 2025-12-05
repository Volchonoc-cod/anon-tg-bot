"""
Утилиты для веб-панели
"""

from .templates import (
    get_base_html,
    get_header,
    get_footer,
    get_common_css
)
from .database import get_stats
from .system import get_system_info

__all__ = [
    'get_base_html',
    'get_header',
    'get_footer',
    'get_common_css',
    'get_stats',
    'get_system_info'
]
