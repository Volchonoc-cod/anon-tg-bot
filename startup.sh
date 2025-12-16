#!/bin/bash
# startup.sh - Объединенная версия

echo "🚀 Запуск ShadowTalk Bot на Render..."

# Устанавливаем переменные окружения
export PYTHONPATH=/opt/render/project/src
export RENDER=true

# Переходим в директорию проекта
cd /opt/render/project/src

# 1. Создаем необходимые директории
echo "📁 Создаю необходимые директории..."
mkdir -p data backups logs uploads

# 2. Проверка и восстановление БД
echo "🔍 Проверка и восстановление БД..."
if [ -f "auto_restore.py" ]; then
    python auto_restore.py
    RESTORE_RESULT=$?
    if [ $RESTORE_RESULT -eq 0 ]; then
        echo "✅ Автовосстановление БД завершено успешно"
    else
        echo "⚠️ Автовосстановление не выполнено или завершилось с ошибкой"
    fi
else
    echo "⚠️ Файл auto_restore.py не найден, пропускаю автовосстановление"
fi

# 3. Проверяем наличие таблиц БД
echo "🔍 Проверяю базу данных..."
if [ ! -f data/bot.db ] || [ ! -s data/bot.db ]; then
    echo "📝 База данных не найдена или пустая, создаю таблицы..."
    if [ -f "create_tables.py" ]; then
        python create_tables.py
    else
        echo "❌ Файл create_tables.py не найден, создаю БД через Python..."
        python -c "
import sqlite3
import os

# Создаем базовую БД
conn = sqlite3.connect('data/bot.db')
cursor = conn.cursor()

# Создаем таблицу users
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        first_name TEXT NOT NULL,
        last_name TEXT,
        anon_link_uid TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        balance INTEGER DEFAULT 0,
        premium_until TIMESTAMP,
        available_reveals INTEGER DEFAULT 0
    )
''')

# Создаем таблицу payments
cursor.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        payment_type TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        yookassa_payment_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
''')

# Создаем таблицу anon_messages
cursor.execute('''
    CREATE TABLE IF NOT EXISTS anon_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER,
        receiver_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        is_anonymous BOOLEAN DEFAULT TRUE,
        is_revealed BOOLEAN DEFAULT FALSE,
        is_reported BOOLEAN DEFAULT FALSE,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reply_to_message_id INTEGER,
        FOREIGN KEY (sender_id) REFERENCES users (id),
        FOREIGN KEY (receiver_id) REFERENCES users (id),
        FOREIGN KEY (reply_to_message_id) REFERENCES anon_messages (id)
    )
''')

conn.commit()
conn.close()
print('✅ База данных создана')
        "
    fi
else
    echo "✅ База данных уже существует"
    
    # Проверяем структуру БД
    echo "🔍 Проверяю структуру БД..."
    python -c "
import sqlite3
import sys

try:
    conn = sqlite3.connect('data/bot.db')
    cursor = conn.cursor()
    
    # Проверяем основные таблицы
    cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
    tables = [row[0] for row in cursor.fetchall()]
    
    required_tables = ['users', 'anon_messages', 'payments']
    missing_tables = [t for t in required_tables if t not in tables]
    
    if missing_tables:
        print(f'⚠️ Отсутствуют таблицы: {missing_tables}')
        sys.exit(1)
    else:
        print('✅ Все необходимые таблицы существуют')
        
        # Проверяем количество записей в каждой таблице
        for table in required_tables:
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            count = cursor.fetchone()[0]
            print(f'  📋 {table}: {count} записей')
    
    conn.close()
    
except Exception as e:
    print(f'❌ Ошибка проверки БД: {e}')
    sys.exit(1)
    "
    
    CHECK_RESULT=$?
    if [ $CHECK_RESULT -ne 0 ]; then
        echo "🔄 Восстанавливаю структуру БД..."
        if [ -f "create_tables.py" ]; then
            python create_tables.py
        else
            echo "❌ Файл create_tables.py не найден, БД может быть повреждена"
        fi
    fi
fi

# 4. Запускаем Telegram бота в фоновом режиме
echo "🤖 Запускаю Telegram бота..."
if [ -f "run_bot.py" ]; then
    # Запускаем бота в фоне
    python run_bot.py &
    
    # Сохраняем PID бота
    BOT_PID=$!
    echo "📝 PID бота: $BOT_PID"
    
    # Ждем немного чтобы бот инициализировался
    echo "⏳ Жду инициализации бота (5 секунд)..."
    sleep 5
    
    # Проверяем запустился ли бот
    if ps -p $BOT_PID > /dev/null; then
        echo "✅ Бот успешно запущен (PID: $BOT_PID)"
    else
        echo "⚠️ Бот, возможно, не запустился, продолжаю запуск веб-сервера..."
    fi
else
    echo "⚠️ Файл run_bot.py не найден, пропускаю запуск бота"
    BOT_PID=""
fi

# 5. Запускаем веб-сервер
echo "🌐 Запуск веб-сервера..."

# Устанавливаем порт по умолчанию если не задан
if [ -z "$PORT" ]; then
    PORT=10000
    echo "🔌 Порт не задан, использую порт по умолчанию: $PORT"
else
    echo "🔌 Использую порт: $PORT"
fi

# Запускаем Gunicorn
echo "🚀 Запускаю Gunicorn..."
exec gunicorn render_server:app \
    --bind 0.0.0.0:$PORT \
    --worker-class aiohttp.GunicornWebWorker \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --preload

# Примечание: exec заменяет текущий процесс, поэтому код после этой строки не выполнится
# Если веб-сервер упадет, скрипт завершится

# (Этот код никогда не выполнится из-за exec выше, но оставляю для понимания логики)
if [ ! -z "$BOT_PID" ]; then
    echo "🛑 Останавливаю бота..."
    kill $BOT_PID 2>/dev/null
fi

echo "👋 Завершение работы"
