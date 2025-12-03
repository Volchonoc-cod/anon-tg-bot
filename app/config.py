import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения! Проверьте файл .env")

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

# Настройки БД
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/bot.db")

# Настройки ЮMoney
YOOMONEY_TOKEN = os.getenv("YOOMONEY_TOKEN")
YOOMONEY_WALLET = os.getenv("YOOMONEY_WALLET")  # Номер кошелька 4100...
BOT_USERNAME = "SShadowMaskBot"  # Или получите динамически

# Вывод информации о конфигурации
print(f"✅ Конфигурация загружена: Bot Token = {BOT_TOKEN[:10]}...")
print(f"✅ Админы: {ADMIN_IDS}")
print(f"✅ База данных: {DATABASE_URL}")
print(f"✅ ЮMoney кошелек: {YOOMONEY_WALLET}")

IS_RENDER = bool(os.getenv("RENDER"))
PORT = int(os.getenv("PORT", 8080))

print(f"✅ Конфигурация загружена")
print(f"✅ Админы: {len(ADMIN_IDS)}")
print(f"✅ Render: {IS_RENDER}")
print(f"✅ Порт: {PORT}")
