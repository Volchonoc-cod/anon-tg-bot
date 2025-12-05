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


# Импортируем менеджер БД
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from app.database_manager import db_manager
from web.utils.database import get_stats
from web.utils.system import get_system_info

async def api_create_backup(request):
    """API для создания бэкапа"""
    try:
        backup_path = db_manager.create_backup()
        
        if backup_path:
            backup_name = os.path.basename(backup_path)
            size = os.path.getsize(backup_path)
            
            return web.json_response({
                'success': True,
                'backup_name': backup_name,
                'size': size,
                'size_mb': size / (1024 * 1024),
                'timestamp': datetime.now().isoformat(),
                'backup_count': len(db_manager.list_backups())
            })
        else:
            return web.json_response({
                'success': False,
                'error': 'Не удалось создать бэкап'
            }, status=500)
            
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)

async def api_restore_backup(request):
    """API для восстановления из бэкапа"""
    try:
        file_name = request.query.get('file', '')
        if not file_name:
            return web.json_response({
                'success': False,
                'error': 'Не указано имя файла'
            }, status=400)
        
        backup_path = os.path.join('backups', file_name)
        
        if not os.path.exists(backup_path):
            return web.json_response({
                'success': False,
                'error': 'Файл бэкапа не найден'
            }, status=404)
        
        # Восстанавливаем
        success = db_manager.restore_from_backup(backup_path)
        
        if success:
            return web.json_response({
                'success': True,
                'message': f'БД восстановлена из {file_name}',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return web.json_response({
                'success': False,
                'error': 'Ошибка восстановления'
            }, status=500)
            
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)

async def api_cleanup_backups(request):
    """API для очистки старых бэкапов"""
    try:
        deleted_count = db_manager.cleanup_old_backups()
        
        return web.json_response({
            'success': True,
            'deleted': deleted_count,
            'backup_count': len(db_manager.list_backups()),
            'timestamp': datetime.now().isoformat()
        })
            
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)

async def api_dbinfo(request):
    """API для получения информации о БД"""
    try:
        db_info = db_manager.get_db_info()
        backups = db_manager.list_backups()
        metadata = db_manager.load_metadata()
        
        return web.json_response({
            'success': True,
            'db_info': db_info,
            'backup_count': len(backups),
            'metadata': metadata,
            'timestamp': datetime.now().isoformat()
        })
            
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)


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



async def api_send_backup(request):
    """Отправка бекапа в Telegram (заглушка)"""
    file_name = request.query.get('file', '')
    return web.json_response({
        'success': True,
        'message': f'Backup {file_name} sent to Telegram',
        'timestamp': datetime.now().isoformat()
    })
