"""
Обработчик страницы логов
"""
from aiohttp import web
from web.utils.templates import get_base_html
import os
from datetime import datetime

async def logs_handler(request):
    """Страница просмотра логов"""
    log_files = []
    logs_dir = 'logs'
    
    if os.path.exists(logs_dir):
        for file in os.listdir(logs_dir):
            if file.endswith('.log'):
                filepath = os.path.join(logs_dir, file)
                stat = os.stat(filepath)
                size_kb = stat.st_size / 1024
                log_files.append({
                    'name': file,
                    'size': f"{size_kb:.1f} KB",
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%d.%m.%Y %H:%M')
                })
    
    # Читаем последние 50 строк из основного лога
    log_content = ""
    main_log = 'bot.log'
    if os.path.exists(main_log):
        try:
            with open(main_log, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                log_content = ''.join(lines[-50:])  # Последние 50 строк
        except:
            log_content = "Не удалось прочитать файл лога"
    else:
        log_content = "Файл лога не найден"
    
    log_files_html = ''
    for log in sorted(log_files, key=lambda x: x['modified'], reverse=True):
        log_files_html += f'''
        <tr>
            <td>{log['name']}</td>
            <td>{log['size']}</td>
            <td>{log['modified']}</td>
            <td>
                <button class="btn" style="padding: 6px 12px;" onclick="viewLog('{log['name']}')">
                    <i class="fas fa-eye"></i>
                </button>
            </td>
        </tr>
        '''
    
    content = f'''
    <div class="glass-card">
        <h2 style="margin-bottom: 25px;">
            <i class="fas fa-terminal"></i> Просмотр логов
        </h2>
        
        <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 30px; margin-bottom: 30px;">
            <div>
                <h3 style="margin-bottom: 15px;">
                    <i class="fas fa-file-alt"></i> Основной лог (bot.log)
                </h3>
                <div style="background: #1f2937; color: #00ff00; padding: 20px; border-radius: 10px; font-family: monospace; font-size: 0.9em; height: 400px; overflow-y: auto;">
                    {log_content or 'Логи отсутствуют'}
                </div>
                <div style="margin-top: 10px; display: flex; gap: 10px;">
                    <button class="btn" onclick="refreshLogs()">
                        <i class="fas fa-sync-alt"></i> Обновить
                    </button>
                    <button class="btn btn-secondary" onclick="clearLogs()">
                        <i class="fas fa-trash"></i> Очистить логи
                    </button>
                    <button class="btn" onclick="downloadLogs()">
                        <i class="fas fa-download"></i> Скачать
                    </button>
                </div>
            </div>
            
            <div>
                <h3 style="margin-bottom: 15px;">
                    <i class="fas fa-folder"></i> Файлы логов
                </h3>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background: var(--primary); color: white;">
                                <th style="padding: 10px; text-align: left;">Имя файла</th>
                                <th style="padding: 10px; text-align: left;">Размер</th>
                                <th style="padding: 10px; text-align: left;">Изменен</th>
                                <th style="padding: 10px; text-align: left;">Действия</th>
                            </tr>
                        </thead>
                        <tbody>
                            {log_files_html if log_files_html else '''
                            <tr>
                                <td colspan="4" style="padding: 15px; text-align: center; color: var(--gray);">
                                    Файлы логов не найдены
                                </td>
                            </tr>
                            '''}
                        </tbody>
                    </table>
                </div>
                
                <div style="margin-top: 20px; padding: 15px; background: rgba(99, 102, 241, 0.1); border-radius: 10px;">
                    <h4><i class="fas fa-info-circle"></i> Уровни логирования</h4>
                    <div style="display: grid; gap: 5px; margin-top: 10px;">
                        <div><span style="color: #10b981;">INFO</span> - Информационные сообщения</div>
                        <div><span style="color: #f59e0b;">WARNING</span> - Предупреждения</div>
                        <div><span style="color: #ef4444;">ERROR</span> - Ошибки</div>
                        <div><span style="color: #dc2626;">CRITICAL</span> - Критические ошибки</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div style="margin-top: 30px;">
            <h3 style="margin-bottom: 15px;">
                <i class="fas fa-filter"></i> Фильтры логов
            </h3>
            <div style="display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 20px;">
                <select id="logLevel" style="padding: 10px; border: 2px solid var(--gray-light); border-radius: 8px;">
                    <option value="all">Все уровни</option>
                    <option value="info">Только INFO</option>
                    <option value="warning">Только WARNING</option>
                    <option value="error">Только ERROR</option>
                </select>
                
                <input type="text" id="logSearch" placeholder="Поиск по тексту..." 
                       style="padding: 10px; border: 2px solid var(--gray-light); border-radius: 8px; flex: 1;">
                
                <select id="logDate" style="padding: 10px; border: 2px solid var(--gray-light); border-radius: 8px;">
                    <option value="today">Сегодня</option>
                    <option value="yesterday">Вчера</option>
                    <option value="week">Неделя</option>
                    <option value="month">Месяц</option>
                    <option value="all">Все время</option>
                </select>
                
                <button class="btn" onclick="applyFilters()">
                    <i class="fas fa-filter"></i> Применить
                </button>
            </div>
        </div>
        
        <div style="margin-top: 30px; padding: 20px; background: rgba(16, 185, 129, 0.1); border-radius: 15px;">
            <h3><i class="fas fa-lightbulb"></i> Рекомендации</h3>
            <ul style="margin-top: 10px; padding-left: 20px;">
                <li>Регулярно очищайте логи для экономии места на диске</li>
                <li>Используйте фильтры для поиска конкретных ошибок</li>
                <li>Все критические ошибки автоматически отправляются администраторам</li>
                <li>Рекомендуется хранить логи не более 30 дней</li>
            </ul>
        </div>
    </div>
    
    <script>
    function refreshLogs() {{
        location.reload();
    }}
    
    function clearLogs() {{
        if (confirm('Вы уверены? Это удалит все логи и их нельзя будет восстановить.')) {{
            fetch('/api/clear_logs')
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        alert('Логи очищены!');
                        refreshLogs();
                    }}
                }});
        }}
    }}
    
    function downloadLogs() {{
        alert('Скачивание логов...\\n\\nФункция будет реализована в следующей версии.');
    }}
    
    function viewLog(filename) {{
        alert('Просмотр лога: ' + filename + '\\n\\nФункция будет реализована в следующей версии.');
    }}
    
    function applyFilters() {{
        const level = document.getElementById('logLevel').value;
        const search = document.getElementById('logSearch').value;
        const date = document.getElementById('logDate').value;
        alert(`Применены фильтры:\\nУровень: ${level}\\nПоиск: ${search}\\nПериод: ${date}`);
    }}
    </script>
    '''
    
    html = get_base_html("Просмотр логов", content, active_tab='/logs')
    return web.Response(text=html, content_type='text/html')
