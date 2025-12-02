import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import User

logger = logging.getLogger(__name__)

class PriceService:
    def __init__(self):
        # Базовая структура цен
        self.packages = {
            "reveal_1": {
                "name": "1 раскрытие",
                "base_price": 1599,  # 15.99₽
                "current_price": 1599,
                "discount": 0,
                "discount_end": None,
                "active": True
            },
            "reveal_10": {
                "name": "10 раскрытий", 
                "base_price": 9999,   # 99.99₽
                "current_price": 9999,
                "discount": 0,
                "discount_end": None,
                "active": True
            },
            "reveal_30": {
                "name": "30 раскрытий",
                "base_price": 19999,  # 199.99₽
                "current_price": 19999,
                "discount": 0,
                "discount_end": None,
                "active": True
            },
            "reveal_50": {
                "name": "50 раскрытий", 
                "base_price": 31999,  # 319.99₽
                "current_price": 31999,
                "discount": 0,
                "discount_end": None,
                "active": True
            }
        }

    def get_package_info(self, package_id: str):
        """Получить информацию о пакете"""
        return self.packages.get(package_id)

    def get_all_packages(self):
        """Получить все пакеты"""
        return self.packages

    def update_price(self, package_id: str, new_price: int):
        """Обновить цену пакета"""
        if package_id in self.packages:
            self.packages[package_id]["base_price"] = new_price
            self.packages[package_id]["current_price"] = new_price
            self.packages[package_id]["discount"] = 0
            self.packages[package_id]["discount_end"] = None
            return True
        return False

    def set_discount(self, package_id: str, discount_percent: int, days: int = 7):
        """Установить скидку на пакет"""
        if package_id in self.packages:
            package = self.packages[package_id]
            discount_amount = int(package["base_price"] * discount_percent / 100)
            package["current_price"] = package["base_price"] - discount_amount
            package["discount"] = discount_percent
            package["discount_end"] = datetime.now() + timedelta(days=days)
            return True
        return False

    def add_new_package(self, package_id: str, name: str, price: int):
        """Добавить новый пакет"""
        if package_id not in self.packages:
            self.packages[package_id] = {
                "name": name,
                "base_price": price,
                "current_price": price,
                "discount": 0,
                "discount_end": None,
                "active": True
            }
            return True
        return False

    def toggle_package(self, package_id: str):
        """Включить/выключить пакет"""
        if package_id in self.packages:
            self.packages[package_id]["active"] = not self.packages[package_id]["active"]
            return True
        return False

    def format_price(self, price: int):
        """Форматировать цену в рубли"""
        return f"{price / 100:.2f}₽"

    def get_price_text(self):
        """Получить текст для отображения цен"""
        text = "🎯 <b>Текущие цены:</b>\n\n"
        
        for package_id, package in self.packages.items():
            if package["active"]:
                price_text = self.format_price(package["current_price"])
                base_price_text = self.format_price(package["base_price"])
                
                if package["discount"] > 0:
                    text += f"• {package['name']} - <b>{price_text}</b> "
                    text += f"<s>{base_price_text}</s> "
                    text += f"<b>(-{package['discount']}%)</b>\n"
                else:
                    text += f"• {package['name']} - <b>{price_text}</b>\n"
        
        return text

# Глобальный экземпляр
price_service = PriceService()
