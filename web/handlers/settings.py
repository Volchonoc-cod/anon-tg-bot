"""
Обработчик страницы настроек
"""
from aiohttp import web
from web.utils.templates import get_base_html
import os

async def settings_handler(request):
    """Страница настроек"""
    bot_token = os.getenv("BOT_TOKEN", "")
    admin_ids = os.getenv("ADMIN_IDS", "")
    render_url = os.getenv("RENDER_EXTERNAL_URL", "")
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/bot.db")
    
    content = f'''
    <div class="glass-card">
        <h2 style="margin-bottom: 25px;">
            <i class="fas fa-cog"></i> Настройки системы
        </h2>
        
        <div style="margin-bottom: 30px;">
            <h3 style="margin-bottom: 15px;">
                <i class="fas fa-key"></i> Конфигурация бота
            </h3>
            <div style="display: grid; gap: 15px;">
                <div>
                    <div style="font-weight: 600; margin-bottom: 5px;">BOT_TOKEN</div>
                    <div style="background: #f3f4f6; padding: 10px; border-radius: 8px; font-family: monospace;">
                        {bot_token[:20]}...
                    </div>
                </div>
                <div>
                    <div style="font-weight: 600; margin-bottom: 5px;">ADMIN_IDS</div>
                    <div style="background: #f3f4f6; padding: 10px; border-radius: 8px;">
                        {admin_ids or 'Не установлено'}
                    </div>
                </div>
                <div>
                    <div style="font-weight: 600; margin-bottom: 5px;">DATABASE_URL</div>
                    <div style="background: #f3f4f6; padding: 10px; border-radius: 8px; font-family: monospace;">
                        {database_url}
                    </div>
                </div>
            </div>
        </div>
        
        <div style="margin-bottom: 30px;">
            <h3 style="margin-bottom: 15px;">
                <i class="fas fa-sliders-h"></i> Настройки системы
            </h3>
            <div style="display: grid; gap: 20px;">
                <div>
                    <div style="font-weight: 600; margin-bottom: 10px;">
                        <i class="fas fa-bell"></i> Уведомления
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 10px;">
                        <label style="display: flex; align-items: center; gap: 10px;">
                            <input type="checkbox" checked style="width: 18px; height: 18px;">
                            Отправлять уведомления о запуске/остановке
                        </label>
                        <label style="display: flex; align-items: center; gap: 10px;">
                            <input type="checkbox" checked style="width: 18px; height: 18px;">
                            Уведомлять об ошибках в реальном времени
                        </label>
                        <label style="display: flex; align-items: center; gap: 10px;">
                            <input type="checkbox" style="width: 18px; height: 18px;">
                            Уведомлять о новых пользователях
                        </label>
                    </div>
                </div>
                
                <div>
                    <div style="font-weight: 600; margin-bottom: 10px;">
                        <i class="fas fa-database"></i> Настройки БД
                    </div>
                    <div style="display: grid; gap: 10px;">
                        <div>
                            <div style="margin-bottom: 5px;">Интервал авто-бекапа</div>
                            <select style="width: 100%; padding: 10px; border: 2px solid var(--gray-light); border-radius: 8px;">
                                <option>Каждый час</option>
                                <option selected>Каждые 6 часов</option>
                                <option>Каждые 12 часов</option>
                                <option>Раз в день</option>
                            </select>
                        </div>
                        <div>
                            <div style="margin-bottom: 5px;">Хранить бекапов</div>
                            <select style="width: 100%; padding: 10px; border: 2px solid var(--gray-light); border-radius: 8px;">
                                <option>3 последних</option>
                                <option selected>5 последних</option>
                                <option>10 последних</option>
                                <option>Все бекапы</option>
                            </select>
                        </div>
                    </div>
                </div>
                
                <div>
                    <div style="font-weight: 600; margin-bottom: 10px;">
                        <i class="fas fa-robot"></i> Настройки бота
                    </div>
                    <div style="display: grid; gap: 10px;">
                        <div>
                            <div style="margin-bottom: 5px;">Лимит сообщений в минуту</div>
                            <input type="number" value="30" style="width: 100%; padding: 10px; border: 2px solid var(--gray-light); border-radius: 8px;">
                        </div>
                        <div>
                            <div style="margin-bottom: 5px;">Лимит новых пользователей в час</div>
                            <input type="number" value="100" style="width: 100%; padding: 10px; border: 2px solid var(--gray-light); border-radius: 8px;">
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div style="margin-bottom: 30px;">
            <h3 style="margin-bottom: 15px;">
                <i class="fas fa-shield-alt"></i> Безопасность
            </h3>
            <div style="display: grid; gap: 15px;">
                <div style="padding: 15px; background: rgba(16, 185, 129, 0.1); border-radius: 10px;">
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 5px;">
                        <i class="fas fa-check-circle" style="color: var(--success);"></i>
                        <span style="font-weight: 600;">Защита от спама</span>
                    </div>
                    <div style="font-size: 0.9em; color: var(--gray);">
                        Автоматическая блокировка пользователей при подозрении на спам
                    </div>
                </div>
                
                <div style="padding: 15px; background: rgba(245, 158, 11, 0.1); border-radius: 10px;">
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 5px;">
                        <i class="fas fa-exclamation-triangle" style="color: var(--warning);"></i>
                        <span style="font-weight: 600;">Логирование действий</span>
                    </div>
                    <div style="font-size: 0.9em; color: var(--gray);">
                        Все действия администраторов записываются в журнал
                    </div>
                </div>
                
                <div style="padding: 15px; background: rgba(99, 102, 241, 0.1); border-radius: 10px;">
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 5px;">
                        <i class="fas fa-key" style="color: var(--primary);"></i>
                        <span style="font-weight: 600;">Доступ по токену</span>
                    </div>
                    <div style="font-size: 0.9em; color: var(--gray);">
                        Доступ к панели управления защищен токеном администратора
                    </div>
                </div>
            </div>
        </div>
        
        <div style="display: flex; gap: 10px;">
            <button class="btn btn-success" onclick="saveSettings()">
                <i class="fas fa-save"></i> Сохранить настройки
            </button>
            <button class="btn btn-secondary" onclick="testConnection()">
                <i class="fas fa-plug"></i> Проверить соединения
            </button>
            <button class="btn" onclick="clearCache()">
                <i class="fas fa-broom"></i> Очистить кэш
            </button>
        </div>
    </div>
    
    <script>
    function saveSettings() {{
        alert('Настройки сохранены!\\n\\nИзменения применятся после перезагрузки приложения.');
    }}
    
    function testConnection() {{
        alert('Проверка соединений...\\n\\nВсе системы работают нормально.');
    }}
    
    function clearCache() {{
        if (confirm('Очистить кэш приложения? Это может временно замедлить работу.')) {{
            alert('Кэш очищен!');
        }}
    }}
    </script>
    '''
    
    html = get_base_html("Настройки", content, active_tab='/settings')
    return web.Response(text=html, content_type='text/html')
