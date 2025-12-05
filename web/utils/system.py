"""
Утилиты для получения системной информации
"""
import psutil
import humanize
from datetime import datetime
import sys

def get_system_info():
    """Получение системной информации"""
    try:
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Время запуска приложения (приблизительно)
        from render_server import START_TIME
        uptime = datetime.now() - START_TIME
        days = uptime.days
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60
        
        uptime_str = f"{days}д {hours}ч {minutes}м" if days > 0 else f"{hours}ч {minutes}м"
        
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_used': humanize.naturalsize(memory.used),
            'memory_total': humanize.naturalsize(memory.total),
            'uptime': uptime_str,
            'python_version': sys.version.split()[0],
            'platform': sys.platform
        }
        
    except Exception as e:
        return {
            'cpu_percent': 0,
            'memory_percent': 0,
            'memory_used': 'N/A',
            'memory_total': 'N/A',
            'uptime': 'N/A',
            'python_version': sys.version.split()[0],
            'platform': sys.platform
        }
