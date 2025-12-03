#!/bin/bash
# build.sh - скрипт сборки для Render

echo "🚀 Начало сборки на Render..."

# Установка pip
pip install --upgrade pip

# Установка зависимостей
pip install -r requirements.txt

echo "✅ Зависимости установлены"
