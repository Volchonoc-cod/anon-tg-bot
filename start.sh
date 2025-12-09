#!/bin/bash
echo "🚀 Запуск ShadowTalk с модульной архитектурой..."

# Создаем структуру папок
mkdir -p data backups logs web/static/css web/static/js

echo "✅ Структура папок создана"

# Экспортируем переменные окружения
export RENDER=true
export PORT=${PORT:-8080}

echo "🌐 Порт: $PORT"
echo "🔧 Режим: Render"

# Создаем таблицы БД перед запуском
echo "🗄️ Проверка таблиц БД..."
python3 -c "
import sys
sys.path.insert(0, '.')
from app.database import engine
from app.models import Base
Base.metadata.create_all(bind=engine)
print('✅ Таблицы БД созданы/проверены')
" || echo "⚠️ Не удалось создать таблицы БД"

# Запускаем бота в фоне
echo "🤖 Запуск Telegram бота в фоне..."
python3 -u run_bot.py &
BOT_PID=$!

echo "✅ Бот запущен с PID: $BOT_PID"

# Ждем немного чтобы бот успел инициализироваться
echo "⏳ Ожидание инициализации бота..."
sleep 5

# Проверяем что бот жив
if ps -p $BOT_PID > /dev/null; then
    echo "✅ Бот работает (PID: $BOT_PID)"
else
    echo "❌ Бот не запустился, проверьте логи"
fi

# Запускаем веб-сервер
echo "🌐 Запуск веб-сервера на порту $PORT..."
exec gunicorn render_server:app \
    --bind 0.0.0.0:$PORT \
    --worker-class aiohttp.GunicornWebWorker \
    --workers 1 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
