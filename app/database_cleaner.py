import os
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AnonMessage, Payment
from app.backup_service import backup_service


class DatabaseCleaner:
    def __init__(self):
        self.keep_messages_days = 90  # Храним сообщения 90 дней
        self.keep_payments_days = 365  # Храним платежи 1 год

    async def cleanup_old_data(self):
        """Автоматическая очистка старых данных"""
        db = next(get_db())
        try:
            # Удаляем старые сообщения
            messages_cutoff = datetime.utcnow() - timedelta(days=self.keep_messages_days)
            deleted_messages = db.query(AnonMessage).filter(
                AnonMessage.timestamp < messages_cutoff
            ).delete()

            # Удаляем старые pending платежи (старше 7 дней)
            payments_cutoff = datetime.utcnow() - timedelta(days=7)
            deleted_payments = db.query(Payment).filter(
                Payment.status == "pending",
                Payment.created_at < payments_cutoff
            ).delete()

            db.commit()

            # Логируем результат
            if deleted_messages > 0 or deleted_payments > 0:
                print(f"🗑️ Очистка: удалено {deleted_messages} сообщений, {deleted_payments} платежей")

                # Отправляем уведомление админу
                await self.send_cleanup_notification(deleted_messages, deleted_payments)

            return deleted_messages, deleted_payments

        except Exception as e:
            db.rollback()
            print(f"❌ Ошибка очистки базы: {e}")
            return 0, 0
        finally:
            db.close()

    async def send_cleanup_notification(self, messages_count, payments_count):
        """Уведомление о очистке"""
        from aiogram import Bot
        from app.config import BOT_TOKEN, ADMIN_IDS

        bot = Bot(token=BOT_TOKEN)
        message = (
            f"🧹 **Автоматическая очистка базы**\n\n"
            f"• Удалено сообщений: {messages_count}\n"
            f"• Удалено платежей: {payments_count}\n"
            f"• Новый размер: {backup_service.get_db_size():.2f} MB"
        )

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, message, parse_mode="Markdown")
            except Exception as e:
                print(f"❌ Ошибка уведомления админа: {e}")


# Глобальный экземпляр
db_cleaner = DatabaseCleaner()