#!/bin/bash
echo "🚀 Запуск ShadowTalk с модульной архитектурой..."

# Создаем структуру папок
mkdir -p data backups logs web/static/css web/static/js

# Запускаем бота в фоне
echo "🤖 Запуск Telegram бота в фоне..."
python3 -u run_bot.py &

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
