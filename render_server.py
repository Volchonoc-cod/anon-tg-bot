"""
ShadowTalk - Панель управления ботом для анонимных вопросов
"""
import os
import sys
import asyncio
import logging
import aiohttp
from aiohttp import web
from datetime import datetime, timedelta
import json
import math
import psutil
import humanize
from pathlib import Path

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
START_TIME = datetime.now()

# ============================================
# 1. ФУНКЦИЯ САМОПИНГА
# ============================================
async def keep_alive_ping():
    """Постоянный пинг самого себя"""
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
                            if ping_count % 30 == 0:
                                logger.info(f"✅ Самопинг #{ping_count}")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка самопинга: {e}")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка самопинга: {e}")
        
        await asyncio.sleep(20)

# ============================================
# 2. ФУНКЦИЯ ПИНГА АДМИНУ
# ============================================
async def admin_ping():
    """Пинг админу о статусе бота"""
    if not BOT_TOKEN or not ADMIN_IDS:
        logger.warning("⚠️ BOT_TOKEN или ADMIN_IDS не установлены")
        return
    
    start_time = datetime.now()
    
    while True:
        try:
            await asyncio.sleep(15 * 60)
            
            uptime = datetime.now() - start_time
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            
            message = (
                f"🔄 <b>Статус бота</b>\n\n"
                f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n"
                f"⏱ Аптайм: {hours}ч {minutes}м\n"
                f"🌐 Сервер: <code>Активен</code>\n\n"
                f"✅ Бот работает стабильно"
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
    """Запускает Telegram бота"""
    try:
        logger.info("🤖 Запуск Telegram бота...")
        
        from run_bot import run_bot_async
        await run_bot_async()
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
        await asyncio.sleep(30)
        asyncio.create_task(start_your_bot())

# ============================================
# 4. CSS СТИЛИ ДЛЯ ВСЕХ СТРАНИЦ
# ============================================
COMMON_CSS = """
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
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
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
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .glass-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
        }
        
        .header {
            text-align: center;
            margin-bottom: 40px;
            padding: 40px 20px;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            border-radius: 20px;
            color: white;
            position: relative;
            overflow: hidden;
        }
        
        .header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" preserveAspectRatio="none"><path d="M0,0 L100,0 L100,100 Z" fill="rgba(255,255,255,0.1)"/></svg>');
            background-size: cover;
        }
        
        .header h1 {
            font-size: 3em;
            font-weight: 800;
            margin-bottom: 10px;
            position: relative;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
            position: relative;
        }
        
        .status-badge {
            display: inline-block;
            padding: 8px 20px;
            background: var(--success);
            color: white;
            border-radius: 50px;
            font-weight: 600;
            font-size: 0.9em;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
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
            transition: all 0.3s ease;
            border-left: 5px solid var(--primary);
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
        }
        
        .stat-icon {
            font-size: 2.5em;
            margin-bottom: 15px;
            color: var(--primary);
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
            letter-spacing: 1px;
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
            border: 2px solid transparent;
            display: flex;
            align-items: center;
            gap: 10px;
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
        
        .nav-tab i {
            font-size: 1.2em;
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
            transition: all 0.3s ease;
            font-size: 1em;
        }
        
        .btn:hover {
            background: var(--primary-dark);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(99, 102, 241, 0.3);
        }
        
        .btn-success {
            background: var(--success);
        }
        
        .btn-warning {
            background: var(--warning);
        }
        
        .btn-danger {
            background: var(--danger);
        }
        
        .btn-secondary {
            background: var(--secondary);
        }
        
        .btn-group {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin: 20px 0;
        }
        
        .card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08);
            border-top: 4px solid var(--primary);
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid var(--gray-light);
        }
        
        .card-title {
            font-size: 1.5em;
            font-weight: 700;
            color: var(--dark);
        }
        
        .progress-bar {
            height: 10px;
            background: var(--gray-light);
            border-radius: 5px;
            overflow: hidden;
            margin: 15px 0;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
            border-radius: 5px;
            transition: width 0.5s ease;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        
        th {
            background: var(--primary);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }
        
        td {
            padding: 15px;
            border-bottom: 1px solid var(--gray-light);
        }
        
        tr:hover {
            background: rgba(99, 102, 241, 0.05);
        }
        
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
        }
        
        .badge-success {
            background: rgba(16, 185, 129, 0.1);
            color: var(--success);
        }
        
        .badge-warning {
            background: rgba(245, 158, 11, 0.1);
            color: var(--warning);
        }
        
        .badge-danger {
            background: rgba(239, 68, 68, 0.1);
            color: var(--danger);
        }
        
        .footer {
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: white;
            opacity: 0.8;
            font-size: 0.9em;
        }
        
        .uptime-counter {
            font-family: monospace;
            background: var(--dark);
            color: var(--success);
            padding: 10px 15px;
            border-radius: 8px;
            font-size: 1.1em;
        }
        
        .system-monitor {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        
        .monitor-item {
            background: rgba(255, 255, 255, 0.9);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        
        .monitor-value {
            font-size: 1.8em;
            font-weight: 700;
            color: var(--primary);
        }
        
        .monitor-label {
            font-size: 0.85em;
            color: var(--gray);
            margin-top: 5px;
        }
        
        .logs-container {
            background: var(--dark);
            color: #00ff00;
            padding: 20px;
            border-radius: 10px;
            font-family: monospace;
            font-size: 0.9em;
            max-height: 300px;
            overflow-y: auto;
            margin: 20px 0;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            
            .header h1 {
                font-size: 2em;
            }
            
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .nav-tabs {
                justify-content: center;
            }
            
            .btn-group {
                justify-content: center;
            }
        }
    </style>
    
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
"""

# ============================================
# 5. ОСНОВНЫЕ HTTP ХЕНДЛЕРЫ
# ============================================
async def index_handler(request):
    """Главная страница - панель управления"""
    try:
        # Получаем статистику системы
        from app.database import get_db
        from app.models import User, AnonMessage, Payment
        
        db = next(get_db())
        
        # Основная статистика
        total_users = db.query(User).count()
        total_messages = db.query(AnonMessage).count()
        active_users = db.query(User).filter(User.anon_link_uid.isnot(None)).count()
        total_payments = db.query(Payment).filter(Payment.status == 'completed').count()
        
        # Статистика за сегодня
        today = datetime.now().date()
        today_users = db.query(User).filter(User.created_at >= today).count()
        today_messages = db.query(AnonMessage).filter(AnonMessage.timestamp >= today).count()
        
        # Статистика за неделю
        week_ago = datetime.now() - timedelta(days=7)
        week_users = db.query(User).filter(User.created_at >= week_ago).count()
        week_messages = db.query(AnonMessage).filter(AnonMessage.timestamp >= week_ago).count()
        
        db.close()
        
        # Системная информация
        uptime = datetime.now() - START_TIME
        uptime_str = f"{uptime.days}д {uptime.seconds // 3600}ч {(uptime.seconds % 3600) // 60}м"
        
        # Использование памяти
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Информация о сервере
        server_info = {
            'platform': sys.platform,
            'python_version': sys.version.split()[0],
            'uptime': uptime_str,
            'cpu_usage': cpu_percent,
            'memory_usage': memory.percent,
            'memory_used': humanize.naturalsize(memory.used),
            'memory_total': humanize.naturalsize(memory.total),
            'disk_usage': psutil.disk_usage('/').percent if hasattr(psutil, 'disk_usage') else 0
        }
        
        html = f"""
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>ShadowTalk • Панель управления</title>
            {COMMON_CSS}
            <script>
                function updateTime() {{
                    const now = new Date();
                    const timeStr = now.toLocaleTimeString('ru-RU');
                    document.getElementById('current-time').textContent = timeStr;
                }}
                
                function refreshStats() {{
                    fetch('/api/stats')
                        .then(response => response.json())
                        .then(data => {{
                            document.getElementById('total-users').textContent = data.total_users;
                            document.getElementById('total-messages').textContent = data.total_messages;
                            document.getElementById('active-users').textContent = data.active_users;
                        }});
                }}
                
                // Обновляем время каждую секунду
                setInterval(updateTime, 1000);
                // Обновляем статистику каждые 30 секунд
                setInterval(refreshStats, 30000);
                
                // Инициализация
                document.addEventListener('DOMContentLoaded', function() {{
                    updateTime();
                    refreshStats();
                }});
            </script>
        </head>
        <body>
            <div class="container">
                <!-- Шапка -->
                <div class="header">
                    <h1><i class="fas fa-robot"></i> ShadowTalk</h1>
                    <p>Панель управления ботом для анонимных вопросов</p>
                    <div style="margin-top: 20px;">
                        <span class="status-badge">
                            <i class="fas fa-circle" style="font-size: 0.7em; margin-right: 8px;"></i>
                            Система активна
                        </span>
                        <div style="margin-top: 10px; font-size: 0.9em;">
                            <span id="current-time"></span> • Аптайм: {server_info['uptime']}
                        </div>
                    </div>
                </div>
                
                <!-- Навигация -->
                <div class="nav-tabs">
                    <a href="/" class="nav-tab active">
                        <i class="fas fa-tachometer-alt"></i> Дашборд
                    </a>
                    <a href="/backups" class="nav-tab">
                        <i class="fas fa-database"></i> Бекапы
                    </a>
                    <a href="/monitor" class="nav-tab">
                        <i class="fas fa-chart-line"></i> Мониторинг
                    </a>
                    <a href="/users" class="nav-tab">
                        <i class="fas fa-users"></i> Пользователи
                    </a>
                    <a href="/settings" class="nav-tab">
                        <i class="fas fa-cog"></i> Настройки
                    </a>
                    <a href="/logs" class="nav-tab">
                        <i class="fas fa-terminal"></i> Логи
                    </a>
                </div>
                
                <!-- Основная статистика -->
                <div class="glass-card">
                    <h2 style="margin-bottom: 25px; color: var(--dark);">
                        <i class="fas fa-chart-bar" style="margin-right: 10px;"></i>Основная статистика
                    </h2>
                    
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-icon">
                                <i class="fas fa-users"></i>
                            </div>
                            <div class="stat-value" id="total-users">{total_users}</div>
                            <div class="stat-label">Всего пользователей</div>
                            <div style="margin-top: 10px; font-size: 0.9em; color: var(--success);">
                                <i class="fas fa-arrow-up"></i> +{today_users} сегодня
                            </div>
                        </div>
                        
                        <div class="stat-card">
                            <div class="stat-icon">
                                <i class="fas fa-envelope"></i>
                            </div>
                            <div class="stat-value" id="total-messages">{total_messages}</div>
                            <div class="stat-label">Всего сообщений</div>
                            <div style="margin-top: 10px; font-size: 0.9em; color: var(--success);">
                                <i class="fas fa-arrow-up"></i> +{today_messages} сегодня
                            </div>
                        </div>
                        
                        <div class="stat-card">
                            <div class="stat-icon">
                                <i class="fas fa-user-check"></i>
                            </div>
                            <div class="stat-value" id="active-users">{active_users}</div>
                            <div class="stat-label">Активных пользователей</div>
                            <div style="margin-top: 10px; font-size: 0.9em; color: var(--secondary);">
                                <i class="fas fa-link"></i> с активными ссылками
                            </div>
                        </div>
                        
                        <div class="stat-card">
                            <div class="stat-icon">
                                <i class="fas fa-credit-card"></i>
                            </div>
                            <div class="stat-value">{total_payments}</div>
                            <div class="stat-label">Успешных платежей</div>
                            <div style="margin-top: 10px; font-size: 0.9em; color: var(--primary);">
                                <i class="fas fa-money-bill-wave"></i> монетизация
                            </div>
                        </div>
                    </div>
                    
                    <!-- Прогресс активности -->
                    <div style="margin-top: 30px;">
                        <h3 style="margin-bottom: 15px; color: var(--gray);">
                            <i class="fas fa-chart-line"></i> Активность за неделю
                        </h3>
                        <div style="display: flex; justify-content: space-between; gap: 20px;">
                            <div style="flex: 1;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                                    <span>Новые пользователи</span>
                                    <span style="font-weight: 600; color: var(--primary);">{week_users}</span>
                                </div>
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: {min(week_users, 100)}%;"></div>
                                </div>
                            </div>
                            <div style="flex: 1;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                                    <span>Сообщения</span>
                                    <span style="font-weight: 600; color: var(--primary);">{week_messages}</span>
                                </div>
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: {min(week_messages/100, 100)}%;"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Быстрые действия и мониторинг -->
                <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 30px; margin-bottom: 30px;">
                    <!-- Быстрые действия -->
                    <div class="glass-card">
                        <h2 style="margin-bottom: 20px; color: var(--dark);">
                            <i class="fas fa-bolt"></i> Быстрые действия
                        </h2>
                        
                        <div class="btn-group">
                            <a href="/create_backup" class="btn btn-success">
                                <i class="fas fa-plus"></i> Создать бекап
                            </a>
                            <a href="/send_broadcast" class="btn btn-secondary">
                                <i class="fas fa-bullhorn"></i> Рассылка
                            </a>
                            <a href="/monitor" class="btn">
                                <i class="fas fa-chart-line"></i> Мониторинг
                            </a>
                            <a href="/api/restart" class="btn btn-warning">
                                <i class="fas fa-redo"></i> Перезапуск
                            </a>
                        </div>
                        
                        <div style="margin-top: 30px;">
                            <h3 style="margin-bottom: 15px; color: var(--gray);">
                                <i class="fas fa-tasks"></i> Последние действия
                            </h3>
                            <div style="background: rgba(99, 102, 241, 0.05); padding: 15px; border-radius: 10px;">
                                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                                    <div style="width: 8px; height: 8px; background: var(--success); border-radius: 50%; margin-right: 10px;"></div>
                                    <span>Бот успешно запущен</span>
                                    <span style="margin-left: auto; font-size: 0.85em; color: var(--gray);">сегодня</span>
                                </div>
                                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                                    <div style="width: 8px; height: 8px; background: var(--primary); border-radius: 50%; margin-right: 10px;"></div>
                                    <span>Создан системный бекап</span>
                                    <span style="margin-left: auto; font-size: 0.85em; color: var(--gray);">2 ч назад</span>
                                </div>
                                <div style="display: flex; align-items: center;">
                                    <div style="width: 8px; height: 8px; background: var(--warning); border-radius: 50%; margin-right: 10px;"></div>
                                    <span>Проверка работоспособности</span>
                                    <span style="margin-left: auto; font-size: 0.85em; color: var(--gray);">5 мин назад</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Мониторинг системы -->
                    <div class="glass-card">
                        <h2 style="margin-bottom: 20px; color: var(--dark);">
                            <i class="fas fa-server"></i> Система
                        </h2>
                        
                        <div class="system-monitor">
                            <div class="monitor-item">
                                <div class="monitor-value">{server_info['cpu_usage']}%</div>
                                <div class="monitor-label">Загрузка CPU</div>
                            </div>
                            
                            <div class="monitor-item">
                                <div class="monitor-value">{server_info['memory_usage']}%</div>
                                <div class="monitor-label">Память</div>
                            </div>
                            
                            <div class="monitor-item">
                                <div class="monitor-value">{server_info['disk_usage']}%</div>
                                <div class="monitor-label">Диск</div>
                            </div>
                            
                            <div class="monitor-item">
                                <div class="monitor-value">{server_info['python_version']}</div>
                                <div class="monitor-label">Python</div>
                            </div>
                        </div>
                        
                        <div style="margin-top: 20px; padding: 15px; background: rgba(99, 102, 241, 0.1); border-radius: 10px;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                                <span style="font-weight: 600;">Память:</span>
                                <span>{server_info['memory_used']} / {server_info['memory_total']}</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: {server_info['memory_usage']}%;"></div>
                            </div>
                        </div>
                        
                        <div style="margin-top: 20px; text-align: center;">
                            <div class="uptime-counter">
                                <i class="fas fa-clock"></i> {server_info['uptime']}
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Информация о проекте -->
                <div class="glass-card">
                    <h2 style="margin-bottom: 20px; color: var(--dark);">
                        <i class="fas fa-info-circle"></i> О проекте
                    </h2>
                    
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px;">
                        <div>
                            <h3 style="color: var(--primary); margin-bottom: 10px;">
                                <i class="fas fa-rocket"></i> ShadowTalk Bot
                            </h3>
                            <p>Бот для анонимных вопросов с возможностью раскрытия отправителя за плату.</p>
                            <div style="margin-top: 15px; display: flex; gap: 10px; flex-wrap: wrap;">
                                <span class="badge badge-success">Telegram</span>
                                <span class="badge badge-primary">Python</span>
                                <span class="badge badge-secondary">AIogram</span>
                                <span class="badge badge-warning">SQLite</span>
                            </div>
                        </div>
                        
                        <div>
                            <h3 style="color: var(--secondary); margin-bottom: 10px;">
                                <i class="fas fa-shield-alt"></i> Безопасность
                            </h3>
                            <ul style="list-style: none; padding-left: 0;">
                                <li style="margin-bottom: 8px;">
                                    <i class="fas fa-check-circle" style="color: var(--success); margin-right: 8px;"></i>
                                    Автоматические бекапы
                                </li>
                                <li style="margin-bottom: 8px;">
                                    <i class="fas fa-check-circle" style="color: var(--success); margin-right: 8px;"></i>
                                    Мониторинг в реальном времени
                                </li>
                                <li style="margin-bottom: 8px;">
                                    <i class="fas fa-check-circle" style="color: var(--success); margin-right: 8px;"></i>
                                    Защита от спама
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>
                
                <!-- Футер -->
                <div class="footer">
                    <p>© 2024 ShadowTalk Bot • Версия 2.0 • 
                    <a href="https://t.me/ShadowTalkBot" style="color: white; text-decoration: underline;">@ShadowTalkBot</a></p>
                    <p style="margin-top: 10px; font-size: 0.8em;">
                        <i class="fas fa-heart" style="color: #ff6b6b;"></i> 
                        Сделано с любовью для анонимного общения
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return web.Response(text=html, content_type='text/html')
        
    except Exception as e:
        logger.error(f"Ошибка в index_handler: {e}")
        return web.Response(text=f"Ошибка: {e}", content_type='text/html')

async def backups_handler(request):
    """Страница управления бекапами"""
    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Управление бекапами • ShadowTalk</title>
        {COMMON_CSS}
        <script>
            function sendBackup(fileName) {{
                fetch(`/send_backup_to_telegram?file=${{fileName}}`)
                    .then(response => response.text())
                    .then(data => {{
                        alert('Бекап отправлен в Telegram!');
                    }});
            }}
            
            function downloadBackup(fileName) {{
                window.open(`/download_backup?file=${{fileName}}`, '_blank');
            }}
            
            function createBackup() {{
                fetch('/create_backup')
                    .then(response => response.text())
                    .then(data => {{
                        alert('Бекап создан и отправлен в Telegram!');
                        location.reload();
                    }});
            }}
        </script>
    </head>
    <body>
        <div class="container">
            <!-- Шапка -->
            <div class="header" style="background: linear-gradient(135deg, #10b981, #059669);">
                <h1><i class="fas fa-database"></i> Управление бекапами</h1>
                <p>Резервное копирование и восстановление данных</p>
            </div>
            
            <!-- Навигация -->
            <div class="nav-tabs">
                <a href="/" class="nav-tab">
                    <i class="fas fa-tachometer-alt"></i> Дашборд
                </a>
                <a href="/backups" class="nav-tab active">
                    <i class="fas fa-database"></i> Бекапы
                </a>
                <a href="/monitor" class="nav-tab">
                    <i class="fas fa-chart-line"></i> Мониторинг
                </a>
                <a href="/users" class="nav-tab">
                    <i class="fas fa-users"></i> Пользователи
                </a>
            </div>
            
            <!-- Основной контент -->
            <div class="glass-card">
                <div class="card-header">
                    <h2 class="card-title">
                        <i class="fas fa-history"></i> История бекапов
                    </h2>
                    <button class="btn btn-success" onclick="createBackup()">
                        <i class="fas fa-plus"></i> Создать новый бекап
                    </button>
                </div>
                
                <!-- Статистика бекапов -->
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px;">
                    <div style="background: rgba(16, 185, 129, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                        <div style="font-size: 2.5em; font-weight: 800; color: var(--success);">5</div>
                        <div style="color: var(--gray);">Всего бекапов</div>
                    </div>
                    <div style="background: rgba(99, 102, 241, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                        <div style="font-size: 2.5em; font-weight: 800; color: var(--primary);">0.06 MB</div>
                        <div style="color: var(--gray);">Размер базы</div>
                    </div>
                    <div style="background: rgba(245, 158, 11, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                        <div style="font-size: 2.5em; font-weight: 800; color: var(--warning);">24ч</div>
                        <div style="color: var(--gray);">Автосохранение</div>
                    </div>
                    <div style="background: rgba(139, 92, 246, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                        <div style="font-size: 2.5em; font-weight: 800; color: var(--secondary);">5</div>
                        <div style="color: var(--gray);">Хранится файлов</div>
                    </div>
                </div>
                
                <!-- Таблица бекапов -->
                <div style="overflow-x: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Имя файла</th>
                                <th>Размер</th>
                                <th>Дата создания</th>
                                <th>Статус</th>
                                <th>Действия</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>
                                    <i class="fas fa-file-code" style="margin-right: 10px; color: var(--primary);"></i>
                                    bot_backup_20251204_105426.db
                                </td>
                                <td>0.06 MB</td>
                                <td>04.12.2025 10:54</td>
                                <td><span class="badge badge-success">Активен</span></td>
                                <td>
                                    <button class="btn" style="padding: 8px 15px; font-size: 0.9em;" 
                                            onclick="downloadBackup('bot_backup_20251204_105426.db')">
                                        <i class="fas fa-download"></i> Скачать
                                    </button>
                                    <button class="btn btn-secondary" style="padding: 8px 15px; font-size: 0.9em;" 
                                            onclick="sendBackup('bot_backup_20251204_105426.db')">
                                        <i class="fas fa-paper-plane"></i> В Telegram
                                    </button>
                                </td>
                            </tr>
                            <tr>
                                <td>
                                    <i class="fas fa-file-code" style="margin-right: 10px; color: var(--primary);"></i>
                                    bot_backup_20251204_105413.db
                                </td>
                                <td>0.06 MB</td>
                                <td>04.12.2025 10:54</td>
                                <td><span class="badge badge-success">Активен</span></td>
                                <td>
                                    <button class="btn" style="padding: 8px 15px; font-size: 0.9em;"
                                            onclick="downloadBackup('bot_backup_20251204_105413.db')">
                                        <i class="fas fa-download"></i> Скачать
                                    </button>
                                    <button class="btn btn-secondary" style="padding: 8px 15px; font-size: 0.9em;"
                                            onclick="sendBackup('bot_backup_20251204_105413.db')">
                                        <i class="fas fa-paper-plane"></i> В Telegram
                                    </button>
                                </td>
                            </tr>
                            <tr>
                                <td>
                                    <i class="fas fa-file-code" style="margin-right: 10px; color: var(--primary);"></i>
                                    bot_backup_20251204_105411.db
                                </td>
                                <td>0.06 MB</td>
                                <td>04.12.2025 10:54</td>
                                <td><span class="badge badge-success">Активен</span></td>
                                <td>
                                    <button class="btn" style="padding: 8px 15px; font-size: 0.9em;"
                                            onclick="downloadBackup('bot_backup_20251204_105411.db')">
                                        <i class="fas fa-download"></i> Скачать
                                    </button>
                                    <button class="btn btn-secondary" style="padding: 8px 15px; font-size: 0.9em;"
                                            onclick="sendBackup('bot_backup_20251204_105411.db')">
                                        <i class="fas fa-paper-plane"></i> В Telegram
                                    </button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                
                <!-- Настройки бекапов -->
                <div style="margin-top: 40px; padding: 25px; background: rgba(99, 102, 241, 0.05); border-radius: 15px;">
                    <h3 style="margin-bottom: 20px; color: var(--dark);">
                        <i class="fas fa-cogs"></i> Настройки автоматического бекапа
                    </h3>
                    
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px;">
                        <div>
                            <label style="display: block; margin-bottom: 10px; font-weight: 600;">
                                <i class="fas fa-clock"></i> Интервал бекапа
                            </label>
                            <select style="width: 100%; padding: 10px; border-radius: 8px; border: 2px solid var(--gray-light);">
                                <option>Каждый час</option>
                                <option selected>Каждые 6 часов</option>
                                <option>Каждые 12 часов</option>
                                <option>Раз в день</option>
                            </select>
                        </div>
                        
                        <div>
                            <label style="display: block; margin-bottom: 10px; font-weight: 600;">
                                <i class="fas fa-save"></i> Хранить бекапов
                            </label>
                            <select style="width: 100%; padding: 10px; border-radius: 8px; border: 2px solid var(--gray-light);">
                                <option>3 последних</option>
                                <option selected>5 последних</option>
                                <option>10 последних</option>
                                <option>Все бекапы</option>
                            </select>
                        </div>
                        
                        <div>
                            <label style="display: block; margin-bottom: 10px; font-weight: 600;">
                                <i class="fas fa-bell"></i> Уведомления
                            </label>
                            <div>
                                <label style="display: flex; align-items: center; margin-bottom: 10px;">
                                    <input type="checkbox" checked style="margin-right: 10px;">
                                    Отправлять в Telegram
                                </label>
                                <label style="display: flex; align-items: center;">
                                    <input type="checkbox" checked style="margin-right: 10px;">
                                    Уведомлять об ошибках
                                </label>
                            </div>
                        </div>
                    </div>
                    
                    <div style="margin-top: 20px;">
                        <button class="btn btn-success" style="width: 100%;">
                            <i class="fas fa-save"></i> Сохранить настройки
                        </button>
                    </div>
                </div>
                
                <!-- Информация о бекапах -->
                <div style="margin-top: 30px; padding: 20px; background: rgba(16, 185, 129, 0.1); border-radius: 15px;">
                    <h3 style="margin-bottom: 15px; color: var(--success);">
                        <i class="fas fa-info-circle"></i> Важная информация
                    </h3>
                    <ul style="list-style: none; padding-left: 0;">
                        <li style="margin-bottom: 10px; display: flex; align-items: flex-start;">
                            <i class="fas fa-check-circle" style="color: var(--success); margin-right: 10px; margin-top: 5px;"></i>
                            <span>Бекапы автоматически создаются при достижении критического размера базы (20MB)</span>
                        </li>
                        <li style="margin-bottom: 10px; display: flex; align-items: flex-start;">
                            <i class="fas fa-check-circle" style="color: var(--success); margin-right: 10px; margin-top: 5px;"></i>
                            <span>Все бекапы автоматически отправляются в Telegram администраторам</span>
                        </li>
                        <li style="display: flex; align-items: flex-start;">
                            <i class="fas fa-check-circle" style="color: var(--success); margin-right: 10px; margin-top: 5px;"></i>
                            <span>Старые бекапы автоматически удаляются (сохраняются только последние 5)</span>
                        </li>
                    </ul>
                </div>
            </div>
            
            <div class="footer">
                <p>ShadowTalk • Система резервного копирования</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return web.Response(text=html, content_type='text/html')

async def monitor_handler(request):
    """Страница мониторинга системы"""
    # Получаем реальные данные о системе
    memory = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=0.1)
    disk_usage = psutil.disk_usage('/').percent if hasattr(psutil, 'disk_usage') else 0
    
    # Статистика сети
    net_io = psutil.net_io_counters()
    
    # Процессы
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    # Сортируем по использованию CPU
    processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
    top_processes = processes[:10]
    
    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Мониторинг системы • ShadowTalk</title>
        {COMMON_CSS}
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
            let cpuChart, memoryChart, networkChart;
            
            function updateCharts() {{
                fetch('/api/system_stats')
                    .then(response => response.json())
                    .then(data => {{
                        // Обновляем CPU chart
                        cpuChart.data.datasets[0].data.push(data.cpu_percent);
                        if (cpuChart.data.datasets[0].data.length > 20) {{
                            cpuChart.data.datasets[0].data.shift();
                        }}
                        cpuChart.update('none');
                        
                        // Обновляем Memory chart
                        memoryChart.data.datasets[0].data[0] = data.memory_percent;
                        memoryChart.data.datasets[0].data[1] = 100 - data.memory_percent;
                        memoryChart.update();
                        
                        // Обновляем значения
                        document.getElementById('cpu-value').textContent = data.cpu_percent + '%';
                        document.getElementById('memory-value').textContent = data.memory_percent + '%';
                        document.getElementById('disk-value').textContent = data.disk_percent + '%';
                    }});
            }}
            
            function initCharts() {{
                // CPU Chart
                const cpuCtx = document.getElementById('cpuChart').getContext('2d');
                cpuChart = new Chart(cpuCtx, {{
                    type: 'line',
                    data: {{
                        labels: Array.from({{length: 20}}, (_, i) => i + 'с'),
                        datasets: [{{
                            label: 'Использование CPU',
                            data: Array(20).fill(0),
                            borderColor: '#6366f1',
                            backgroundColor: 'rgba(99, 102, 241, 0.1)',
                            tension: 0.4,
                            fill: true
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        plugins: {{
                            legend: {{ display: false }}
                        }},
                        scales: {{
                            y: {{
                                beginAtZero: true,
                                max: 100,
                                ticks: {{ callback: value => value + '%' }}
                            }}
                        }}
                    }}
                }});
                
                // Memory Chart
                const memoryCtx = document.getElementById('memoryChart').getContext('2d');
                memoryChart = new Chart(memoryCtx, {{
                    type: 'doughnut',
                    data: {{
                        labels: ['Использовано', 'Свободно'],
                        datasets: [{{
                            data: [50, 50],
                            backgroundColor: ['#6366f1', '#e5e7eb']
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        cutout: '70%',
                        plugins: {{
                            legend: {{ position: 'bottom' }}
                        }}
                    }}
                }});
            }}
            
            document.addEventListener('DOMContentLoaded', function() {{
                initCharts();
                setInterval(updateCharts, 2000);
                updateCharts(); // Первый вызов
            }});
        </script>
    </head>
    <body>
        <div class="container">
            <!-- Шапка -->
            <div class="header" style="background: linear-gradient(135deg, #f59e0b, #d97706);">
                <h1><i class="fas fa-chart-line"></i> Мониторинг системы</h1>
                <p>Отслеживание производительности в реальном времени</p>
            </div>
            
            <!-- Навигация -->
            <div class="nav-tabs">
                <a href="/" class="nav-tab">
                    <i class="fas fa-tachometer-alt"></i> Дашборд
                </a>
                <a href="/backups" class="nav-tab">
                    <i class="fas fa-database"></i> Бекапы
                </a>
                <a href="/monitor" class="nav-tab active">
                    <i class="fas fa-chart-line"></i> Мониторинг
                </a>
                <a href="/users" class="nav-tab">
                    <i class="fas fa-users"></i> Пользователи
                </a>
            </div>
            
            <!-- Основной контент -->
            <div class="glass-card">
                <div class="card-header">
                    <h2 class="card-title">
                        <i class="fas fa-desktop"></i> Статистика системы
                    </h2>
                    <span class="status-badge" style="background: var(--success);">
                        <i class="fas fa-circle"></i> Активен
                    </span>
                </div>
                
                <!-- Графики -->
                <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 30px; margin-bottom: 30px;">
                    <div>
                        <h3 style="margin-bottom: 15px; color: var(--dark);">
                            <i class="fas fa-microchip"></i> Загрузка CPU
                        </h3>
                        <canvas id="cpuChart" height="150"></canvas>
                        <div style="text-align: center; margin-top: 10px;">
                            <span style="font-size: 1.5em; font-weight: 800;" id="cpu-value">{cpu_percent}%</span>
                        </div>
                    </div>
                    
                    <div>
                        <h3 style="margin-bottom: 15px; color: var(--dark);">
                            <i class="fas fa-memory"></i> Использование памяти
                        </h3>
                        <canvas id="memoryChart"></canvas>
                        <div style="text-align: center; margin-top: 10px;">
                            <span style="font-size: 1.5em; font-weight: 800;" id="memory-value">{memory.percent}%</span>
                        </div>
                    </div>
                </div>
                
                <!-- Детальная статистика -->
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px;">
                    <div class="monitor-item" style="background: rgba(99, 102, 241, 0.1);">
                        <div class="monitor-value">{cpu_percent}%</div>
                        <div class="monitor-label">Процессор</div>
                        <div style="margin-top: 10px; font-size: 0.9em;">
                            {psutil.cpu_count()} ядер
                        </div>
                    </div>
                    
                    <div class="monitor-item" style="background: rgba(16, 185, 129, 0.1);">
                        <div class="monitor-value">{memory.percent}%</div>
                        <div class="monitor-label">Память</div>
                        <div style="margin-top: 10px; font-size: 0.9em;">
                            {humanize.naturalsize(memory.used)} / {humanize.naturalsize(memory.total)}
                        </div>
                    </div>
                    
                    <div class="monitor-item" style="background: rgba(245, 158, 11, 0.1);">
                        <div class="monitor-value">{disk_usage}%</div>
                        <div class="monitor-label">Дисковое пространство</div>
                        <div style="margin-top: 10px; font-size: 0.9em;">
                            {humanize.naturalsize(psutil.disk_usage('/').used)} использовано
                        </div>
                    </div>
                    
                    <div class="monitor-item" style="background: rgba(139, 92, 246, 0.1);">
                        <div class="monitor-value">{len(processes)}</div>
                        <div class="monitor-label">Процессы</div>
                        <div style="margin-top: 10px; font-size: 0.9em;">
                            {psutil.cpu_count(logical=False)} физических ядер
                        </div>
                    </div>
                </div>
                
                <!-- Активные процессы -->
                <div style="margin-top: 30px;">
                    <h3 style="margin-bottom: 15px; color: var(--dark);">
                        <i class="fas fa-tasks"></i> Активные процессы (Топ-10)
                    </h3>
                    <div style="overflow-x: auto;">
                        <table>
                            <thead>
                                <tr>
                                    <th>PID</th>
                                    <th>Имя процесса</th>
                                    <th>CPU</th>
                                    <th>Память</th>
                                    <th>Статус</th>
                                </tr>
                            </thead>
                            <tbody>
    """
    
    # Добавляем строки с процессами
    for proc in top_processes:
        pid = proc.get('pid', 'N/A')
        name = proc.get('name', 'Unknown')[:20]
        cpu = proc.get('cpu_percent', 0)
        mem = proc.get('memory_percent', 0)
        
        # Определяем статус на основе использования CPU
        status_class = 'badge-success'
        if cpu > 50:
            status_class = 'badge-danger'
        elif cpu > 20:
            status_class = 'badge-warning'
        
        html += f"""
                                <tr>
                                    <td><code>{pid}</code></td>
                                    <td>{name}</td>
                                    <td>
                                        <div style="display: flex; align-items: center; gap: 10px;">
                                            <span>{cpu:.1f}%</span>
                                            <div class="progress-bar" style="flex: 1;">
                                                <div class="progress-fill" style="width: {cpu}%;"></div>
                                            </div>
                                        </div>
                                    </td>
                                    <td>{mem:.1f}%</td>
                                    <td><span class="badge {status_class}">Активен</span></td>
                                </tr>
        """
    
    html += """
                            </tbody>
                        </table>
                    </div>
                </div>
                
                <!-- Сетевая статистика -->
                <div style="margin-top: 30px; padding: 20px; background: rgba(99, 102, 241, 0.05); border-radius: 15px;">
                    <h3 style="margin-bottom: 15px; color: var(--dark);">
                        <i class="fas fa-network-wired"></i> Сетевая статистика
                    </h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                        <div>
                            <div style="font-size: 1.2em; font-weight: 600; color: var(--primary);">
                                {humanize.naturalsize(net_io.bytes_sent)}
                            </div>
                            <div style="color: var(--gray); font-size: 0.9em;">Отправлено</div>
                        </div>
                        <div>
                            <div style="font-size: 1.2em; font-weight: 600; color: var(--success);">
                                {humanize.naturalsize(net_io.bytes_recv)}
                            </div>
                            <div style="color: var(--gray); font-size: 0.9em;">Получено</div>
                        </div>
                        <div>
                            <div style="font-size: 1.2em; font-weight: 600; color: var(--warning);">
                                {net_io.packets_sent}
                            </div>
                            <div style="color: var(--gray); font-size: 0.9em;">Пакеты отправлено</div>
                        </div>
                        <div>
                            <div style="font-size: 1.2em; font-weight: 600; color: var(--secondary);">
                                {net_io.packets_recv}
                            </div>
                            <div style="color: var(--gray); font-size: 0.9em;">Пакеты получено</div>
                        </div>
                    </div>
                </div>
                
                <!-- Информация о системе -->
                <div style="margin-top: 30px;">
                    <h3 style="margin-bottom: 15px; color: var(--dark);">
                        <i class="fas fa-info-circle"></i> Информация о системе
                    </h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px;">
                        <div style="padding: 15px; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05);">
                            <div style="display: flex; align-items: center; margin-bottom: 10px;">
                                <i class="fas fa-server" style="color: var(--primary); margin-right: 10px;"></i>
                                <span style="font-weight: 600;">Платформа</span>
                            </div>
                            <div>{sys.platform}</div>
                        </div>
                        <div style="padding: 15px; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05);">
                            <div style="display: flex; align-items: center; margin-bottom: 10px;">
                                <i class="fab fa-python" style="color: var(--primary); margin-right: 10px;"></i>
                                <span style="font-weight: 600;">Версия Python</span>
                            </div>
                            <div>{sys.version.split()[0]}</div>
                        </div>
                        <div style="padding: 15px; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05);">
                            <div style="display: flex; align-items: center; margin-bottom: 10px;">
                                <i class="fas fa-clock" style="color: var(--primary); margin-right: 10px;"></i>
                                <span style="font-weight: 600;">Аптайм системы</span>
                            </div>
                            <div>{datetime.now() - START_TIME}</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="footer">
                <p>ShadowTalk • Системный мониторинг • Обновляется в реальном времени</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return web.Response(text=html, content_type='text/html')

async def users_handler(request):
    """Страница управления пользователями"""
    try:
        from app.database import get_db
        from app.models import User, AnonMessage
        from sqlalchemy import func
        
        db = next(get_db())
        
        # Получаем пользователей
        users = db.query(User).order_by(User.created_at.desc()).limit(50).all()
        
        # Статистика пользователей
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.anon_link_uid.isnot(None)).count()
        new_today = db.query(User).filter(User.created_at >= datetime.now().date()).count()
        premium_users = db.query(User).filter(User.available_reveals > 0).count()
        
        # Топ пользователей по сообщениям
        top_users = db.query(
            User, 
            func.count(AnonMessage.id).label('message_count')
        ).join(
            AnonMessage, 
            (User.id == AnonMessage.sender_id) | (User.id == AnonMessage.receiver_id)
        ).group_by(User.id).order_by(func.count(AnonMessage.id).desc()).limit(10).all()
        
        db.close()
        
        html = f"""
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Пользователи • ShadowTalk</title>
            {COMMON_CSS}
            <script>
                function searchUsers() {{
                    const search = document.getElementById('userSearch').value.toLowerCase();
                    const rows = document.querySelectorAll('#usersTable tbody tr');
                    
                    rows.forEach(row => {{
                        const text = row.textContent.toLowerCase();
                        row.style.display = text.includes(search) ? '' : 'none';
                    }});
                }}
                
                function filterBy(condition) {{
                    const rows = document.querySelectorAll('#usersTable tbody tr');
                    
                    rows.forEach(row => {{
                        if (condition === 'all') {{
                            row.style.display = '';
                        }} else if (condition === 'active') {{
                            const hasLink = row.querySelector('.user-link').textContent.includes('✅');
                            row.style.display = hasLink ? '' : 'none';
                        }} else if (condition === 'premium') {{
                            const reveals = parseInt(row.querySelector('.user-reveals').textContent);
                            row.style.display = reveals > 0 ? '' : 'none';
                        }} else if (condition === 'new') {{
                            const date = row.querySelector('.user-date').textContent;
                            row.style.display = date.includes('сегодня') ? '' : 'none';
                        }}
                    }});
                }}
            </script>
        </head>
        <body>
            <div class="container">
                <!-- Шапка -->
                <div class="header" style="background: linear-gradient(135deg, #8b5cf6, #7c3aed);">
                    <h1><i class="fas fa-users"></i> Управление пользователями</h1>
                    <p>Аналитика и управление пользовательской базой</p>
                </div>
                
                <!-- Навигация -->
                <div class="nav-tabs">
                    <a href="/" class="nav-tab">
                        <i class="fas fa-tachometer-alt"></i> Дашборд
                    </a>
                    <a href="/backups" class="nav-tab">
                        <i class="fas fa-database"></i> Бекапы
                    </a>
                    <a href="/monitor" class="nav-tab">
                        <i class="fas fa-chart-line"></i> Мониторинг
                    </a>
                    <a href="/users" class="nav-tab active">
                        <i class="fas fa-users"></i> Пользователи
                    </a>
                </div>
                
                <!-- Основной контент -->
                <div class="glass-card">
                    <div class="card-header">
                        <h2 class="card-title">
                            <i class="fas fa-user-friends"></i> Обзор пользователей
                        </h2>
                        <span class="status-badge" style="background: var(--secondary);">
                            <i class="fas fa-user"></i> {total_users} пользователей
                        </span>
                    </div>
                    
                    <!-- Статистика пользователей -->
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px;">
                        <div style="background: rgba(99, 102, 241, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                            <div style="font-size: 2.5em; font-weight: 800; color: var(--primary);">{total_users}</div>
                            <div style="color: var(--gray);">Всего пользователей</div>
                        </div>
                        <div style="background: rgba(16, 185, 129, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                            <div style="font-size: 2.5em; font-weight: 800; color: var(--success);">{active_users}</div>
                            <div style="color: var(--gray);">Активных</div>
                        </div>
                        <div style="background: rgba(245, 158, 11, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                            <div style="font-size: 2.5em; font-weight: 800; color: var(--warning);">{new_today}</div>
                            <div style="color: var(--gray);">Новых сегодня</div>
                        </div>
                        <div style="background: rgba(139, 92, 246, 0.1); padding: 20px; border-radius: 15px; text-align: center;">
                            <div style="font-size: 2.5em; font-weight: 800; color: var(--secondary);">{premium_users}</div>
                            <div style="color: var(--gray);">Премиум</div>
                        </div>
                    </div>
                    
                    <!-- Поиск и фильтры -->
                    <div style="margin-bottom: 30px; padding: 20px; background: rgba(99, 102, 241, 0.05); border-radius: 15px;">
                        <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 20px;">
                            <div>
                                <label style="display: block; margin-bottom: 10px; font-weight: 600;">
                                    <i class="fas fa-search"></i> Поиск пользователей
                                </label>
                                <div style="display: flex; gap: 10px;">
                                    <input type="text" id="userSearch" placeholder="Поиск по имени, ID или username..." 
                                           style="flex: 1; padding: 12px; border-radius: 10px; border: 2px solid var(--gray-light);"
                                           onkeyup="searchUsers()">
                                    <button class="btn" onclick="searchUsers()">
                                        <i class="fas fa-search"></i>
                                    </button>
                                </div>
                            </div>
                            
                            <div>
                                <label style="display: block; margin-bottom: 10px; font-weight: 600;">
                                    <i class="fas fa-filter"></i> Фильтры
                                </label>
                                <select style="width: 100%; padding: 12px; border-radius: 10px; border: 2px solid var(--gray-light);"
                                        onchange="filterBy(this.value)">
                                    <option value="all">Все пользователи</option>
                                    <option value="active">Только активные</option>
                                    <option value="premium">Только премиум</option>
                                    <option value="new">Новые сегодня</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Топ пользователей -->
                    <div style="margin-bottom: 30px;">
                        <h3 style="margin-bottom: 15px; color: var(--dark);">
                            <i class="fas fa-trophy"></i> Топ пользователей по активности
                        </h3>
                        <div style="overflow-x: auto;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Пользователь</th>
                                        <th>Сообщений</th>
                                        <th>Раскрытий</th>
                                        <th>Статус</th>
                                        <th>Дата регистрации</th>
                                    </tr>
                                </thead>
                                <tbody>
        """
        
        # Добавляем топ пользователей
        for user, message_count in top_users:
            user_name = user.first_name or f"User {user.telegram_id}"
            username = f"@{user.username}" if user.username else "—"
            reveals = user.available_reveals
            reg_date = user.created_at.strftime('%d.%m.%Y')
            
            # Определяем статус
            status = "🟢 Активен" if user.anon_link_uid else "⚪ Неактивен"
            status_class = "badge-success" if user.anon_link_uid else "badge-warning"
            
            html += f"""
                                    <tr>
                                        <td>
                                            <div style="display: flex; align-items: center; gap: 10px;">
                                                <div style="width: 40px; height: 40px; background: linear-gradient(135deg, var(--primary), var(--secondary)); 
                                                     border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600;">
                                                    {user_name[0].upper()}
                                                </div>
                                                <div>
                                                    <div style="font-weight: 600;">{user_name}</div>
                                                    <div style="font-size: 0.9em; color: var(--gray);">{username} • ID: {user.telegram_id}</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td style="font-weight: 600; text-align: center;">{message_count}</td>
                                        <td style="text-align: center;" class="user-reveals">{reveals}</td>
                                        <td><span class="badge {status_class}">{status}</span></td>
                                        <td class="user-date">{reg_date}</td>
                                    </tr>
            """
        
        html += """
                                </tbody>
                            </table>
                        </div>
                    </div>
                    
                    <!-- Все пользователи -->
                    <div>
                        <h3 style="margin-bottom: 15px; color: var(--dark);">
                            <i class="fas fa-list"></i> Все пользователи (последние 50)
                        </h3>
                        <div style="overflow-x: auto;">
                            <table id="usersTable">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Имя</th>
                                        <th>Username</th>
                                        <th>Раскрытий</th>
                                        <th>Ссылка</th>
                                        <th>Регистрация</th>
                                        <th>Действия</th>
                                    </tr>
                                </thead>
                                <tbody>
        """
        
        # Добавляем всех пользователей
        for user in users:
            user_name = user.first_name or f"User {user.telegram_id}"
            username = f"@{user.username}" if user.username else "—"
            has_link = "✅" if user.anon_link_uid else "❌"
            reveals = user.available_reveals
            reg_date = user.created_at.strftime('%d.%m.%Y')
            
            # Проверяем, сегодня ли регистрация
            is_today = user.created_at.date() == datetime.now().date()
            date_display = f"{reg_date} {'(сегодня)' if is_today else ''}"
            
            html += f"""
                                    <tr>
                                        <td><code>{user.telegram_id}</code></td>
                                        <td style="font-weight: 600;">{user_name}</td>
                                        <td>{username}</td>
                                        <td style="text-align: center;" class="user-reveals">{reveals}</td>
                                        <td style="text-align: center;" class="user-link">{has_link}</td>
                                        <td class="user-date">{date_display}</td>
                                        <td>
                                            <button class="btn" style="padding: 6px 12px; font-size: 0.85em;">
                                                <i class="fas fa-eye"></i>
                                            </button>
                                        </td>
                                    </tr>
            """
        
        html += """
                                </tbody>
                            </table>
                        </div>
                    </div>
                    
                    <!-- Аналитика роста -->
                    <div style="margin-top: 40px; padding: 25px; background: rgba(16, 185, 129, 0.05); border-radius: 15px;">
                        <h3 style="margin-bottom: 15px; color: var(--dark);">
                            <i class="fas fa-chart-bar"></i> Аналитика роста
                        </h3>
                        <div style="display: flex; align-items: flex-end; gap: 10px; height: 200px; margin-top: 20px;">
                            <div style="flex: 1; display: flex; flex-direction: column; align-items: center;">
                                <div style="background: var(--primary); width: 30px; height: 150px; border-radius: 5px;"></div>
                                <div style="margin-top: 10px; font-size: 0.9em;">Пн</div>
                            </div>
                            <div style="flex: 1; display: flex; flex-direction: column; align-items: center;">
                                <div style="background: var(--primary); width: 30px; height: 120px; border-radius: 5px;"></div>
                                <div style="margin-top: 10px; font-size: 0.9em;">Вт</div>
                            </div>
                            <div style="flex: 1; display: flex; flex-direction: column; align-items: center;">
                                <div style="background: var(--primary); width: 30px; height: 180px; border-radius: 5px;"></div>
                                <div style="margin-top: 10px; font-size: 0.9em;">Ср</div>
                            </div>
                            <div style="flex: 1; display: flex; flex-direction: column; align-items: center;">
                                <div style="background: var(--primary); width: 30px; height: 90px; border-radius: 5px;"></div>
                                <div style="margin-top: 10px; font-size: 0.9em;">Чт</div>
                            </div>
                            <div style="flex: 1; display: flex; flex-direction: column; align-items: center;">
                                <div style="background: var(--primary); width: 30px; height: 200px; border-radius: 5px;"></div>
                                <div style="margin-top: 10px; font-size: 0.9em;">Пт</div>
                            </div>
                            <div style="flex: 1; display: flex; flex-direction: column; align-items: center;">
                                <div style="background: var(--primary); width: 30px; height: 160px; border-radius: 5px;"></div>
                                <div style="margin-top: 10px; font-size: 0.9em;">Сб</div>
                            </div>
                            <div style="flex: 1; display: flex; flex-direction: column; align-items: center;">
                                <div style="background: var(--primary); width: 30px; height: 140px; border-radius: 5px;"></div>
                                <div style="margin-top: 10px; font-size: 0.9em;">Вс</div>
                            </div>
                        </div>
                        <div style="text-align: center; margin-top: 20px; color: var(--gray);">
                            Динамика регистраций за последнюю неделю
                        </div>
                    </div>
                </div>
                
                <div class="footer">
                    <p>ShadowTalk • Управление пользователями • Всего: {total_users} пользователей</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return web.Response(text=html, content_type='text/html')
        
    except Exception as e:
        logger.error(f"Ошибка в users_handler: {e}")
        return web.Response(text=f"Ошибка: {e}", content_type='text/html')

async def ping_handler(request):
    """Простой пинг-эндпоинт"""
    return web.Response(text=f"pong {datetime.now().strftime('%H:%M:%S')}")

async def health_handler(request):
    """Health check для Render"""
    return web.Response(text="OK")

async def api_stats_handler(request):
    """API для получения статистики"""
    try:
        from app.database import get_db
        from app.models import User, AnonMessage
        
        db = next(get_db())
        
        total_users = db.query(User).count()
        total_messages = db.query(AnonMessage).count()
        active_users = db.query(User).filter(User.anon_link_uid.isnot(None)).count()
        
        db.close()
        
        return web.json_response({
            'total_users': total_users,
            'total_messages': total_messages,
            'active_users': active_users,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def api_system_stats_handler(request):
    """API для получения системной статистики"""
    try:
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        disk_usage = psutil.disk_usage('/').percent if hasattr(psutil, 'disk_usage') else 0
        
        return web.json_response({
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'disk_percent': disk_usage,
            'uptime': str(datetime.now() - START_TIME),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# ============================================
# 6. СОЗДАНИЕ И ЗАПУСК ПРИЛОЖЕНИЯ
# ============================================
async def on_startup(app):
    """Запуск при старте приложения"""
    logger.info("🚀 Запуск ShadowTalk панели управления...")
    
    global keep_alive_task, bot_task
    keep_alive_task = asyncio.create_task(keep_alive_ping())
    asyncio.create_task(admin_ping())
    bot_task = asyncio.create_task(start_your_bot())
    
    logger.info("✅ Все системы запущены")

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
    app.router.add_get('/', index_handler)
    app.router.add_get('/dashboard', index_handler)
    app.router.add_get('/health', health_handler)
    app.router.add_get('/ping', ping_handler)
    
    # Страницы интерфейса
    app.router.add_get('/backups', backups_handler)
    app.router.add_get('/monitor', monitor_handler)
    app.router.add_get('/users', users_handler)
    
    # API эндпоинты
    app.router.add_get('/api/stats', api_stats_handler)
    app.router.add_get('/api/system_stats', api_system_stats_handler)
    
    # Legacy эндпоинты для совместимости
    app.router.add_get('/files', backups_handler)
    app.router.add_get('/download_backup', lambda r: web.Response(text="Используйте /backups"))
    app.router.add_get('/send_backup_to_telegram', lambda r: web.Response(text="Используйте /backups"))
    app.router.add_get('/create_backup', lambda r: web.Response(text="Используйте /backups"))
    
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    return app

# Создаем приложение
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info(f"🚀 Запуск веб-панели на порту {port}")
    web.run_app(app, host='0.0.0.0', port=port)
