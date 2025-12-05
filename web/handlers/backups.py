"""
Обработчик страницы управления бекапами
"""
from aiohttp import web
from web.utils.templates import get_base_html
import os
from datetime import datetime

# Импортируем менеджер БД
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from app.database_manager import db_manager

async def backups_handler(request):
    """Страница управления бекапами"""
    try:
        # Получаем список бэкапов через менеджер
        backups = db_manager.list_backups()
        
        # Получаем информацию о БД
        db_info = db_manager.get_db_info()
        
        backups_html = ''
        for backup in sorted(backups, key=lambda x: x['created'], reverse=True)[:10]:
            backups_html += f'''
            <tr>
                <td>{backup["name"]}</td>
                <td>{backup["size_mb"]:.2f} MB</td>
                <td>{backup["created"].strftime('%d.%m.%Y %H:%M')}</td>
                <td>{'✅' if backup['is_valid'] else '❌'}</td>
                <td>
                    <a href="/download_backup?file={backup['name']}" class="btn" style="padding: 8px 15px;">
                        <i class="fas fa-download"></i>
                    </a>
                    <button class="btn btn-secondary" style="padding: 8px 15px;" 
                            onclick="restoreBackup('{backup['name']}')">
                        <i class="fas fa-undo"></i>
                    </button>
                </td>
            </tr>
            '''
        
        # HTML для случая, когда нет бекапов
        no_backups_html = '''<tr><td colspan="5" style="padding: 20px; text-align: center; color: var(--gray);">Бекапы не найдены</td></tr>'''
        
        content = f'''
        <div class="glass-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;">
                <h2><i class="fas fa-database"></i> Управление бекапами БД</h2>
                <div style="display: flex; gap: 10px;">
                    <a href="/api/create_backup" class="btn btn-success">
                        <i class="fas fa-plus"></i> Создать бекап
                    </a>
                    <button class="btn btn-warning" onclick="cleanupBackups()">
                        <i class="fas fa-broom"></i> Очистить старые
                    </button>
                </div>
            </div>
            
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
            </div>
        </div>
        
        <script>
        function restoreBackup(filename) {{
            if (confirm(`Восстановить БД из бэкапа ${{filename}}?\\n\\nТекущая БД будет заменена!`)) {{
                fetch(`/api/restore_backup?file=${{encodeURIComponent(filename)}}`)
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            alert('✅ БД восстановлена! Перезапустите приложение.');
                        }} else {{
                            alert('❌ Ошибка: ' + data.error);
                        }}
                    }});
            }}
        }}
        
        function cleanupBackups() {{
            if (confirm('Удалить старые бэкапы (оставить 10 последних)?')) {{
                fetch('/api/cleanup_backups')
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            alert(`🧹 Удалено ${{data.deleted}} старых бэкапов`);
                            location.reload();
                        }}
                    }});
            }}
        }}
        </script>
        '''
        
        html = get_base_html("Управление бекапами", content, active_tab='/backups')
        return web.Response(text=html, content_type='text/html')
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.Response(text=f"Ошибка: {e}", content_type='text/html')
