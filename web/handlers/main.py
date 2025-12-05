"""
Обработчик главной страницы
"""
from aiohttp import web
from web.utils.templates import get_base_html
from web.utils.database import get_stats
from web.utils.system import get_system_info
from datetime import datetime

async def index_handler(request):
    """Главная страница - дашборд"""
    try:
        # Получаем статистику
        stats = get_stats()
        system_info = get_system_info()
        
        content = f'''
        <div class="glass-card">
            <h2 style="margin-bottom: 25px;">
                <i class="fas fa-chart-bar"></i> Основная статистика
            </h2>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div style="font-size: 2.5em; margin-bottom: 10px; color: var(--primary);">
                        <i class="fas fa-users"></i>
                    </div>
                    <div class="stat-value">{stats['total_users']}</div>
                    <div class="stat-label">Всего пользователей</div>
                </div>
                
                <div class="stat-card">
                    <div style="font-size: 2.5em; margin-bottom: 10px; color: var(--success);">
                        <i class="fas fa-envelope"></i>
                    </div>
                    <div class="stat-value">{stats['total_messages']}</div>
                    <div class="stat-label">Всего сообщений</div>
                </div>
                
                <div class="stat-card">
                    <div style="font-size: 2.5em; margin-bottom: 10px; color: var(--secondary);">
                        <i class="fas fa-user-check"></i>
                    </div>
                    <div class="stat-value">{stats['active_users']}</div>
                    <div class="stat-label">Активных пользователей</div>
                </div>
                
                <div class="stat-card">
                    <div style="font-size: 2.5em; margin-bottom: 10px; color: var(--warning);">
                        <i class="fas fa-credit-card"></i>
                    </div>
                    <div class="stat-value">{stats['total_payments']}</div>
                    <div class="stat-label">Успешных платежей</div>
                </div>
            </div>
            
            <div style="margin-top: 40px;">
                <h3><i class="fas fa-server"></i> Системная информация</h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-top: 20px;">
                    <div style="background: rgba(99, 102, 241, 0.1); padding: 15px; border-radius: 10px;">
                        <div style="font-size: 1.2em; font-weight: 600;">CPU</div>
                        <div style="font-size: 1.5em; font-weight: 800;">{system_info['cpu_percent']}%</div>
                    </div>
                    <div style="background: rgba(16, 185, 129, 0.1); padding: 15px; border-radius: 10px;">
                        <div style="font-size: 1.2em; font-weight: 600;">Память</div>
                        <div style="font-size: 1.5em; font-weight: 800;">{system_info['memory_percent']}%</div>
                    </div>
                    <div style="background: rgba(245, 158, 11, 0.1); padding: 15px; border-radius: 10px;">
                        <div style="font-size: 1.2em; font-weight: 600;">Аптайм</div>
                        <div style="font-size: 1.2em; font-weight: 600;">{system_info['uptime']}</div>
                    </div>
                </div>
            </div>
            
            <div style="margin-top: 30px; padding: 20px; background: rgba(99, 102, 241, 0.05); border-radius: 15px;">
                <h3><i class="fas fa-bolt"></i> Быстрые действия</h3>
                <div style="display: flex; gap: 10px; margin-top: 15px; flex-wrap: wrap;">
                    <a href="/api/create_backup" class="btn btn-success">
                        <i class="fas fa-plus"></i> Создать бекап
                    </a>
                    <a href="/monitor" class="btn">
                        <i class="fas fa-chart-line"></i> Мониторинг
                    </a>
                    <a href="/users" class="btn btn-secondary">
                        <i class="fas fa-users"></i> Пользователи
                    </a>
                </div>
            </div>
        </div>
        '''
        
        html = get_base_html("Панель управления", content, active_tab='/')
        return web.Response(text=html, content_type='text/html')
        
    except Exception as e:
        return web.Response(text=f"Ошибка: {e}", content_type='text/html')
