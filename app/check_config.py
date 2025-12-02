import os
from dotenv import load_dotenv


def check_config():
    load_dotenv()

    print("🔍 Проверка конфигурации...")

    # Проверяем файл .env
    if not os.path.exists('../.env'):
        print("❌ Файл .env не найден!")
        return False

    # Проверяем токен
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("❌ BOT_TOKEN не найден в .env")
        return False

    if token == "your_actual_bot_token_here":
        print("❌ Вы не заменили BOT_TOKEN на реальный токен!")
        return False

    if ":" not in token:
        print("❌ Неверный формат BOT_TOKEN")
        return False

    print(f"✅ BOT_TOKEN: {token[:10]}...")
    print(f"✅ ADMIN_IDS: {os.getenv('ADMIN_IDS')}")
    print(f"✅ DATABASE_URL: {os.getenv('DATABASE_URL')}")

    return True


if __name__ == "__main__":
    if check_config():
        print("\n🎉 Конфигурация в порядке! Можно запускать бота.")
    else:
        print("\n💥 Проблемы с конфигурацией! Смотрите выше.")
