"""
Обработчик страницы управления бекапами с возможностью загрузки, отправки и просмотра БД
"""
from aiohttp import web
from web.utils.templates import get_base_html
import os
import json
from datetime import datetime
import shutil
import sqlite3
from aiohttp import web
import aiohttp
import asyncio

# Импортируем менеджер БД
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from app.database_manager import db_manager
from app.config import ADMIN_IDS, BOT_TOKEN

async def backups_handler(request):
    """Страница управления бекапами"""
    try:
        # Получаем список бэкапов через менеджер
        backups = db_manager.list_backups()
        
        # Получаем информацию о БД
        db_info = db_manager.get_db_info()
        
        # Получаем информацию о текущей БД
        current_db_info = await get_current_db_info()
        
        backups_html = ''
        for backup in sorted(backups, key=lambda x: x['created'], reverse=True)[:10]:
            backups_html += f'''
            <tr>
                <td>{backup["name"]}</td>
                <td>{backup["size_mb"]:.2f} MB</td>
                <td>{backup["created"].strftime('%d.%m.%Y %H:%M')}</td>
                <td>{'✅' if backup['is_valid'] else '❌'}</td>
                <td>
                    <div style="display: flex; gap: 5px;">
                        <a href="/download_backup?file={backup['name']}" class="btn" style="padding: 8px 15px;" title="Скачать">
                            <i class="fas fa-download"></i>
                        </a>
                        <button class="btn btn-secondary" style="padding: 8px 15px;" 
                                onclick="restoreBackup('{backup['name']}')" title="Восстановить">
                            <i class="fas fa-undo"></i>
                        </button>
                        <button class="btn btn-warning" style="padding: 8px 15px;" 
                                onclick="sendToAdmins('{backup['name']}')" title="Отправить админам">
                            <i class="fas fa-paper-plane"></i>
                        </button>
                        <button class="btn btn-info" style="padding: 8px 15px;" 
                                onclick="showBackupInfo('{backup['name']}')" title="Информация">
                            <i class="fas fa-info-circle"></i>
                        </button>
                    </div>
                </td>
            </tr>
            '''
        
        # HTML для случая, когда нет бекапов
        no_backups_html = '''<tr><td colspan="5" style="padding: 20px; text-align: center; color: var(--gray);">Бекапы не найдены</td></tr>'''
        
        content = f'''
        <div class="glass-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;">
                <h2><i class="fas fa-database"></i> Управление базой данных</h2>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <a href="/api/create_backup" class="btn btn-success">
                        <i class="fas fa-plus"></i> Создать бекап
                    </a>
                    <button class="btn btn-warning" onclick="cleanupBackups()">
                        <i class="fas fa-broom"></i> Очистить старые
                    </button>
                    <button class="btn btn-info" onclick="showDbInfo()">
                        <i class="fas fa-chart-bar"></i> Статистика БД
                    </button>
                    <button class="btn btn-secondary" onclick="showUploadForm()">
                        <i class="fas fa-upload"></i> Загрузить БД
                    </button>
                    <button class="btn btn-danger" onclick="sendCurrentDbToAdmins()">
                        <i class="fas fa-share-alt"></i> Отправить текущую БД
                    </button>
                </div>
            </div>
            
            <!-- Форма загрузки БД (скрыта по умолчанию) -->
            <div id="uploadForm" style="display: none; margin-bottom: 30px; padding: 20px; background: rgba(99, 102, 241, 0.1); border-radius: 15px;">
                <h3><i class="fas fa-upload"></i> Загрузка новой базы данных</h3>
                <form id="dbUploadForm" enctype="multipart/form-data" style="margin-top: 20px;">
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 5px; font-weight: 600;">Выберите файл БД (.db):</label>
                        <input type="file" name="database" accept=".db" required style="
                            padding: 10px;
                            border: 2px dashed #cbd5e0;
                            border-radius: 10px;
                            width: 100%;
                            background: white;
                        ">
                    </div>
                    <div style="margin-bottom: 15px;">
                        <label>
                            <input type="checkbox" name="create_backup" checked>
                            Создать резервную копию текущей БД перед загрузкой
                        </label>
                    </div>
                    <div style="margin-bottom: 15px;">
                        <label>
                            <input type="checkbox" name="send_to_admins" checked>
                            Отправить новую БД всем админам
                        </label>
                    </div>
                    <div style="display: flex; gap: 10px;">
                        <button type="submit" class="btn btn-success" style="flex: 1;">
                            <i class="fas fa-upload"></i> Загрузить БД
                        </button>
                        <button type="button" class="btn btn-danger" onclick="hideUploadForm()" style="flex: 1;">
                            <i class="fas fa-times"></i> Отмена
                        </button>
                    </div>
                </form>
                <div id="uploadProgress" style="display: none; margin-top: 20px;">
                    <div class="progress-bar">
                        <div class="progress-fill" id="uploadProgressBar" style="width: 0%;"></div>
                    </div>
                    <div id="uploadStatus" style="text-align: center; margin-top: 10px;"></div>
                </div>
            </div>
            
            <!-- Информация о текущей БД -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px;">
                <div style="background: rgba(99, 102, 241, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                    <div style="font-size: 2em; font-weight: 800; color: var(--primary);">
                        {len(backups)}
                    </div>
                    <div style="color: var(--gray);">Всего бекапов</div>
                </div>
                <div style="background: rgba(16, 185, 129, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                    <div style="font-size: 2em; font-weight: 800; color: var(--success);">
                        {db_info.get('size_mb', 0):.2f}
                    </div>
                    <div style="color: var(--gray);">Размер БД (MB)</div>
                </div>
                <div style="background: rgba(245, 158, 11, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                    <div style="font-size: 2em; font-weight: 800; color: var(--warning);">
                        {len(db_info.get('tables', []))}
                    </div>
                    <div style="color: var(--gray);">Таблиц в БД</div>
                </div>
                <div style="background: rgba(139, 92, 246, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                    <div style="font-size: 2em; font-weight: 800; color: var(--secondary);">
                        {current_db_info.get('total_records', 0)}
                    </div>
                    <div style="color: var(--gray);">Всего записей</div>
                </div>
            </div>
            
            <!-- Детальная информация о БД -->
            <div style="margin-bottom: 30px; padding: 20px; background: rgba(139, 92, 246, 0.1); border-radius: 15px;">
                <h3><i class="fas fa-table"></i> Текущее состояние базы данных</h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; margin-top: 15px;">
                    {current_db_info.get('tables_html', '')}
                </div>
            </div>
            
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: var(--primary); color: white;">
                            <th style="padding: 15px; text-align: left;">Имя файла</th>
                            <th style="padding: 15px; text-align: left;">Размер</th>
                            <th style="padding: 15px; text-align: left;">Дата создания</th>
                            <th style="padding: 15px; text-align: left;">Валидность</th>
                            <th style="padding: 15px; text-align: left;">Действия</th>
                        </tr>
                    </thead>
                    <tbody>
                        {backups_html if backups_html else no_backups_html}
                    </tbody>
                </table>
            </div>
            
            <div style="margin-top: 30px; padding: 20px; background: rgba(16, 185, 129, 0.1); border-radius: 15px;">
                <h3><i class="fas fa-info-circle"></i> Информация о системе бэкапов</h3>
                <p>• Автоматический бэкап создается при выходе из приложения</p>
                <p>• При запуске проверяется целостность БД и при необходимости восстанавливается из бэкапа</p>
                <p>• Старые бэкапы автоматически удаляются (остается 10 последних)</p>
                <p>• Все бэкапы валидируются на корректность структуры</p>
                <p>• Загруженные БД проверяются на валидность перед восстановлением</p>
                <p>• Возможность отправки БД админам прямо из веб-панели</p>
            </div>
            
            <!-- Модальное окно для информации о бэкапе -->
            <div id="backupInfoModal" style="
                display: none;
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: white;
                padding: 30px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                z-index: 1000;
                max-width: 600px;
                width: 90%;
                max-height: 80vh;
                overflow-y: auto;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <h3><i class="fas fa-info-circle"></i> Информация о бэкапе</h3>
                    <button onclick="closeModal()" style="background: none; border: none; font-size: 1.5em; cursor: pointer; color: var(--danger);">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div id="backupInfoContent">
                    <!-- Информация будет загружена здесь -->
                </div>
                <div style="text-align: center; margin-top: 20px;">
                    <button onclick="closeModal()" class="btn">Закрыть</button>
                </div>
            </div>
            
            <!-- Модальное окно для информации о БД -->
            <div id="dbInfoModal" style="
                display: none;
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: white;
                padding: 30px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                z-index: 1000;
                max-width: 800px;
                width: 90%;
                max-height: 80vh;
                overflow-y: auto;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <h3><i class="fas fa-chart-bar"></i> Детальная информация о БД</h3>
                    <button onclick="closeModal()" style="background: none; border: none; font-size: 1.5em; cursor: pointer; color: var(--danger);">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div id="dbInfoContent">
                    <!-- Информация будет загружена здесь -->
                </div>
                <div style="text-align: center; margin-top: 20px;">
                    <button onclick="closeModal()" class="btn">Закрыть</button>
                </div>
            </div>
            
            <!-- Оверлей для модальных окон -->
            <div id="modalOverlay" style="
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.5);
                z-index: 999;
            "></div>
        </div>
        
        <script>
        function restoreBackup(filename) {{
            if (confirm(`Восстановить БД из бэкапа ${{filename}}?\\n\\nТекущая БД будет заменена!`)) {{
                showLoading('Восстановление БД...');
                fetch(`/api/restore_backup?file=${{encodeURIComponent(filename)}}`)
                    .then(response => response.json())
                    .then(data => {{
                        hideLoading();
                        if (data.success) {{
                            alert('✅ БД восстановлена! Перезапустите приложение для применения изменений.');
                        }} else {{
                            alert('❌ Ошибка: ' + data.error);
                        }}
                    }})
                    .catch(error => {{
                        hideLoading();
                        alert('❌ Ошибка сети: ' + error);
                    }});
            }}
        }}
        
        function cleanupBackups() {{
            if (confirm('Удалить старые бэкапы (оставить 10 последних)?')) {{
                showLoading('Очистка бэкапов...');
                fetch('/api/cleanup_backups')
                    .then(response => response.json())
                    .then(data => {{
                        hideLoading();
                        if (data.success) {{
                            alert(`🧹 Удалено ${{data.deleted}} старых бэкапов`);
                            location.reload();
                        }}
                    }});
            }}
        }}
        
        function sendToAdmins(filename) {{
            if (confirm(`Отправить бэкап ${{filename}} всем админам?`)) {{
                showLoading('Отправка админам...');
                fetch(`/api/send_to_admins?file=${{encodeURIComponent(filename)}}`)
                    .then(response => response.json())
                    .then(data => {{
                        hideLoading();
                        if (data.success) {{
                            alert(`✅ Отправлено ${{data.sent}}/${{data.total}} админам`);
                        }} else {{
                            alert('❌ Ошибка: ' + data.error);
                        }}
                    }});
            }}
        }}
        
        function sendCurrentDbToAdmins() {{
            if (confirm('Отправить текущую базу данных всем админам?')) {{
                showLoading('Отправка текущей БД...');
                fetch('/api/send_current_db_to_admins')
                    .then(response => response.json())
                    .then(data => {{
                        hideLoading();
                        if (data.success) {{
                            alert(`✅ Отправлено ${{data.sent}}/${{data.total}} админам`);
                        }} else {{
                            alert('❌ Ошибка: ' + data.error);
                        }}
                    }});
            }}
        }}
        
        function showBackupInfo(filename) {{
            showLoading('Загрузка информации...');
            fetch(`/api/get_backup_info?file=${{encodeURIComponent(filename)}}`)
                .then(response => response.json())
                .then(data => {{
                    hideLoading();
                    if (data.success) {{
                        document.getElementById('backupInfoContent').innerHTML = data.html;
                        showModal('backupInfoModal');
                    }} else {{
                        alert('❌ Ошибка: ' + data.error);
                    }}
                }});
        }}
        
        function showDbInfo() {{
            showLoading('Загрузка информации о БД...');
            fetch('/api/get_db_detailed_info')
                .then(response => response.json())
                .then(data => {{
                    hideLoading();
                    if (data.success) {{
                        document.getElementById('dbInfoContent').innerHTML = data.html;
                        showModal('dbInfoModal');
                    }} else {{
                        alert('❌ Ошибка: ' + data.error);
                    }}
                }});
        }}
        
        function showUploadForm() {{
            document.getElementById('uploadForm').style.display = 'block';
        }}
        
        function hideUploadForm() {{
            document.getElementById('uploadForm').style.display = 'none';
            document.getElementById('uploadProgress').style.display = 'none';
            document.getElementById('dbUploadForm').reset();
        }}
        
        function showModal(modalId) {{
            document.getElementById(modalId).style.display = 'block';
            document.getElementById('modalOverlay').style.display = 'block';
        }}
        
        function closeModal() {{
            document.getElementById('backupInfoModal').style.display = 'none';
            document.getElementById('dbInfoModal').style.display = 'none';
            document.getElementById('modalOverlay').style.display = 'none';
        }}
        
        function showLoading(message) {{
            // Можно добавить реализацию loading overlay
            console.log('Loading:', message);
        }}
        
        function hideLoading() {{
            console.log('Loading hidden');
        }}
        
        // Обработка формы загрузки БД
        document.getElementById('dbUploadForm').addEventListener('submit', async function(e) {{
            e.preventDefault();
            
            const formData = new FormData(this);
            const progressBar = document.getElementById('uploadProgressBar');
            const uploadStatus = document.getElementById('uploadStatus');
            const uploadProgress = document.getElementById('uploadProgress');
            
            uploadProgress.style.display = 'block';
            progressBar.style.width = '0%';
            uploadStatus.textContent = 'Начинаю загрузку...';
            
            try {{
                const response = await fetch('/api/upload_db', {{
                    method: 'POST',
                    body: formData
                }});
                
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let result = '';
                
                while (true) {{
                    const {{value, done}} = await reader.read();
                    if (done) break;
                    
                    result += decoder.decode(value);
                    
                    // Парсим прогресс из SSE
                    const lines = result.split('\\n');
                    for (const line of lines) {{
                        if (line.startsWith('data: ')) {{
                            const data = JSON.parse(line.slice(6));
                            if (data.progress) {{
                                progressBar.style.width = data.progress + '%';
                                uploadStatus.textContent = data.message;
                            }}
                            if (data.success !== undefined) {{
                                if (data.success) {{
                                    alert('✅ БД успешно загружена!');
                                    location.reload();
                                }} else {{
                                    alert('❌ Ошибка: ' + data.error);
                                }}
                            }}
                        }}
                    }}
                }}
            }} catch (error) {{
                uploadStatus.textContent = '❌ Ошибка загрузки: ' + error;
                progressBar.style.width = '100%';
            }}
        }});
        
        // Закрытие модального окна по клику на оверлей
        document.getElementById('modalOverlay').addEventListener('click', closeModal);
        </script>
        '''
        
        html = get_base_html("Управление базой данных", content, active_tab='/backups')
        return web.Response(text=html, content_type='text/html')
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.Response(text=f"Ошибка: {e}", content_type='text/html')

async def get_current_db_info():
    """Получить детальную информацию о текущей БД"""
    try:
        db_path = db_manager.db_path
        
        if not os.path.exists(db_path):
            return {"total_records": 0, "tables_html": "<p>БД не найдена</p>"}
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Получаем список таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        total_records = 0
        tables_html = ""
        
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                total_records += count
                
                # Получаем структуру таблицы
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                
                tables_html += f'''
                <div style="background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                    <div style="font-weight: 600; color: var(--primary); margin-bottom: 10px;">
                        {table} <span class="badge badge-success">{count} записей</span>
                    </div>
                    <div style="font-size: 0.9em; color: var(--gray);">
                        Колонки: {', '.join([col[1] for col in columns[:3]])}{'...' if len(columns) > 3 else ''}
                    </div>
                </div>
                '''
            except:
                continue
        
        conn.close()
        
        return {
            "total_records": total_records,
            "tables_html": tables_html,
            "tables": tables
        }
        
    except Exception as e:
        return {"total_records": 0, "tables_html": f"<p>Ошибка: {e}</p>"}

# Добавьте эти функции в ваш routes.py
async def download_backup(request):
    """Скачать бекап"""
    try:
        filename = request.query.get('file')
        if not filename:
            return web.Response(status=400, text="Не указано имя файла")
        
        filepath = os.path.join('backups', filename)
        if not os.path.exists(filepath):
            return web.Response(status=404, text="Файл не найден")
        
        return web.FileResponse(
            filepath,
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': 'application/octet-stream'
            }
        )
        
    except Exception as e:
        return web.Response(status=500, text=f"Ошибка: {e}")

async def upload_db_handler(request):
    """Обработчик загрузки БД"""
    try:
        reader = await request.multipart()
        field = await reader.next()
        
        if field.name != 'database':
            return web.Response(status=400, text="Неверное поле")
        
        filename = field.filename
        if not filename.endswith('.db'):
            return web.Response(status=400, text="Только файлы .db разрешены")
        
        # Создаем директорию uploads если нет
        upload_dir = 'uploads'
        os.makedirs(upload_dir, exist_ok=True)
        
        filepath = os.path.join(upload_dir, filename)
        
        # Записываем файл
        size = 0
        with open(filepath, 'wb') as f:
            while True:
                chunk = await field.read_chunk()
                if not chunk:
                    break
                size += len(chunk)
                f.write(chunk)
        
        # Проверяем валидность
        if not db_manager.validate_backup(filepath):
            os.remove(filepath)
            return web.Response(status=400, text="Файл не является валидной SQLite БД")
        
        # Создаем бекап текущей БД если запрошено
        data = await request.post()
        if 'create_backup' in data and data['create_backup'] == 'on':
            db_manager.create_backup("before_upload_backup.db", send_to_admins=False)
        
        # Восстанавливаем БД
        success = db_manager.restore_from_backup(filepath)
        
        if success:
            # Отправляем админам если запрошено
            if 'send_to_admins' in data and data['send_to_admins'] == 'on':
                await send_database_to_admins(db_manager.db_path, "Загруженная база данных")
            
            return web.json_response({
                "success": True,
                "message": "БД успешно загружена и восстановлена"
            })
        else:
            return web.json_response({
                "success": False,
                "error": "Ошибка восстановления БД"
            })
            
    except Exception as e:
        return web.Response(status=500, text=f"Ошибка: {e}")

async def send_database_to_admins(db_path, caption):
    """Отправить базу данных всем админам через Telegram"""
    try:
        if not BOT_TOKEN or not ADMIN_IDS:
            return {"sent": 0, "total": 0, "error": "Не настроен бот или админы"}
        
        from aiogram import Bot
        from aiogram.types import FSInputFile
        
        bot = Bot(token=BOT_TOKEN)
        sent_count = 0
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_document(
                    chat_id=admin_id,
                    document=FSInputFile(db_path),
                    caption=f"📁 {caption}\n⏰ {datetime.now().strftime('%H:%M:%S')}"
                )
                sent_count += 1
            except Exception as e:
                print(f"Ошибка отправки админу {admin_id}: {e}")
        
        await bot.session.close()
        return {"sent": sent_count, "total": len(ADMIN_IDS)}
        
    except Exception as e:
        return {"sent": 0, "total": len(ADMIN_IDS), "error": str(e)}

async def get_backup_info_handler(request):
    """Получить информацию о бэкапе"""
    try:
        filename = request.query.get('file')
        if not filename:
            return web.json_response({"success": False, "error": "Не указано имя файла"})
        
        filepath = os.path.join('backups', filename)
        if not os.path.exists(filepath):
            return web.json_response({"success": False, "error": "Файл не найден"})
        
        # Получаем информацию о файле
        stat = os.stat(filepath)
        size_mb = stat.st_size / (1024 * 1024)
        created = datetime.fromtimestamp(stat.st_ctime)
        
        # Получаем информацию о содержимом БД
        conn = sqlite3.connect(f"file:{filepath}?mode=ro", uri=True)
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
            <div>{filename}</div>
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
                <button onclick="restoreBackup('''' + filename + '''')" class="btn btn-secondary" style="flex: 1;">
                    <i class="fas fa-undo"></i> Восстановить
                </button>
                <button onclick="sendToAdmins('''' + filename + '''')" class="btn btn-warning" style="flex: 1;">
                    <i class="fas fa-paper-plane"></i> Отправить админам
                </button>
            </div>
        </div>
        '''
        
        return web.json_response({
            "success": True,
            "html": html
        })
        
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)})

async def get_db_detailed_info_handler(request):
    """Получить детальную информацию о текущей БД"""
    try:
        db_info = await get_current_db_info()
        db_path = db_manager.db_path
        
        if not os.path.exists(db_path):
            return web.json_response({
                "success": False, 
                "error": "БД не найдена"
            })
        
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
                <div style="font-size: 1.5em; font-weight: 800;">{len(db_info.get('tables', []))}</div>
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
                <a href="/api/create_backup" class="btn btn-success" style="flex: 1;">
                    <i class="fas fa-plus"></i> Создать бекап
                </a>
            </div>
        </div>
        '''
        
        return web.json_response({
            "success": True,
            "html": html
        })
        
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)})


# В backups.py или отдельном файле добавьте:
async def send_to_admins_handler(request):
    """Отправить бекап админам"""
    try:
        filename = request.query.get('file')
        if not filename:
            return web.json_response({"success": False, "error": "Не указано имя файла"})
        
        filepath = os.path.join('backups', filename)
        if not os.path.exists(filepath):
            return web.json_response({"success": False, "error": "Файл не найден"})
        
        result = await send_database_to_admins(filepath, f"Бекап БД: {filename}")
        
        return web.json_response({
            "success": "error" not in result or not result["error"],
            "sent": result["sent"],
            "total": result["total"],
            "error": result.get("error")
        })
        
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)})

async def send_current_db_to_admins_handler(request):
    """Отправить текущую БД админам"""
    try:
        result = await send_database_to_admins(
            db_manager.db_path, 
            "Текущая база данных"
        )
        
        return web.json_response({
            "success": "error" not in result or not result["error"],
            "sent": result["sent"],
            "total": result["total"],
            "error": result.get("error")
        })
        
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)})
