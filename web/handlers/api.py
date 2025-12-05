"""
API эндпоинты для веб-панели
"""
from aiohttp import web
import json
from datetime import datetime
import os
import shutil
from web.utils.database import get_stats
from web.utils.system import get_system_info

async def api_stats_handler(request):
    """API для получения статистики"""
    try:
        stats = get_stats()
        return web.json_response({
            'total_users': stats['total_users'],
            'total_messages': stats['total_messages'],
            'active_users': stats['active_users'],
            'total_payments': stats['total_payments'],
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def api_system_stats_handler(request):
    """API для получения системной статистики"""
    try:
        system_info = get_system_info()
        return web.json_response({
            'cpu_percent': system_info['cpu_percent'],
            'memory_percent': system_info['memory_percent'],
            'uptime': system_info['uptime'],
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def api_create_backup(request):
    """Создание бекапа базы данных"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"bot_backup_{timestamp}.db"
        source = 'data/bot.db'
        dest = f'backups/{backup_name}'
        
        os.makedirs('backups', exist_ok=True)
        
        if os.path.exists(source):
            shutil.copy2(source, dest)
            
            # Удаляем старые бекапы (оставляем 10 последних)
            backups = sorted([f for f in os.listdir('backups') if f.endswith('.db')])
            if len(backups) > 10:
                for old_backup in backups[:-10]:
                    os.remove(f'backups/{old_backup}')
            
            return web.json_response({
                'success': True,
                'backup_name': backup_name,
                'size': os.path.getsize(dest)
            })
        else:
            return web.json_response({'error': 'Source database not found'}, status=404)
            
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def api_send_backup(request):
    """Отправка бекапа в Telegram (заглушка)"""
    file_name = request.query.get('file', '')
    return web.json_response({
        'success': True,
        'message': f'Backup {file_name} sent to Telegram',
        'timestamp': datetime.now().isoformat()
    })
