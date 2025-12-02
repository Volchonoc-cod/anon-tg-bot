#!/usr/bin/env python3
import os
import sys

# Добавляем путь к проекту
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

print("🔍 Тестируем конфигурацию...")

try:
    from app.config import BOT_TOKEN, ADMIN_IDS
    print(f"✅ BOT_TOKEN: {BOT_TOKEN[:10]}...")
    print(f"✅ ADMIN_IDS: {ADMIN_IDS}")
    print("✅ Конфигурация загружена успешно!")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
