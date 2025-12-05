"""
Обработчик страницы управления бекапами
"""
from aiohttp import web
from web.utils.templates import get_base_html
import os
from datetime import datetime

async def backups_handler(request):
    """Страница управления бекапами"""
    backups_dir = 'backups'
    backups = []
    
    if os.path.exists(backups_dir):
        for file in os.listdir(backups_dir):
            if file.endswith('.db'):
                filepath = os.path.join(backups_dir, file)
                stat = os.stat(filepath)
                size_mb = stat.st_size / (1024 * 1024)
                date = datetime.fromtimestamp(stat.st_mtime)
                backups.append({
                    'name': file,
                    'size': f"{size_mb:.2f} MB",
                    'date': date.strftime('%d.%m.%Y %H:%M')
                })
    
    backups_html = ''
    for backup in sorted(backups, key=lambda x: x['date'], reverse=True)[:10]:
        backups_html += f'''
        <tr>
            <td>{backup['name']}</td>
            <td>{backup['size']}</td>
            <td>{backup['date']}</td>
            <td>
                <a href="/api/send_backup?file={backup['name']}" class="btn" style="padding: 8px 15px;">
                    <i class="fas fa-paper-plane"></i>
                </a>
            </td>
        </tr>
        '''
    
    content = f'''
    <div class="glass-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;">
            <h2><i class="fas fa-database"></i> Управление бекапами</h2>
            <a href="/api/create_backup" class="btn btn-success">
                <i class="fas fa-plus"></i> Создать бекап
            </a>
        </div>
        
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background: var(--primary); color: white;">
                        <th style="padding: 15px; text-align: left;">Имя файла</th>
                        <th style="padding: 15px; text-align: left;">Размер</th>
                        <th style="padding: 15px; text-align: left;">Дата создания</th>
                        <th style="padding: 15px; text-align: left;">Действия</th>
                    </tr>
                </thead>
                <tbody>
                    {backups_html if backups_html else '''
                    <tr>
                        <td colspan="4" style="padding: 20px; text-align: center; color: var(--gray);">
                            Бекапы не найдены
                        </td>
                    </tr>
                    '''}
                </tbody>
            </table>
        </div>
        
        <div style="margin-top: 30px; padding: 20px; background: rgba(16, 185, 129, 0.1); border-radius: 15px;">
            <h3><i class="fas fa-info-circle"></i> Информация</h3>
            <p>Бекапы автоматически создаются при достижении критического размера базы данных (20MB).</p>
            <p>Все бекапы автоматически отправляются в Telegram администраторам.</p>
        </div>
    </div>
    '''
    
    html = get_base_html("Управление бекапами", content, active_tab='/backups')
    return web.Response(text=html, content_type='text/html')
