"""
API эндпоинты для веб-панели
"""
from aiohttp import web
import json
import os
import shutil
import sqlite3
from datetime import datetime
import asyncio
from web.utils.database import get_stats
from web.utils.system import get_system_info

# Импортируем менеджер БД
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from app.database_manager import db_manager
from app.config import ADMIN_IDS, BOT_TOKEN

async def send_backup_to_telegram(file_path, caption):
    """Отправить файл в Telegram админам"""
    try:
        # Динамический импорт aiogram чтобы избежать циклических импортов
        from aiogram import Bot
        from aiogram.types import FSInputFile
        
        if not BOT_TOKEN:
            print("⚠️ BOT_TOKEN не настроен")
            return {"sent": 0, "total": len(ADMIN_IDS), "error": "BOT_TOKEN не настроен"}
        
        if not ADMIN_IDS:
            print("⚠️ ADMIN_IDS не настроены")
            return {"sent": 0, "total": 0, "error": "ADMIN_IDS не настроены"}
        
        bot = Bot(token=BOT_TOKEN)
        sent_count = 0
        
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_document(
                    chat_id=admin_id,
                    document=FSInputFile(file_path),
                    caption=f"{caption}\n📊 Размер: {file_size_mb:.2f} MB\n⏰ {datetime.now().strftime('%H:%M:%S')}"
                )
                sent_count += 1
                print(f"✅ Отправлено админу {admin_id}")
            except Exception as e:
                print(f"❌ Ошибка отправки админу {admin_id}: {e}")
        
        await bot.session.close()
        return {"sent": sent_count, "total": len(ADMIN_IDS)}
        
    except Exception as e:
        print(f"❌ Ошибка в send_backup_to_telegram: {e}")
        return {"sent": 0, "total": len(ADMIN_IDS), "error": str(e)}

async def api_stats_handler(request):
    """API для получения статистики"""
    try:
        stats = get_stats()
        return web.json_response({
            'success': True,
            'total_users': stats['total_users'],
            'total_messages': stats['total_messages'],
            'active_users': stats['active_users'],
            'total_payments': stats['total_payments'],
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)

async def api_system_stats_handler(request):
    """API для получения системной статистики"""
    try:
        system_info = get_system_info()
        return web.json_response({
            'success': True,
            'cpu_percent': system_info['cpu_percent'],
            'memory_percent': system_info['memory_percent'],
            'uptime': system_info['uptime'],
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)

async def api_create_backup(request):
    """API для создания бэкапа - возвращаем JSON а не редирект"""
    try:
        backup_path = db_manager.create_backup()
        
        if backup_path:
            backup_name = os.path.basename(backup_path)
            size = os.path.getsize(backup_path)
            
            # Отправляем админам через Telegram
            send_result = await send_backup_to_telegram(
                backup_path, 
                f"💾 Новый бекап базы данных\n📁 {backup_name}"
            )
            
            response_data = {
                'success': True,
                'backup_name': backup_name,
                'size': size,
                'size_mb': round(size / (1024 * 1024), 2),
                'timestamp': datetime.now().isoformat(),
                'backup_count': len(db_manager.list_backups()),
                'telegram_sent': send_result['sent'],
                'telegram_total': send_result['total']
            }
            
            if 'error' in send_result:
                response_data['telegram_error'] = send_result['error']
            
            return web.json_response(response_data)
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
            # Отправляем уведомление админам
            await send_backup_to_telegram(
                backup_path,
                f"🔄 БД восстановлена из бэкапа\n📁 {file_name}\n⚠️ Перезапустите бота для применения изменений"
            )
            
            return web.json_response({
                'success': True,
                'message': f'БД восстановлена из {file_name}. Перезапустите бота для применения изменений.',
                'timestamp': datetime.now().isoformat(),
                'requires_restart': True
            })
        else:
            return web.json_response({
                'success': False,
                'error': 'Ошибка восстановления БД'
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
        
        return web.json_response({
            'success': True,
            'db_info': db_info,
            'backup_count': len(backups),
            'timestamp': datetime.now().isoformat()
        })
            
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)

async def api_download_backup(request):
    """API для скачивания бэкапа"""
    try:
        file_name = request.query.get('file', '')
        if not file_name:
            return web.Response(status=400, text="Не указано имя файла")
        
        backup_path = os.path.join('backups', file_name)
        if not os.path.exists(backup_path):
            return web.Response(status=404, text="Файл не найден")
        
        return web.FileResponse(
            backup_path,
            headers={
                'Content-Disposition': f'attachment; filename="{file_name}"',
                'Content-Type': 'application/octet-stream'
            }
        )
        
    except Exception as e:
        return web.Response(status=500, text=f"Ошибка: {e}")

async def api_get_backup_info(request):
    """API для получения информации о бэкапе"""
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
                'error': 'Файл не найден'
            }, status=404)
        
        # Получаем информацию о файле
        stat = os.stat(backup_path)
        size_mb = stat.st_size / (1024 * 1024)
        created = datetime.fromtimestamp(stat.st_ctime)
        
        # Получаем информацию о содержимом БД
        conn = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        table_info = []
        total_records = 0
        
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                total_records += count
                
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                
                table_info.append({
                    'name': table,
                    'records': count,
                    'columns': len(columns),
                    'column_names': [col[1] for col in columns[:5]]
                })
            except:
                continue
        
        conn.close()
        
        html = f'''
        <div style="margin-bottom: 20px;">
            <div style="font-weight: 600; color: var(--primary); margin-bottom: 5px;">Имя файла:</div>
            <div>{file_name}</div>
        </div>
        
        <div style="margin-bottom: 20px;">
            <div style="font-weight: 600; color: var(--primary); margin-bottom: 5px;">Размер:</div>
            <div>{size_mb:.2f} MB ({stat.st_size:,} байт)</div>
        </div>
        
        <div style="margin-bottom: 20px;">
            <div style="font-weight: 600; color: var(--primary); margin-bottom: 5px;">Дата создания:</div>
            <div>{created.strftime('%d.%m.%Y %H:%M:%S')}</div>
        </div>
        
        <div style="margin-bottom: 20px;">
            <div style="font-weight: 600; color: var(--primary); margin-bottom: 5px;">Таблиц:</div>
            <div>{len(tables)}</div>
        </div>
        
        <div style="margin-bottom: 20px;">
            <div style="font-weight: 600; color: var(--primary); margin-bottom: 5px;">Всего записей:</div>
            <div>{total_records:,}</div>
        </div>
        
        <div style="margin-bottom: 20px;">
            <div style="font-weight: 600; color: var(--primary); margin-bottom: 10px;">Таблицы:</div>
            <div style="max-height: 300px; overflow-y: auto;">
        '''
        
        for table in table_info:
            html += f'''
            <div style="background: #f7fafc; padding: 10px; margin-bottom: 10px; border-radius: 8px; border-left: 4px solid var(--primary);">
                <div style="font-weight: 600; color: var(--primary);">{table['name']}</div>
                <div style="font-size: 0.9em; color: var(--gray);">
                    Записей: {table['records']:,} | Колонок: {table['columns']}<br>
                    Колонки: {', '.join(table['column_names'])}{'...' if len(table['column_names']) < table['columns'] else ''}
                </div>
            </div>
            '''
        
        html += '''
            </div>
        </div>
        
        <div style="background: rgba(16, 185, 129, 0.1); padding: 15px; border-radius: 10px;">
            <div style="font-weight: 600; color: var(--success); margin-bottom: 5px;">Действия:</div>
            <div style="display: flex; gap: 10px;">
                <button onclick="restoreBackup('''' + file_name + '''')" class="btn btn-secondary" style="flex: 1;">
                    <i class="fas fa-undo"></i> Восстановить
                </button>
                <button onclick="sendToAdmins('''' + file_name + '''')" class="btn btn-warning" style="flex: 1;">
                    <i class="fas fa-paper-plane"></i> Отправить админам
                </button>
            </div>
        </div>
        '''
        
        return web.json_response({
            'success': True,
            'html': html
        })
        
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)

async def api_get_db_detailed_info(request):
    """API для получения детальной информации о текущей БД"""
    try:
        db_info = db_manager.get_db_info()
        db_path = db_manager.db_path
        
        if not os.path.exists(db_path):
            return web.json_response({
                'success': False, 
                'error': 'БД не найдена'
            }, status=404)
        
        stat = os.stat(db_path)
        size_mb = stat.st_size / (1024 * 1024)
        modified = datetime.fromtimestamp(stat.st_mtime)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Получаем статистику по пользователям
        try:
            cursor.execute("SELECT COUNT(*) FROM users")
            users_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE anon_link_uid IS NOT NULL")
            active_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE available_reveals > 0")
            premium_users = cursor.fetchone()[0]
        except:
            users_count = active_users = premium_users = 0
        
        # Получаем статистику по сообщениям
        try:
            cursor.execute("SELECT COUNT(*) FROM anon_messages")
            messages_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM anon_messages WHERE timestamp >= datetime('now', '-1 day')")
            messages_today = cursor.fetchone()[0]
        except:
            messages_count = messages_today = 0
        
        # Получаем статистику по платежам
        try:
            cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'completed'")
            payments_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(amount) FROM payments WHERE status = 'completed'")
            total_revenue = cursor.fetchone()[0] or 0
        except:
            payments_count = total_revenue = 0
        
        conn.close()
        
        html = f'''
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 30px;">
            <div style="background: rgba(99, 102, 241, 0.1); padding: 20px; border-radius: 15px;">
                <div style="font-weight: 600; color: var(--primary); margin-bottom: 5px;">Размер БД:</div>
                <div style="font-size: 1.5em; font-weight: 800;">{size_mb:.2f} MB</div>
            </div>
            
            <div style="background: rgba(16, 185, 129, 0.1); padding: 20px; border-radius: 15px;">
                <div style="font-weight: 600; color: var(--success); margin-bottom: 5px;">Последнее изменение:</div>
                <div>{modified.strftime('%d.%m.%Y %H:%M:%S')}</div>
            </div>
            
            <div style="background: rgba(139, 92, 246, 0.1); padding: 20px; border-radius: 15px;">
                <div style="font-weight: 600; color: var(--secondary); margin-bottom: 5px;">Всего таблиц:</div>
                <div style="font-size: 1.5em; font-weight: 800;">{db_info.get('table_count', 0)}</div>
            </div>
            
            <div style="background: rgba(245, 158, 11, 0.1); padding: 20px; border-radius: 15px;">
                <div style="font-weight: 600; color: var(--warning); margin-bottom: 5px;">Всего записей:</div>
                <div style="font-size: 1.5em; font-weight: 800;">{db_info.get('total_records', 0):,}</div>
            </div>
        </div>
        
        <div style="background: white; padding: 20px; border-radius: 15px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <h4 style="color: var(--primary); margin-bottom: 15px;">📊 Статистика пользователей</h4>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
                <div>
                    <div style="font-weight: 600; color: var(--gray);">Всего пользователей:</div>
                    <div style="font-size: 1.2em; font-weight: 600;">{users_count}</div>
                </div>
                <div>
                    <div style="font-weight: 600; color: var(--gray);">Активных пользователей:</div>
                    <div style="font-size: 1.2em; font-weight: 600;">{active_users}</div>
                </div>
                <div>
                    <div style="font-weight: 600; color: var(--gray);">Премиум пользователей:</div>
                    <div style="font-size: 1.2em; font-weight: 600;">{premium_users}</div>
                </div>
            </div>
        </div>
        
        <div style="background: white; padding: 20px; border-radius: 15px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <h4 style="color: var(--primary); margin-bottom: 15px;">📨 Статистика сообщений</h4>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
                <div>
                    <div style="font-weight: 600; color: var(--gray);">Всего сообщений:</div>
                    <div style="font-size: 1.2em; font-weight: 600;">{messages_count}</div>
                </div>
                <div>
                    <div style="font-weight: 600; color: var(--gray);">Сообщений за 24ч:</div>
                    <div style="font-size: 1.2em; font-weight: 600;">{messages_today}</div>
                </div>
            </div>
        </div>
        
        <div style="background: white; padding: 20px; border-radius: 15px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <h4 style="color: var(--primary); margin-bottom: 15px;">💰 Финансовая статистика</h4>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
                <div>
                    <div style="font-weight: 600; color: var(--gray);">Всего платежей:</div>
                    <div style="font-size: 1.2em; font-weight: 600;">{payments_count}</div>
                </div>
                <div>
                    <div style="font-weight: 600; color: var(--gray);">Общая выручка:</div>
                    <div style="font-size: 1.2em; font-weight: 600;">{total_revenue / 100:.2f} ₽</div>
                </div>
            </div>
        </div>
        
        <div style="background: rgba(16, 185, 129, 0.1); padding: 20px; border-radius: 15px; margin-top: 20px;">
            <h4 style="color: var(--success); margin-bottom: 15px;">⚡ Быстрые действия</h4>
            <div style="display: flex; gap: 10px;">
                <button onclick="sendCurrentDbToAdmins()" class="btn btn-warning" style="flex: 1;">
                    <i class="fas fa-paper-plane"></i> Отправить эту БД админам
                </button>
                <button onclick="createNewBackup()" class="btn btn-success" style="flex: 1;">
                    <i class="fas fa-plus"></i> Создать бекап
                </button>
            </div>
        </div>
        '''
        
        return web.json_response({
            'success': True,
            'html': html
        })
        
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)

async def api_send_to_admins(request):
    """API для отправки бэкапа админам"""
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
                'error': 'Файл не найден'
            }, status=404)
        
        # Отправляем админам через Telegram
        result = await send_backup_to_telegram(backup_path, f"📁 Бекап БД: {file_name}")
        
        if 'error' in result:
            return web.json_response({
                'success': False,
                'error': result['error'],
                'sent': result['sent'],
                'total': result['total']
            })
        else:
            return web.json_response({
                'success': True,
                'sent': result['sent'],
                'total': result['total'],
                'message': f'Отправлено {result["sent"]} из {result["total"]} админам'
            })
            
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)

async def api_send_current_db_to_admins(request):
    """API для отправки текущей БД админам"""
    try:
        # Отправляем текущую БД
        result = await send_backup_to_telegram(
            db_manager.db_path, 
            "💾 Текущая база данных"
        )
        
        if 'error' in result:
            return web.json_response({
                'success': False,
                'error': result['error'],
                'sent': result['sent'],
                'total': result['total']
            })
        else:
            return web.json_response({
                'success': True,
                'sent': result['sent'],
                'total': result['total'],
                'message': f'Отправлено {result["sent"]} из {result["total"]} админам'
            })
            
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)

async def api_upload_db(request):
    """API для загрузки новой БД"""
    try:
        reader = await request.multipart()
        field = await reader.next()
        
        if field.name != 'database':
            return web.json_response({
                'success': False,
                'error': 'Неверное поле'
            }, status=400)
        
        filename = field.filename
        if not filename.endswith('.db'):
            return web.json_response({
                'success': False,
                'error': 'Только файлы .db разрешены'
            }, status=400)
        
        # Создаем директорию uploads если нет
        upload_dir = 'uploads'
        os.makedirs(upload_dir, exist_ok=True)
        
        filepath = os.path.join(upload_dir, f"upload_{int(datetime.now().timestamp())}_{filename}")
        
        # Записываем файл
        size = 0
        with open(filepath, 'wb') as f:
            while True:
                chunk = await field.read_chunk()
                if not chunk:
                    break
                size += len(chunk)
                f.write(chunk)
        
        print(f"📁 Файл загружен: {filepath} ({size} байт)")
        
        # Проверяем валидность
        if not db_manager.validate_backup(filepath):
            os.remove(filepath)
            return web.json_response({
                'success': False,
                'error': 'Файл не является валидной SQLite БД'
            }, status=400)
        
        # Создаем бекап текущей БД если запрошено
        data = await request.post()
        create_backup = data.get('create_backup', 'off') == 'on'
        
        if create_backup:
            db_manager.create_backup("before_upload_backup.db", send_to_admins=False)
            print("✅ Бекап текущей БД создан")
        
        # Восстанавливаем БД
        print(f"🔄 Восстанавливаю БД из {filepath}")
        success = db_manager.restore_from_backup(filepath)
        
        # Очищаем загруженный файл
        if os.path.exists(filepath):
            os.remove(filepath)
        
        if success:
            print("✅ БД восстановлена успешно")
            
            # Отправляем админам если запрошено
            send_to_admins = data.get('send_to_admins', 'off') == 'on'
            if send_to_admins:
                await send_backup_to_telegram(
                    db_manager.db_path, 
                    "🔄 Новая БД загружена через веб-панель"
                )
            
            return web.json_response({
                'success': True,
                'message': '✅ БД успешно загружена и восстановлена!\n⚠️ Перезапустите бота для применения изменений.',
                'requires_restart': True,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return web.json_response({
                'success': False,
                'error': '❌ Ошибка восстановления БД'
            }, status=500)
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({
            'success': False,
            'error': f'❌ Ошибка: {str(e)}'
        }, status=500)

async def api_send_backup(request):
    """Старая версия для совместимости"""
    file_name = request.query.get('file', '')
    return web.json_response({
        'success': True,
        'message': f'Backup {file_name} будет отправлен',
        'timestamp': datetime.now().isoformat()
    })
