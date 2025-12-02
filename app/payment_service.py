import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import User, Payment
from app.price_service import price_service

logger = logging.getLogger(__name__)

class PaymentService:
    def __init__(self):
        # Теперь цены берутся из price_service
        pass

    def get_prices(self):
        """Получить текущие цены"""
        return price_service.get_all_packages()

    def create_payment(self, db: Session, user_id: int, payment_type: str) -> Payment:
        """Создание записи о платеже в БД - ВРЕМЕННО НЕДОСТУПНО"""
        # Платежи временно отключены
        return None

    def complete_payment_by_id(self, db: Session, payment_id: int) -> bool:
        """Завершение платежа по ID - ВРЕМЕННО НЕДОСТУПНО"""
        return False

    def can_reveal_sender(self, user: User) -> bool:
        """Может ли пользователь раскрыть отправителя"""
        return user.available_reveals > 0

    def use_reveal(self, db: Session, user: User) -> bool:
        """Использовать одно раскрытие"""
        if user.available_reveals > 0:
            user.available_reveals -= 1
            db.commit()
            return True
        return False

    def set_reveals(self, db: Session, user_id: int, new_count: int) -> bool:
        """Установить количество раскрытий"""
        try:
            if new_count < 0:
                return False
                
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False

            user.available_reveals = new_count
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка установки раскрытий: {e}")
            db.rollback()
            return False

# Создаем экземпляр сервиса
payment_service = PaymentService()
