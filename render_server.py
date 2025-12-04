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
        '/home/render',
        '/tmp',
        './backups',
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
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            tr:hover { background-color: #f5f5f5; }
            a { color: #0066cc; text-decoration: none; }
            a:hover { text-decoration: underline; }
            .empty { color: #999; font-style: italic; }
        </style>
    </head>
    <body>
        <h1>📁 Backup файлы бота</h1>
    """
    
    if files_list:
        html += f"<p>Найдено файлов: <b>{len(files_list)}</b></p>"
        html += """
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
            html += f"""
            <tr>
                <td><code>{file_info['name']}</code></td>
                <td>{file_info['size_mb']} MB</td>
                <td>{file_info['modified']}</td>
                <td><code>{file_info['directory']}</code></td>
                <td>
                    <a href="{download_url}" target="_blank">📥 Скачать</a> |
                    <a href="/send_backup_to_telegram?file={file_info['name']}">📤 Отправить в Telegram</a>
                </td>
            </tr>
            """
        
        html += "</table>"
    else:
        html += '<p class="empty">Файлы backups не найдены</p>'
        html += '<p>Возможные причины:</p>'
        html += '<ul>'
        html += '<li>Backup еще не создан</li>'
        html += '<li>Файлы удалены при перезапуске Render</li>'
        html += '<li>Файлы находятся в другой директории</li>'
        html += '</ul>'
    
    # Добавляем форму для поиска
    html += """
    <div style="margin-top: 30px; padding: 20px; background-color: #f8f9fa; border-radius: 5px;">
        <h3>🔍 Поиск файла</h3>
        <form action="/download_backup" method="get">
            <label for="filename">Имя файла:</label>
            <input type="text" id="filename" name="file" placeholder="bot_backup_20251204_095137.db" style="padding: 8px; width: 300px;">
            <button type="submit" style="padding: 8px 16px; background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">
                Поиск и скачивание
            </button>
        </form>
    </div>
    
    <div style="margin-top: 20px;">
        <p><a href="/">🏠 На главную</a> | <a href="/status">📊 Статус</a> | <a href="/ping">🔄 Ping</a></p>
    </div>
    """
    
    html += "</body></html>"
    
    return web.Response(text=html, content_type='text/html')

async def download_backup_handler(request):
    """Скачать backup файл"""
    backup_name = request.query.get('file', '')
    if not backup_name:
        return web.Response(
            text="Укажите имя файла: /download_backup?file=bot_backup_20251204_095137.db",
            content_type='text/plain'
        )
    
    # Проверяем безопасность имени файла
    if '..' in backup_name or '/' in backup_name or '\\' in backup_name:
        return web.Response(text="Некорректное имя файла", status=400)
    
    logger.info(f"🔍 Поиск файла: {backup_name}")
    
    # Ищем файл в возможных местах
    possible_paths = [
        f'/opt/render/project/src/backups/{backup_name}',
        f'/tmp/backups/{backup_name}',
        f'/opt/render/project/src/{backup_name}',
        f'/home/render/{backup_name}',
        f'/tmp/{backup_name}',
        f'./backups/{backup_name}',
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
        for root, dirs, files in os.walk('/opt/render'):
            if backup_name in files:
                found_path = os.path.join(root, backup_name)
                logger.info(f"✅ Файл найден (рекурсивно): {found_path}")
                break
        
        if not found_path:
            for root, dirs, files in os.walk('/tmp'):
                if backup_name in files:
                    found_path = os.path.join(root, backup_name)
                    logger.info(f"✅ Файл найден (рекурсивно): {found_path}")
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
        <head><title>Файл не найден</title></head>
        <body>
            <h1>❌ Файл не найден</h1>
            <p>Файл <code>{backup_name}</code> не найден на сервере.</p>
            <p>Возможные причины:</p>
            <ul>
                <li>Файл был удален при перезапуске Render</li>
                <li>Неправильное имя файла</li>
                <li>Файл находится в другой директории</li>
            </ul>
            <p><a href="/files">📁 Посмотреть все файлы</a></p>
            <p><a href="/">🏠 На главную</a></p>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html', status=404)

async def send_backup_to_telegram_handler(request):
    """Отправить backup файл в Telegram"""
    from aiogram import Bot
    from aiogram.types import InputFile
    
    backup_name = request.query.get('file', '')
    
    if not backup_name:
        return web.Response(
            text="Укажите имя файла: /send_backup_to_telegram?file=bot_backup_20251204_095137.db",
            content_type='text/plain'
        )
    
    # Проверяем безопасность имени файла
    if '..' in backup_name or '/' in backup_name or '\\' in backup_name:
        return web.Response(text="Некорректное имя файла", status=400)
    
    logger.info(f"📤 Отправка файла в Telegram: {backup_name}")
    
    # Ищем файл
    possible_paths = [
        f'/opt/render/project/src/backups/{backup_name}',
        f'/tmp/backups/{backup_name}',
        f'/opt/render/project/src/{backup_name}',
        f'/home/render/{backup_name}',
        f'/tmp/{backup_name}',
        f'./backups/{backup_name}',
        f'./{backup_name}',
    ]
    
    found_path = None
    for filepath in possible_paths:
        if os.path.exists(filepath):
            found_path = filepath
            logger.info(f"✅ Файл найден: {filepath}")
            break
    
    if not found_path:
        # Рекурсивный поиск
        logger.info("🔍 Рекурсивный поиск файла...")
        for root, dirs, files in os.walk('/opt/render'):
            if backup_name in files:
                found_path = os.path.join(root, backup_name)
                logger.info(f"✅ Файл найден (рекурсивно): {found_path}")
                break
        
        if not found_path:
            for root, dirs, files in os.walk('/tmp'):
                if backup_name in files:
                    found_path = os.path.join(root, backup_name)
                    logger.info(f"✅ Файл найден (рекурсивно): {found_path}")
                    break
    
    if not found_path or not os.path.exists(found_path):
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Файл не найден</title></head>
        <body>
            <h1>❌ Файл не найден</h1>
            <p>Файл <code>{backup_name}</code> не найден на сервере.</p>
            <p><a href="/files">📁 Посмотреть все файлы</a></p>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html', status=404)
    
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
        
        # Создаем Bot экземпляр
        bot = Bot(token=BOT_TOKEN)
        
        success_count = 0
        error_count = 0
        error_messages = []
        
        # Отправляем каждому админу
        for admin_id in ADMIN_IDS:
            if not admin_id.strip():
                continue
                
            try:
                admin_id_int = int(admin_id.strip())
                logger.info(f"📨 Отправка файла админу {admin_id_int}")
                
                # Сначала отправляем уведомление
                try:
                    await bot.send_message(
                        admin_id_int,
                        f"📤 <b>Отправка backup файла</b>\n\n"
                        f"📁 Файл: <code>{backup_name}</code>\n"
                        f"📦 Размер: {file_size_mb:.2f} MB\n"
                        f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n\n"
                        f"⏳ Загружаю файл...",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление админу {admin_id_int}: {e}")
                
                # Отправляем сам файл с правильным InputFile
                with open(found_path, 'rb') as file:
                    input_file = InputFile(file, filename=backup_name)
                    
                    await bot.send_document(
                        chat_id=admin_id_int,
                        document=input_file,
                        caption=(
                            f"📦 <b>Backup базы данных</b>\n\n"
                            f"📁 Файл: {backup_name}\n"
                            f"📊 Размер: {file_size_mb:.2f} MB\n"
                            f"⏰ Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                            f"💾 Сохраните этот файл для восстановления данных"
                        ),
                        parse_mode="HTML"
                    )
                
                success_count += 1
                logger.info(f"✅ Файл успешно отправлен админу {admin_id_int}")
                
                # Небольшая задержка между отправками
                await asyncio.sleep(1)
                
            except Exception as e:
                error_count += 1
                error_msg = f"Админ {admin_id}: {str(e)[:100]}"
                error_messages.append(error_msg)
                logger.error(f"❌ Ошибка отправки админу {admin_id}: {e}")
        
        # Закрываем сессию бота
        await bot.session.close()
        
        # Формируем результат
        result_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Результат отправки</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .success {{ color: green; }}
                .error {{ color: red; }}
                .info {{ color: blue; }}
            </style>
        </head>
        <body>
            <h1>📤 Результат отправки файла</h1>
            
            <div class="info">
                <p><strong>📁 Файл:</strong> {backup_name}</p>
                <p><strong>📦 Размер:</strong> {file_size_mb:.2f} MB</p>
                <p><strong>⏰ Время отправки:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
            </div>
            
            <div class="success">
                <h2>✅ Успешно отправлено: {success_count}</h2>
            </div>
            
            <div class="error">
                <h2>❌ Ошибок: {error_count}</h2>
                {f'<ul>{"".join([f"<li>{msg}</li>" for msg in error_messages])}</ul>' if error_messages else ''}
            </div>
            
            <div style="margin-top: 30px;">
                <p><a href="/files">📁 Вернуться к списку файлов</a></p>
                <p><a href="/">🏠 На главную</a></p>
            </div>
        </body>
        </html>
        """
        
        return web.Response(text=result_html, content_type='text/html')
        
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта aiogram: {e}")
        return web.Response(
            text="Ошибка: aiogram не установлен или настроен неправильно",
            content_type='text/plain',
            status=500
        )
    except Exception as e:
        logger.error(f"❌ Критическая ошибка отправки в Telegram: {e}")
        import traceback
        traceback_str = traceback.format_exc()
        logger.error(f"Трейсбэк: {traceback_str}")
        
        return web.Response(
            text=f"Ошибка отправки: {str(e)}",
            content_type='text/plain',
            status=500
        )

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
    
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    return app

# Создаем приложение
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info(f"🚀 Запуск сервера на порту {port}")
    web.run_app(app, host='0.0.0.0', port=port)
