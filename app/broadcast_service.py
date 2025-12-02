import logging
import asyncio
from sqlalchemy.orm import Session
from aiogram import Bot
from app.database import get_db
from app.models import User

logger = logging.getLogger(__name__)

class BroadcastService:
    def __init__(self):
        self.bot = None

    def set_bot(self, bot: Bot):
        """Установить бота для рассылки"""
        self.bot = bot

    async def broadcast_to_all(self, message_text: str, admin_id: int):
        """Рассылка сообщения всем пользователям"""
        if not self.bot:
            return {"success": 0, "failed": 0, "total": 0, "error": "Бот не инициализирован"}

        db = next(get_db())
        try:
            users = db.query(User).all()
            total = len(users)
            success = 0
            failed = 0
            
            # Отправляем уведомление админу о начале рассылки
            await self.bot.send_message(
                admin_id,
                f"📢 <b>Начинаю рассылку</b>\n\n"
                f"👥 Получателей: {total}\n"
                f"📝 Сообщение: {message_text[:100]}...",
                parse_mode="HTML"
            )

            # Рассылка с задержкой чтобы не превысить лимиты Telegram
            for user in users:
                try:
                    await self.bot.send_message(
                        user.telegram_id,
                        f"📢 <b>Важное сообщение от администратора:</b>\n\n{message_text}",
                        parse_mode="HTML"
                    )
                    success += 1
                    
                    # Задержка между сообщениями
                    if success % 10 == 0:  # Каждые 10 сообщений
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    failed += 1
                    logger.error(f"❌ Ошибка отправки пользователю {user.telegram_id}: {e}")

            # Отчет админу
            report = (
                f"📊 <b>Рассылка завершена</b>\n\n"
                f"✅ Успешно: {success}\n"
                f"❌ Ошибок: {failed}\n"
                f"👥 Всего: {total}\n"
                f"📈 Успех: {(success/total)*100:.1f}%"
            )
            
            await self.bot.send_message(admin_id, report, parse_mode="HTML")
            
            return {
                "success": success,
                "failed": failed, 
                "total": total,
                "error": None
            }

        except Exception as e:
            logger.error(f"❌ Ошибка рассылки: {e}")
            return {"success": 0, "failed": 0, "total": 0, "error": str(e)}
        finally:
            db.close()

    async def send_to_user(self, telegram_id: int, message_text: str, admin_id: int):
        """Отправка сообщения конкретному пользователю"""
        if not self.bot:
            return False

        try:
            await self.bot.send_message(
                telegram_id,
                f"📢 <b>Сообщение от администратора:</b>\n\n{message_text}",
                parse_mode="HTML"
            )
            
            # Уведомление админу об успешной отправке
            await self.bot.send_message(
                admin_id,
                f"✅ Сообщение отправлено пользователю {telegram_id}",
                parse_mode="HTML"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки пользователю {telegram_id}: {e}")
            await self.bot.send_message(
                admin_id,
                f"❌ Не удалось отправить сообщение пользователю {telegram_id}\nОшибка: {e}",
                parse_mode="HTML"
            )
            return False

# Глобальный экземпляр
broadcast_service = BroadcastService()
