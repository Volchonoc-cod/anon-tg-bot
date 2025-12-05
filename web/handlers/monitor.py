"""
Обработчик страницы мониторинга
"""
from aiohttp import web
from web.utils.templates import get_base_html
from web.utils.system import get_system_info
import psutil
import humanize

async def monitor_handler(request):
    """Страница мониторинга системы"""
    system_info = get_system_info()
    
    # Получаем процессы
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
    
    # Сетевая статистика
    net_io = psutil.net_io_counters()
    
    processes_html = ''
    for proc in processes[:15]:  # Показываем 15 процессов
        pid = proc.get('pid', 'N/A')
        name = proc.get('name', 'Unknown')[:25]
        cpu = proc.get('cpu_percent', 0)
        mem = proc.get('memory_percent', 0)
        
        processes_html += f'''
        <tr>
            <td><code>{pid}</code></td>
            <td>{name}</td>
            <td>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span>{cpu:.1f}%</span>
                    <div style="flex: 1; height: 6px; background: #e5e7eb; border-radius: 3px;">
                        <div style="height: 100%; width: {cpu}%; background: var(--primary); border-radius: 3px;"></div>
                    </div>
                </div>
            </td>
            <td>{mem:.1f}%</td>
        </tr>
        '''
    
    # HTML для случая, когда нет процессов
    no_processes_html = '''<tr><td colspan="4" style="padding: 20px; text-align: center; color: var(--gray);">Нет данных о процессах</td></tr>'''
    
    content = f'''
    <div class="glass-card">
        <h2 style="margin-bottom: 25px;">
            <i class="fas fa-chart-line"></i> Мониторинг системы
        </h2>
        
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px;">
            <div style="background: rgba(99, 102, 241, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                <div style="font-size: 2.5em; font-weight: 800; color: var(--primary);">
                    {system_info['cpu_percent']}%
                </div>
                <div style="color: var(--gray);">Загрузка CPU</div>
            </div>
            
            <div style="background: rgba(16, 185, 129, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                <div style="font-size: 2.5em; font-weight: 800; color: var(--success);">
                    {system_info['memory_percent']}%
                </div>
                <div style="color: var(--gray);">Использование памяти</div>
                <div style="font-size: 0.9em; margin-top: 5px;">
                    {system_info.get('memory_used', 'N/A')} / {system_info.get('memory_total', 'N/A')}
                </div>
            </div>
            
            <div style="background: rgba(245, 158, 11, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                <div style="font-size: 1.8em; font-weight: 800; color: var(--warning);">
                    {system_info['uptime']}
                </div>
                <div style="color: var(--gray);">Аптайм системы</div>
            </div>
            
            <div style="background: rgba(139, 92, 246, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                <div style="font-size: 2em; font-weight: 800; color: var(--secondary);">
                    {len(processes)}
                </div>
                <div style="color: var(--gray);">Активных процессов</div>
            </div>
        </div>
        
        <div style="margin-top: 30px;">
            <h3 style="margin-bottom: 15px;">
                <i class="fas fa-network-wired"></i> Сетевая статистика
            </h3>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                <div style="padding: 15px; background: white; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                    <div style="font-size: 1.2em; font-weight: 600; color: var(--primary);">
                        {humanize.naturalsize(net_io.bytes_sent)}
                    </div>
                    <div style="color: var(--gray); font-size: 0.9em;">Отправлено</div>
                </div>
                <div style="padding: 15px; background: white; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                    <div style="font-size: 1.2em; font-weight: 600; color: var(--success);">
                        {humanize.naturalsize(net_io.bytes_recv)}
                    </div>
                    <div style="color: var(--gray); font-size: 0.9em;">Получено</div>
                </div>
                <div style="padding: 15px; background: white; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                    <div style="font-size: 1.2em; font-weight: 600; color: var(--warning);">
                        {net_io.packets_sent}
                    </div>
                    <div style="color: var(--gray); font-size: 0.9em;">Пакеты отправлено</div>
                </div>
                <div style="padding: 15px; background: white; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                    <div style="font-size: 1.2em; font-weight: 600; color: var(--secondary);">
                        {net_io.packets_recv}
                    </div>
                    <div style="color: var(--gray); font-size: 0.9em;">Пакеты получено</div>
                </div>
            </div>
        </div>
        
        <div style="margin-top: 30px;">
            <h3 style="margin-bottom: 15px;">
                <i class="fas fa-tasks"></i> Активные процессы (Топ-15)
            </h3>
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: var(--primary); color: white;">
                            <th style="padding: 12px; text-align: left;">PID</th>
                            <th style="padding: 12px; text-align: left;">Имя процесса</th>
                            <th style="padding: 12px; text-align: left;">CPU</th>
                            <th style="padding: 12px; text-align: left;">Память</th>
                        </tr>
                    </thead>
                    <tbody>
                        {processes_html if processes_html else no_processes_html}
                    </tbody>
                </table>
            </div>
        </div>
        
        <div style="margin-top: 30px; padding: 20px; background: rgba(99, 102, 241, 0.05); border-radius: 15px;">
            <h3><i class="fas fa-info-circle"></i> Информация о системе</h3>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin-top: 15px;">
                <div>
                    <div style="font-weight: 600; color: var(--gray);">Платформа</div>
                    <div>{system_info.get('platform', 'N/A')}</div>
                </div>
                <div>
                    <div style="font-weight: 600; color: var(--gray);">Python версия</div>
                    <div>{system_info.get('python_version', 'N/A')}</div>
                </div>
                <div>
                    <div style="font-weight: 600; color: var(--gray);">CPU ядер</div>
                    <div>{psutil.cpu_count()} (логических)</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
    function refreshMonitor() {{
        fetch('/api/system_stats')
            .then(response => response.json())
            .then(data => {{
                document.getElementById('cpu-value').textContent = data.cpu_percent + '%';
                document.getElementById('memory-value').textContent = data.memory_percent + '%';
                document.getElementById('uptime-value').textContent = data.uptime;
            }});
    }}
    
    // Обновляем каждые 10 секунд
    setInterval(refreshMonitor, 10000);
    </script>
    '''
    
    html = get_base_html("Мониторинг системы", content, active_tab='/monitor')
    return web.Response(text=html, content_type='text/html')
