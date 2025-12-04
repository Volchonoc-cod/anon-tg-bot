"""
Веб-сервер для Render, который держит бота живым
"""
import os
import sys
import asyncio
import logging
import aiohttp
from aiohttp import web
from datetime import datetime
import glob
import json

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальные переменные
bot_task = None
keep_alive_task = None
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "")

# ============================================
# 1. ФУНКЦИЯ САМОПИНГА (держит Render активным)
# ============================================
async def keep_alive_ping():
    """Постоянный пинг самого себя каждые 20 секунд"""
    # Определяем URL для пинга
    if RENDER_URL:
        base_url = RENDER_URL
    else:
        port = os.getenv("PORT", "8080")
        base_url = f"http://localhost:{port}"
    
    ping_url = f"{base_url}/ping"
    logger.info(f"🚀 Запуск самопинга на {ping_url}")
    
    ping_count = 0
    
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(ping_url, timeout=10) as response:
                        if response.status == 200:
                            ping_count += 1
                            if ping_count % 10 == 0:
                                logger.info(f"✅ Самопинг #{ping_count} успешен")
                        else:
                            logger.warning(f"⚠️ Самопинг #{ping_count} вернул {response.status}")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка самопинга #{ping_count}: {e}")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка самопинга: {e}")
        
        await asyncio.sleep(20)

# ============================================
# 2. ФУНКЦИЯ ПИНГА АДМИНУ (каждые 13 минут)
# ============================================
async def admin_ping():
    """Пинг админу каждые 13 минут о статусе бота"""
    if not BOT_TOKEN or not ADMIN_IDS:
        logger.warning("⚠️ BOT_TOKEN или ADMIN_IDS не установлены, пропускаю админ-пинг")
        return
    
    start_time = datetime.now()
    
    while True:
        try:
            await asyncio.sleep(13 * 60)
            
            uptime = datetime.now() - start_time
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            
            message = (
                f"🔄 <b>Авто-пинг бота</b>\n\n"
                f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n"
                f"⏱ Аптайм: {hours}ч {minutes}м\n"
                f"🌐 Статус: <code>Активен на Render</code>\n\n"
                f"✅ Бот работает 24/7"
            )
            
            async with aiohttp.ClientSession() as session:
                for admin_id in ADMIN_IDS:
                    if not admin_id.strip():
                        continue
                    
                    try:
                        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                        payload = {
                            "chat_id": int(admin_id.strip()),
                            "text": message,
                            "parse_mode": "HTML"
                        }
                        
                        async with session.post(url, json=payload, timeout=10) as resp:
                            if resp.status == 200:
                                logger.info(f"✅ Пинг отправлен админу {admin_id}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки админу {admin_id}: {e}")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка в админ-пинге: {e}")
            await asyncio.sleep(60)

# ============================================
# 3. ФУНКЦИЯ ЗАПУСКА БОТА
# ============================================
async def start_your_bot():
    """Запускает бота из run_bot.py"""
    try:
        logger.info("🤖 Запуск Telegram бота...")
        
        # Импортируем и запускаем бота
        from run_bot import run_bot_async
        await run_bot_async()
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
        await asyncio.sleep(30)
        asyncio.create_task(start_your_bot())

# ============================================
# 4. HTTP ХЕНДЛЕРЫ
# ============================================
async def health_handler(request):
    """Health check для Render"""
    return web.Response(text="OK")

async def ping_handler(request):
    """Простой пинг-эндпоинт"""
    return web.Response(text=f"pong {datetime.now().strftime('%H:%M:%S')}")

async def status_handler(request):
    """Статус сервера"""
    status = {
        "status": "running",
        "time": datetime.now().isoformat(),
        "service": "anon-tg-bot"
    }
    return web.json_response(status)

# ============================================
# 5. BACKUP ХЕНДЛЕРЫ
# ============================================
async def list_files_handler(request):
    """Показать все backup файлы в проекте"""
    files_list = []
    
    # Возможные места хранения backups
    possible_dirs = [
        '/opt/render/project/src/backups',
        '/tmp/backups',
        '/opt/render/project/src',
        '/opt/render/project/src/app/data',
        '/home/render',
        '/tmp',
        './backups',
        './app/data',
        '.'
    ]
    
    for backup_dir in possible_dirs:
        if os.path.exists(backup_dir):
            # Ищем .db файлы
            for root, dirs, files in os.walk(backup_dir):
                for file in files:
                    if file.endswith('.db'):
                        filepath = os.path.join(root, file)
                        try:
                            size_bytes = os.path.getsize(filepath)
                            size_mb = size_bytes / (1024 * 1024)
                            modified_time = os.path.getmtime(filepath)
                            
                            files_list.append({
                                'name': file,
                                'path': filepath,
                                'size_mb': f"{size_mb:.2f}",
                                'size_bytes': size_bytes,
                                'modified': datetime.fromtimestamp(modified_time).strftime('%Y-%m-%d %H:%M:%S'),
                                'directory': backup_dir
                            })
                        except Exception as e:
                            logger.error(f"Ошибка чтения файла {filepath}: {e}")
    
    # Сортируем по дате изменения (новые сверху)
    files_list.sort(key=lambda x: x.get('modified', ''), reverse=True)
    
    # Статистика
    total_size = sum(f['size_bytes'] for f in files_list)
    total_size_mb = total_size / (1024 * 1024)
    
    # Формируем HTML ответ
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Backup файлы бота</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1 { color: #333; }
            h2 { color: #555; }
            h3 { color: #666; }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            tr:hover { background-color: #f5f5f5; }
            a { color: #0066cc; text-decoration: none; }
            a.button { 
                background: #007bff; 
                color: white; 
                padding: 10px 15px; 
                text-decoration: none; 
                border-radius: 5px; 
                display: inline-block;
                margin: 5px;
            }
            a.button-success { background: #28a745; }
            a.button-warning { background: #ffc107; color: #212529; }
            a.button-danger { background: #dc3545; }
            a.button:hover { opacity: 0.9; }
            .empty { color: #999; font-style: italic; }
            .stats { 
                background: #e9ecef; 
                padding: 15px; 
                border-radius: 5px; 
                margin: 20px 0; 
            }
            .actions { 
                background: #d4edda; 
                padding: 15px; 
                border-radius: 5px; 
                margin: 20px 0; 
            }
            code { 
                background: #f8f9fa; 
                padding: 2px 6px; 
                border-radius: 4px; 
                font-family: monospace;
            }
        </style>
    </head>
    <body>
        <h1>📁 Backup файлы бота</h1>
        
        <div class="stats">
            <h3>📊 Статистика backups:</h3>
            <p>📁 Всего файлов: <b>""" + str(len(files_list)) + """</b></p>
            <p>💾 Общий размер: <b>""" + f"{total_size_mb:.2f}" + """ MB</b></p>
            <p>📅 Последний backup: <b>""" + (files_list[0]['modified'] if files_list else 'нет') + """</b></p>
        </div>
        
        <div class="actions">
            <h3>⚡ Быстрые действия:</h3>
            <p>
                <a href="/create_backup" class="button button-success">
                    🔄 Создать новый backup
                </a>
                <a href="/send_backup_to_telegram?file=latest" class="button">
                    📤 Отправить последний backup в Telegram
                </a>
                <a href="/" class="button button-warning">
                    🏠 На главную
                </a>
            </p>
        </div>
    """
    
    if files_list:
        html += f"""
        <h2>📋 Список backup файлов ({len(files_list)})</h2>
        <table>
            <tr>
                <th>Имя файла</th>
                <th>Размер</th>
                <th>Изменен</th>
                <th>Папка</th>
                <th>Действия</th>
            </tr>
        """
        
        for file_info in files_list:
            download_url = f"/download_backup?file={file_info['name']}"
            telegram_url = f"/send_backup_to_telegram?file={file_info['name']}"
            
            html += f"""
            <tr>
                <td><code>{file_info['name']}</code></td>
                <td>{file_info['size_mb']} MB</td>
                <td>{file_info['modified']}</td>
                <td><code>{file_info['directory']}</code></td>
                <td>
                    <a href="{download_url}" class="button" style="padding: 5px 10px; font-size: 12px; margin: 2px;">📥 Скачать</a>
                    <a href="{telegram_url}" class="button button-success" style="padding: 5px 10px; font-size: 12px; margin: 2px;">📤 Telegram</a>
                </td>
            </tr>
            """
        
        html += "</table>"
    else:
        html += '''
        <div style="text-align: center; padding: 40px;">
            <h2 class="empty">😕 Файлы backups не найдены</h2>
            <p>Возможные причины:</p>
            <ul style="text-align: left; display: inline-block;">
                <li>Backup еще не создан</li>
                <li>Файлы удалены при перезапуске Render</li>
                <li>Файлы находятся в другой директории</li>
            </ul>
            <p style="margin-top: 20px;">
                <a href="/create_backup" class="button button-success">🔄 Создать первый backup</a>
            </p>
        </div>
        '''
    
    # Добавляем форму для поиска
    html += """
    <div style="margin-top: 30px; padding: 20px; background-color: #f8f9fa; border-radius: 5px;">
        <h3>🔍 Поиск файла</h3>
        <form action="/download_backup" method="get">
            <label for="filename">Имя файла:</label>
            <input type="text" id="filename" name="file" placeholder="bot_backup_20251204_095137.db" 
                   style="padding: 8px; width: 300px; border: 1px solid #ddd; border-radius: 4px;">
            <button type="submit" style="padding: 8px 16px; background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; margin-left: 10px;">
                Поиск и скачивание
            </button>
        </form>
    </div>
    
    <div style="margin-top: 20px;">
        <p>
            <a href="/" class="button">🏠 На главную</a>
            <a href="/status" class="button">📊 Статус</a>
            <a href="/ping" class="button">🔄 Ping</a>
        </p>
    </div>
    """
    
    html += "</body></html>"
    
    return web.Response(text=html, content_type='text/html')

async def download_backup_handler(request):
    """Скачать backup файл"""
    backup_name = request.query.get('file', '')
    if not backup_name:
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Ошибка</title></head>
        <body>
            <h1>❌ Ошибка</h1>
            <p>Укажите имя файла в параметре file</p>
            <p>Пример: <code>/download_backup?file=bot_backup_20251204_095137.db</code></p>
            <p><a href="/files">📁 Посмотреть все файлы</a></p>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html', status=400)
    
    # Проверяем безопасность имени файла
    if '..' in backup_name or '/' in backup_name or '\\' in backup_name:
        return web.Response(text="Некорректное имя файла", status=400)
    
    # Если запрошен latest, ищем последний файл
    if backup_name == 'latest':
        possible_dirs = ['/opt/render/project/src/backups', '/tmp/backups', './backups']
        latest_file = None
        latest_time = 0
        
        for backup_dir in possible_dirs:
            if os.path.exists(backup_dir):
                for file in os.listdir(backup_dir):
                    if file.startswith('bot_backup_') and file.endswith('.db'):
                        filepath = os.path.join(backup_dir, file)
                        mtime = os.path.getmtime(filepath)
                        if mtime > latest_time:
                            latest_time = mtime
                            latest_file = file
        
        if latest_file:
            backup_name = latest_file
            logger.info(f"🔍 Найден последний backup: {backup_name}")
        else:
            return web.Response(text="Не найден ни один backup файл", status=404)
    
    logger.info(f"🔍 Поиск файла: {backup_name}")
    
    # Ищем файл в возможных местах
    possible_paths = [
        f'/opt/render/project/src/backups/{backup_name}',
        f'/tmp/backups/{backup_name}',
        f'/opt/render/project/src/{backup_name}',
        f'/opt/render/project/src/app/data/{backup_name}',
        f'/home/render/{backup_name}',
        f'/tmp/{backup_name}',
        f'./backups/{backup_name}',
        f'./app/data/{backup_name}',
        f'./{backup_name}',
    ]
    
    found_path = None
    for filepath in possible_paths:
        if os.path.exists(filepath):
            found_path = filepath
            logger.info(f"✅ Файл найден: {filepath}")
            break
    
    if not found_path:
        # Попробуем поискать рекурсивно
        logger.info("Рекурсивный поиск файла...")
        search_dirs = ['/opt/render', '/tmp', '/home/render', '.']
        for search_dir in search_dirs:
            if os.path.exists(search_dir):
                for root, dirs, files in os.walk(search_dir):
                    if backup_name in files:
                        found_path = os.path.join(root, backup_name)
                        logger.info(f"✅ Файл найден (рекурсивно): {found_path}")
                        break
                if found_path:
                    break
    
    if found_path:
        try:
            # Проверяем размер файла
            file_size = os.path.getsize(found_path)
            logger.info(f"📦 Размер файла: {file_size / (1024 * 1024):.2f} MB")
            
            return web.FileResponse(
                path=found_path,
                headers={
                    'Content-Disposition': f'attachment; filename="{backup_name}"',
                    'Content-Type': 'application/octet-stream'
                }
            )
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке файла: {e}")
            return web.Response(text=f"Ошибка: {e}", status=500)
    else:
        logger.warning(f"❌ Файл не найден: {backup_name}")
        
        # Возвращаем страницу с информацией
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Файл не найден</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                code {{ background: #f5f5f5; padding: 2px 5px; border-radius: 3px; }}
                a {{ color: #0066cc; text-decoration: none; }}
                a.button {{ 
                    background: #007bff; 
                    color: white; 
                    padding: 10px 15px; 
                    text-decoration: none; 
                    border-radius: 5px; 
                    display: inline-block;
                    margin: 5px;
                }}
            </style>
        </head>
        <body>
            <h1>❌ Файл не найден</h1>
            <p>Файл <code>{backup_name}</code> не найден на сервере.</p>
            
            <h3>Возможные причины:</h3>
            <ul>
                <li>Файл был удален при перезапуске Render</li>
                <li>Неправильное имя файла</li>
                <li>Файл находится в другой директории</li>
            </ul>
            
            <h3>Что делать:</h3>
            <p>
                <a href="/files" class="button">📁 Посмотреть все доступные файлы</a>
                <a href="/create_backup" class="button" style="background: #28a745;">🔄 Создать новый backup</a>
            </p>
            
            <p><a href="/">🏠 На главную</a></p>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html', status=404)

async def send_backup_to_telegram_handler(request):
    """Отправить backup файл в Telegram - исправленная версия для aiogram 3.x"""
    from aiogram import Bot
    from aiogram.types import BufferedInputFile
    
    backup_name = request.query.get('file', '')
    
    # Если запрошен latest, ищем последний файл
    if backup_name == 'latest':
        possible_dirs = ['/opt/render/project/src/backups', '/tmp/backups', './backups']
        latest_file = None
        latest_time = 0
        
        for backup_dir in possible_dirs:
            if os.path.exists(backup_dir):
                for file in os.listdir(backup_dir):
                    if file.startswith('bot_backup_') and file.endswith('.db'):
                        filepath = os.path.join(backup_dir, file)
                        mtime = os.path.getmtime(filepath)
                        if mtime > latest_time:
                            latest_time = mtime
                            latest_file = file
        
        if latest_file:
            backup_name = latest_file
            logger.info(f"🔍 Найден последний backup: {backup_name}")
        else:
            return web.Response(
                text="Не найден ни один backup файл",
                content_type='text/plain',
                status=404
            )
    
    if not backup_name:
        return web.Response(
            text="Укажите имя файла: /send_backup_to_telegram?file=bot_backup_20251204_095137.db",
            content_type='text/plain',
            status=400
        )
    
    # Проверяем безопасность имени файла
    if '..' in backup_name or '/' in backup_name or '\\' in backup_name:
        return web.Response(text="Некорректное имя файла", status=400)
    
    logger.info(f"📤 Отправка файла в Telegram: {backup_name}")
    
    # Ищем файл
    found_path = None
    search_dirs = [
        '/opt/render/project/src/backups',
        '/opt/render/project/src/app/data',
        '/opt/render/project/src',
        '/tmp/backups',
        '/tmp',
        './backups',
        './app/data',
        '.'
    ]
    
    for search_dir in search_dirs:
        if os.path.exists(search_dir):
            test_path = os.path.join(search_dir, backup_name)
            if os.path.exists(test_path):
                found_path = test_path
                logger.info(f"✅ Файл найден: {found_path}")
                break
    
    if not found_path:
        # Рекурсивный поиск
        for root, dirs, files in os.walk('/opt/render'):
            if backup_name in files:
                found_path = os.path.join(root, backup_name)
                logger.info(f"✅ Файл найден (рекурсивно): {found_path}")
                break
    
    if not found_path or not os.path.exists(found_path):
        return web.Response(
            text=f"Файл {backup_name} не найден",
            content_type='text/plain',
            status=404
        )
    
    try:
        # Проверяем размер файла
        file_size = os.path.getsize(found_path)
        file_size_mb = file_size / (1024 * 1024)
        
        if file_size > 50 * 1024 * 1024:  # 50 MB лимит Telegram
            return web.Response(
                text=f"Файл слишком большой ({file_size_mb:.2f} MB). Лимит Telegram: 50 MB",
                content_type='text/plain',
                status=400
            )
        
        # Получаем настройки
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            return web.Response(
                text="Ошибка: BOT_TOKEN не установлен",
                content_type='text/plain',
                status=500
            )
        
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        admin_ids = [aid.strip() for aid in admin_ids_str.split(",") if aid.strip()]
        
        if not admin_ids:
            return web.Response(
                text="Ошибка: ADMIN_IDS не установлены",
                content_type='text/plain',
                status=500
            )
        
        logger.info(f"📨 Отправка файла {backup_name} ({file_size_mb:.2f} MB) админам: {admin_ids}")
        
        # Читаем файл в память
        with open(found_path, 'rb') as f:
            file_data = f.read()
        
        # Создаем бота
        bot = Bot(token=bot_token)
        
        success_count = 0
        errors = []
        
        # Отправляем каждому админу
        for admin_id in admin_ids:
            try:
                admin_id_int = int(admin_id)
                logger.info(f"  → Отправка админу {admin_id_int}")
                
                # Используем BufferedInputFile для aiogram 3.x
                input_file = BufferedInputFile(
                    file=file_data,
                    filename=backup_name
                )
                
                # Отправляем файл
                await bot.send_document(
                    chat_id=admin_id_int,
                    document=input_file,
                    caption=(
                        f"📦 <b>Backup базы данных</b>\n\n"
                        f"📁 Файл: {backup_name}\n"
                        f"📊 Размер: {file_size_mb:.2f} MB\n"
                        f"⏰ Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                        f"💾 Сохраните для восстановления"
                    ),
                    parse_mode="HTML"
                )
                
                success_count += 1
                logger.info(f"  ✅ Успешно отправлено админу {admin_id_int}")
                
                # Небольшая задержка между отправками
                await asyncio.sleep(0.5)
                
            except Exception as e:
                error_msg = f"Админ {admin_id}: {str(e)[:100]}"
                errors.append(error_msg)
                logger.error(f"  ❌ Ошибка админу {admin_id}: {e}")
        
        # Закрываем сессию
        await bot.session.close()
        
        # Формируем результат
        result_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Результат отправки</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .success {{ color: green; font-weight: bold; }}
                .error {{ color: red; }}
                .info {{ color: #17a2b8; }}
                .card {{ 
                    background: #f8f9fa; 
                    padding: 20px; 
                    border-radius: 8px;
                    margin: 20px 0;
                }}
                code {{ background: #e9ecef; padding: 2px 6px; border-radius: 4px; }}
                a.button {{ 
                    background: #007bff; 
                    color: white; 
                    padding: 10px 15px; 
                    text-decoration: none; 
                    border-radius: 5px; 
                    display: inline-block;
                    margin: 5px;
                }}
                a.button-success {{ background: #28a745; }}
            </style>
        </head>
        <body>
            <h1>📤 Результат отправки файла</h1>
            
            <div class="card info">
                <h3>📋 Информация о файле</h3>
                <p><strong>📁 Имя файла:</strong> <code>{backup_name}</code></p>
                <p><strong>📦 Размер:</strong> {file_size_mb:.2f} MB</p>
                <p><strong>⏰ Время отправки:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
            </div>
            
            <div class="card" style="background: #d4edda;">
                <h3 class="success">✅ Успешно отправлено: {success_count} из {len(admin_ids)}</h3>
                <p>Файл отправлен {success_count} администраторам</p>
            </div>
        """
        
        if errors:
            result_html += f"""
            <div class="card" style="background: #f8d7da;">
                <h3 class="error">❌ Ошибки отправки: {len(errors)}</h3>
                <ul>
            """
            for error in errors:
                result_html += f'<li>{error}</li>'
            result_html += """
                </ul>
            </div>
            """
        
        result_html += f"""
            <div style="margin-top: 30px;">
                <h3>🔗 Действия:</h3>
                <p>
                    <a href="/files" class="button">📁 Вернуться к списку файлов</a>
                    <a href="/download_backup?file={backup_name}" class="button button-success">📥 Скачать файл напрямую</a>
                    <a href="/create_backup" class="button" style="background: #ffc107; color: #212529;">🔄 Создать новый backup</a>
                </p>
            </div>
        </body>
        </html>
        """
        
        return web.Response(text=result_html, content_type='text/html')
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        
        return web.Response(
            text=f"Критическая ошибка: {str(e)}",
            content_type='text/plain',
            status=500
        )

async def create_backup_handler(request):
    """Создать новый backup"""
    try:
        from app.backup_service import backup_service
        
        # Создаем backup
        backup_path = backup_service.create_backup()
        
        if backup_path:
            backup_name = os.path.basename(backup_path)
            file_size = os.path.getsize(backup_path)
            file_size_mb = file_size / (1024 * 1024)
            
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Backup создан</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .success {{ color: #28a745; }}
                    .card {{ 
                        background: #d4edda; 
                        padding: 20px; 
                        border-radius: 8px;
                        margin: 20px 0;
                    }}
                    a.button {{ 
                        background: #007bff; 
                        color: white; 
                        padding: 10px 15px; 
                        text-decoration: none; 
                        border-radius: 5px; 
                        display: inline-block;
                        margin: 5px;
                    }}
                    a.button-success {{ background: #28a745; }}
                    code {{ background: #e9ecef; padding: 2px 6px; border-radius: 4px; }}
                </style>
            </head>
            <body>
                <h1 class="success">✅ Backup успешно создан!</h1>
                
                <div class="card">
                    <h3>📋 Информация о backup</h3>
                    <p><strong>📁 Файл:</strong> <code>{backup_name}</code></p>
                    <p><strong>📦 Размер:</strong> {file_size_mb:.2f} MB</p>
                    <p><strong>⏰ Время создания:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
                    <p><strong>📤 Статус отправки:</strong> Файл автоматически отправлен в Telegram всем админам.</p>
                </div>
                
                <div style="margin-top: 20px;">
                    <h3>🔗 Быстрые действия:</h3>
                    <p>
                        <a href="/download_backup?file={backup_name}" class="button">📥 Скачать backup</a>
                        <a href="/send_backup_to_telegram?file={backup_name}" class="button button-success">📤 Отправить в Telegram еще раз</a>
                        <a href="/files" class="button" style="background: #6c757d;">📁 Все backups</a>
                    </p>
                </div>
                
                <div style="margin-top: 30px;">
                    <p><a href="/">🏠 На главную</a></p>
                </div>
            </body>
            </html>
            """
            
            return web.Response(text=html, content_type='text/html')
        else:
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Ошибка создания backup</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    .error { color: #dc3545; }
                </style>
            </head>
            <body>
                <h1 class="error">❌ Ошибка создания backup</h1>
                <p>Не удалось создать резервную копию базы данных.</p>
                <p>Возможные причины:</p>
                <ul>
                    <li>База данных не найдена</li>
                    <li>Проблемы с правами доступа</li>
                    <li>Недостаточно места на диске</li>
                </ul>
                <p><a href="/files">📁 Вернуться к списку файлов</a></p>
            </body>
            </html>
            """
            
            return web.Response(text=html, content_type='text/html', status=500)
            
    except Exception as e:
        logger.error(f"Ошибка создания backup: {e}")
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Ошибка</title></head>
        <body>
            <h1 style="color: #dc3545;">❌ Критическая ошибка</h1>
            <p><strong>Ошибка:</strong> {str(e)}</p>
            <p><a href="/">🏠 На главную</a></p>
        </body>
        </html>
        """
        
        return web.Response(text=html, content_type='text/html', status=500)

# ============================================
# 6. СОЗДАНИЕ И ЗАПУСК ПРИЛОЖЕНИЯ
# ============================================
async def on_startup(app):
    """Запуск при старте приложения"""
    logger.info("🚀 Запуск приложения...")
    
    global keep_alive_task, bot_task
    keep_alive_task = asyncio.create_task(keep_alive_ping())
    asyncio.create_task(admin_ping())
    bot_task = asyncio.create_task(start_your_bot())
    
    logger.info("✅ Все задачи запущены")

async def on_cleanup(app):
    """Очистка при завершении"""
    logger.info("🛑 Остановка приложения...")
    
    if keep_alive_task:
        keep_alive_task.cancel()
    if bot_task:
        bot_task.cancel()

def create_app():
    """Создание aiohttp приложения"""
    app = web.Application()
    
    # Основные маршруты
    app.router.add_get('/', health_handler)
    app.router.add_get('/health', health_handler)
    app.router.add_get('/ping', ping_handler)
    app.router.add_get('/status', status_handler)
    
    # Backup маршруты
    app.router.add_get('/files', list_files_handler)
    app.router.add_get('/download_backup', download_backup_handler)
    app.router.add_get('/send_backup_to_telegram', send_backup_to_telegram_handler)
    app.router.add_get('/create_backup', create_backup_handler)
    
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    return app

# Создаем приложение
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info(f"🚀 Запуск сервера на порту {port}")
    web.run_app(app, host='0.0.0.0', port=port)
