import requests
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ BOT_TOKEN не найден!")
    exit()

url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"

try:
    print("🔄 Тестируем подключение к Telegram API...")
    response = requests.get(url, timeout=30)
    print(f"✅ Status: {response.status_code}")
    print(f"✅ Response: {response.text}")
except Exception as e:
    print(f"❌ Error: {e}")
