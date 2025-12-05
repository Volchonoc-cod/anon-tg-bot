"""
Обработчик страницы пользователей
"""
from aiohttp import web
from web.utils.templates import get_base_html
from web.utils.database import get_stats
from datetime import datetime, timedelta

async def users_handler(request):
    """Страница управления пользователями"""
    try:
        stats = get_stats()
        
        # HTML для случая, когда нет подключения к БД
        no_db_html = '''<tr><td colspan="5" style="padding: 30px; text-align: center; color: var(--gray);"><i class="fas fa-database" style="font-size: 2em; margin-bottom: 10px; display: block;"></i>Для просмотра пользователей необходимо подключение к базе данных</td></tr>'''
        
        content = f'''
        <div class="glass-card">
            <h2 style="margin-bottom: 25px;">
                <i class="fas fa-users"></i> Управление пользователями
            </h2>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px;">
                <div style="background: rgba(99, 102, 241, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                    <div style="font-size: 2.5em; font-weight: 800; color: var(--primary);">
                        {stats['total_users']}
                    </div>
                    <div style="color: var(--gray);">Всего пользователей</div>
                </div>
                
                <div style="background: rgba(16, 185, 129, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                    <div style="font-size: 2.5em; font-weight: 800; color: var(--success);">
                        {stats['active_users']}
                    </div>
                    <div style="color: var(--gray);">Активных</div>
                </div>
                
                <div style="background: rgba(245, 158, 11, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                    <div style="font-size: 2.5em; font-weight: 800; color: var(--warning);">
                        {stats['total_payments']}
                    </div>
                    <div style="color: var(--gray);">Премиум</div>
                </div>
                
                <div style="background: rgba(139, 92, 246, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                    <div style="font-size: 2.5em; font-weight: 800; color: var(--secondary);">
                        0
                    </div>
                    <div style="color: var(--gray);">Новых сегодня</div>
                </div>
            </div>
            
            <div style="margin-top: 30px;">
                <h3 style="margin-bottom: 15px;">
                    <i class="fas fa-search"></i> Поиск пользователей
                </h3>
                <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                    <input type="text" id="userSearch" placeholder="Поиск по ID, имени или username..." 
                           style="flex: 1; padding: 12px; border: 2px solid var(--gray-light); border-radius: 10px;">
                    <button class="btn" onclick="searchUsers()">
                        <i class="fas fa-search"></i> Найти
                    </button>
                </div>
                
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background: var(--primary); color: white;">
                                <th style="padding: 12px; text-align: left;">ID</th>
                                <th style="padding: 12px; text-align: left;">Имя</th>
                                <th style="padding: 12px; text-align: left;">Username</th>
                                <th style="padding: 12px; text-align: left;">Дата регистрации</th>
                                <th style="padding: 12px; text-align: left;">Статус</th>
                            </tr>
                        </thead>
                        <tbody id="usersTable">
                            {no_db_html}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div style="margin-top: 30px; padding: 20px; background: rgba(99, 102, 241, 0.05); border-radius: 15px;">
                <h3><i class="fas fa-chart-bar"></i> Аналитика роста</h3>
                <div style="display: flex; align-items: flex-end; gap: 10px; height: 150px; margin-top: 20px;">
                    <div style="flex: 1; display: flex; flex-direction: column; align-items: center;">
                        <div style="background: var(--primary); width: 30px; height: 120px; border-radius: 5px;"></div>
                        <div style="margin-top: 10px; font-size: 0.9em;">Пн</div>
                    </div>
                    <div style="flex: 1; display: flex; flex-direction: column; align-items: center;">
                        <div style="background: var(--primary); width: 30px; height: 80px; border-radius: 5px;"></div>
                        <div style="margin-top: 10px; font-size: 0.9em;">Вт</div>
                    </div>
                    <div style="flex: 1; display: flex; flex-direction: column; align-items: center;">
                        <div style="background: var(--primary); width: 30px; height: 150px; border-radius: 5px;"></div>
                        <div style="margin-top: 10px; font-size: 0.9em;">Ср</div>
                    </div>
                    <div style="flex: 1; display: flex; flex-direction: column; align-items: center;">
                        <div style="background: var(--primary); width: 30px; height: 60px; border-radius: 5px;"></div>
                        <div style="margin-top: 10px; font-size: 0.9em;">Чт</div>
                    </div>
                    <div style="flex: 1; display: flex; flex-direction: column; align-items: center;">
                        <div style="background: var(--primary); width: 30px; height: 180px; border-radius: 5px;"></div>
                        <div style="margin-top: 10px; font-size: 0.9em;">Пт</div>
                    </div>
                    <div style="flex: 1; display: flex; flex-direction: column; align-items: center;">
                        <div style="background: var(--primary); width: 30px; height: 100px; border-radius: 5px;"></div>
                        <div style="margin-top: 10px; font-size: 0.9em;">Сб</div>
                    </div>
                    <div style="flex: 1; display: flex; flex-direction: column; align-items: center;">
                        <div style="background: var(--primary); width: 30px; height: 140px; border-radius: 5px;"></div>
                        <div style="margin-top: 10px; font-size: 0.9em;">Вс</div>
                    </div>
                </div>
                <div style="text-align: center; margin-top: 15px; color: var(--gray);">
                    Динамика регистраций за неделю
                </div>
            </div>
        </div>
        
        <script>
        function searchUsers() {{
            const search = document.getElementById('userSearch').value.toLowerCase();
            alert('Поиск: ' + search + '\\n\\nФункция поиска будет реализована после подключения реальной БД');
        }}
        
        function loadUsers() {{
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {{
                    document.getElementById('total-users').textContent = data.total_users;
                    document.getElementById('active-users').textContent = data.active_users;
                }});
        }}
        
        // Загружаем статистику при загрузке страницы
        document.addEventListener('DOMContentLoaded', loadUsers);
        </script>
        '''
        
        html = get_base_html("Управление пользователями", content, active_tab='/users')
        return web.Response(text=html, content_type='text/html')
        
    except Exception as e:
        return web.Response(text=f"Ошибка: {e}", content_type='text/html')
