#!/bin/bash
# startup.sh

echo "🚀 Запуск приложения..."

# 1. Автоматическое восстановление БД
echo "🔍 Проверка и восстановление БД..."
python auto_restore.py

# 2. Запуск веб-сервера
echo "🌐 Запуск веб-сервера..."
exec gunicorn render_server:app --bind 0.0.0.0:$PORT --worker-class aiohttp.GunicornWebWorker
