import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class YooMoneyService:
    def __init__(self):
        # Виртуальная карта ЮMoney (пример: 5559 49** **** 1234)
        # Чтобы получить свою виртуальную карту:
        # 1. Откройте ЮMoney
        # 2. Нажмите "Карты" 
        # 3. Создайте виртуальную карту
        # 4. Скопируйте номер карты
        self.card_number = "5599002125128696"  # ЗАМЕНИТЕ на ваш номер карты
        self.wallet = "4100119410595188"

    async def create_payment(self, amount: float, label: str, description: str = "") -> Dict[str, Any]:
        """Создание платежа - возвращаем данные для перевода"""
        try:
            payment_data = {
                "payment_id": f"card_{label}",
                "amount": amount,
                "status": "pending",
                "card_number": self.card_number,
                "wallet_number": self.wallet,
                "label": label,
                "description": description
            }
            
            logger.info(f"✅ Создан платеж: {amount} руб, карта: {self.card_number}")
            return payment_data
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания платежа: {e}")
            return {}

    async def check_payment_status(self, label: str) -> Dict[str, Any]:
        """Проверка статуса платежа (админ проверяет вручную)"""
        return {
            "paid": False,
            "status": "pending", 
            "label": label
        }

# Создаем экземпляр сервиса
yookassa_service = YooMoneyService()
