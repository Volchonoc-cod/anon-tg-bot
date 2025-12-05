"""
HTML шаблоны и утилиты для генерации страниц
"""
from datetime import datetime
import humanize
import psutil
import os

def get_common_css():
    """Возвращает общие CSS стили"""
    return """
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --secondary: #8b5cf6;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --dark: #1f2937;
            --light: #f9fafb;
            --gray: #6b7280;
            --gray-light: #e5e7eb;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: var(--dark);
            line-height: 1.6;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .glass-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            margin-bottom: 30px;
        }
        
        .header {
            text-align: center;
            margin-bottom: 40px;
            padding: 40px 20px;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            border-radius: 20px;
            color: white;
        }
        
        .nav-tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }
        
        .nav-tab {
            padding: 15px 25px;
            background: rgba(255, 255, 255, 0.9);
            border-radius: 12px;
            text-decoration: none;
            color: var(--dark);
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        .nav-tab:hover {
            background: white;
            border-color: var(--primary);
            transform: translateY(-2px);
        }
        
        .nav-tab.active {
            background: var(--primary);
            color: white;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            text-align: center;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        }
        
        .stat-value {
            font-size: 2.2em;
            font-weight: 800;
            color: var(--dark);
            margin-bottom: 5px;
        }
        
        .stat-label {
            font-size: 0.9em;
            color: var(--gray);
            text-transform: uppercase;
        }
        
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            padding: 12px 25px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 12px;
            font-weight: 600;
            text-decoration: none;
            cursor: pointer;
        }
        
        .btn:hover {
            background: var(--primary-dark);
            transform: translateY(-2px);
        }
        
        .footer {
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: white;
            opacity: 0.8;
        }
        
        @media (max-width: 768px) {
            .container { padding: 10px; }
            .header h1 { font-size: 2em; }
            .stats-grid { grid-template-columns: 1fr; }
        }
    </style>
    """

def get_header(title: str, active_tab: str = ''):
    """Генерирует заголовок страницы с навигацией"""
    tabs = [
        {'url': '/', 'icon': 'fa-tachometer-alt', 'label': 'Дашборд'},
        {'url': '/backups', 'icon': 'fa-database', 'label': 'Бекапы'},
        {'url': '/monitor', 'icon': 'fa-chart-line', 'label': 'Мониторинг'},
        {'url': '/users', 'icon': 'fa-users', 'label': 'Пользователи'},
        {'url': '/settings', 'icon': 'fa-cog', 'label': 'Настройки'},
        {'url': '/logs', 'icon': 'fa-terminal', 'label': 'Логи'},
    ]
    
    nav_html = '<div class="nav-tabs">'
    for tab in tabs:
        is_active = 'active' if tab['url'] == active_tab or (tab['url'] == '/' and active_tab == '') else ''
        nav_html += f'''
        <a href="{tab['url']}" class="nav-tab {is_active}">
            <i class="fas {tab['icon']}"></i> {tab['label']}
        </a>
        '''
    nav_html += '</div>'
    
    return f'''
    <div class="container">
        <div class="header">
            <h1><i class="fas fa-robot"></i> {title}</h1>
            <p>Панель управления ботом для анонимных вопросов</p>
        </div>
        {nav_html}
    '''

def get_footer():
    """Генерирует футер"""
    return '''
    <div class="footer">
        <p>© 2024 ShadowTalk Bot • Версия 2.0 • 
        <a href="https://t.me/ShadowTalkBot" style="color: white; text-decoration: underline;">@ShadowTalkBot</a></p>
    </div>
    </div>
    '''

def get_base_html(title: str, content: str, active_tab: str = ''):
    """Генерирует базовый HTML документ"""
    return f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} • ShadowTalk</title>
        {get_common_css()}
    </head>
    <body>
        {get_header(title, active_tab)}
        {content}
        {get_footer()}
    </body>
    </html>
    '''
