#!/bin/bash
# start.sh - скрипт запуска для модульной архитектуры

echo "🚀 Запуск ShadowTalk с модульной архитектурой..."

# Создаем структуру папок
mkdir -p data backups logs web/static/css web/static/js

# Запускаем бота в фоне
echo "🤖 Запуск Telegram бота в фоне..."
python3 -c "
import subprocess
import sys
import os
import time

# Запускаем бота
bot_proc = subprocess.Popen(
    [sys.executable, 'run_bot.py'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

print(f'[MAIN] ✅ Бот запущен, PID: {bot_proc.pid}')

# Даем боту время на запуск
time.sleep(3)
" &

# Ждем немного
sleep 2

# Запускаем веб-сервер
echo "🌐 Запуск веб-сервера на порту \$PORT..."
exec gunicorn render_server:app \
    --bind 0.0.0.0:\$PORT \
    --worker-class aiohttp.GunicornWebWorker \
    --workers 1 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
