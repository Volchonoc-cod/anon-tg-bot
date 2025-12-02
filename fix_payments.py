#!/usr/bin/env python3
"""
Скрипт для отключения платежной системы и изменения цен
"""

import os
import sys

# Файлы для изменения
files_to_fix = {
    'payment_service.py': '''
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import User, Payment

logger = logging.getLogger(__name__)

class PaymentService:
    def __init__(self):
        self.prices = {
            "reveal_1": 1599,     # 15.99₽ за 1 раскрытие (ИЗМЕНЕНО)
            "reveal_10": 9999,   # 99.99₽ за 10 раскрытий
            "reveal_30": 19999,  # 199.99₽ за 30 раскрытий
            "reveal_50": 31999   # 319.99₽ за 50 раскрытий
        }

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
''',

    'payment_handlers.py': '''
from aiogram import F, Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.orm import Session
import asyncio
from datetime import datetime
from app.database import get_db
from app.models import User, Payment
from app.keyboards import premium_menu, main_menu
from app.payment_service import payment_service
from app.config import ADMIN_IDS

import logging
logger = logging.getLogger(__name__)

router = Router()

class PaymentStates(StatesGroup):
    waiting_payment = State()

def is_admin(user_id: int):
    return user_id in ADMIN_IDS

@router.message(Command("premium"))
@router.message(F.text == "💰 Платные функции")
async def show_premium_menu(message: types.Message):
    db = next(get_db())
    try:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        text = (
            f"💰 <b>Покупка раскрытий</b>\n\n"
            f"📊 <b>Ваш статус:</b>\n"
            f"👁️ <b>Доступные раскрытия:</b> {user.available_reveals}\n\n"
            f"<b>Доступные пакеты:</b>\n"
            f"• 👁️ 1 раскрытие - 15.99₽\n"
            f"• 👁️ 10 раскрытий - 99.99₽\n"
            f"• 👁️ 30 раскрытий - 199.99₽\n"
            f"• 👁️ 50 раскрытий - 319.99₽\n\n"
            f"<b>⚠️ ВНИМАНИЕ:</b>\n"
            f"Платежная система временно недоступна.\n"
            f"Для покупки раскрытий напишите администратору: @Gikkie"
        )

        await message.answer(text, parse_mode="HTML", reply_markup=premium_menu())
    finally:
        db.close()

# Обработчики кнопок покупки - ВРЕМЕННО ОТКЛЮЧЕНЫ
@router.callback_query(F.data == "buy_reveal_1")
async def buy_reveal_1_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "⚠️ <b>Платежная система временно недоступна</b>\n\n"
        "Для покупки раскрытий напишите администратору:\n"
        "👤 @Gikkie\n\n"
        "Укажите:\n"
        "• Ваш Telegram ID\n" 
        "• Количество раскрытий\n"
        "• Способ оплаты",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "buy_reveal_10")
async def buy_reveal_10_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "⚠️ <b>Платежная система временно недоступна</b>\n\n"
        "Для покупки раскрытий напишите администратору:\n"
        "👤 @Gikkie\n\n"
        "Укажите:\n"
        "• Ваш Telegram ID\n" 
        "• Количество раскрытий\n"
        "• Способ оплаты",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "buy_reveal_30")
async def buy_reveal_30_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "⚠️ <b>Платежная система временно недоступна</b>\n\n"
        "Для покупки раскрытий напишите администратору:\n"
        "👤 @Gikkie\n\n"
        "Укажите:\n"
        "• Ваш Telegram ID\n" 
        "• Количество раскрытий\n"
        "• Способ оплаты",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "buy_reveal_50")
async def buy_reveal_50_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "⚠️ <b>Платежная система временно недоступна</b>\n\n"
        "Для покупки раскрытий напишите администратору:\n"
        "👤 @Gikkie\n\n"
        "Укажите:\n"
        "• Ваш Telegram ID\n" 
        "• Количество раскрытий\n"
        "• Способ оплаты",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "my_status")
async def show_my_status(callback: types.CallbackQuery):
    db = next(get_db())
    try:
        user = db.query(User).filter(User.telegram_id == callback.from_user.id).first()
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return

        text = (
            f"📊 <b>Ваш статус</b>\n\n"
            f"👤 {user.first_name}\n"
            f"👁️ Доступные раскрытия: {user.available_reveals}\n"
            f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y')}\n\n"
            f"💡 <b>Для покупки раскрытий:</b>\n"
            f"Напишите @Gikkie"
        )

        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=premium_menu())
        await callback.answer()
    finally:
        db.close()

@router.callback_query(F.data == "back_to_main")
async def back_to_main_from_premium(callback: types.CallbackQuery):
    await callback.message.answer("Главное меню:", reply_markup=main_menu())
    await callback.answer()

# Отключаем проверку платежей
@router.callback_query(F.data == "check_payment")
async def check_payment_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "⚠️ <b>Платежная система временно недоступна</b>\n\n"
        "Для покупки раскрытий напишите администратору:\n"
        "👤 @Gikkie",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "cancel_payment")
async def cancel_payment_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Оплата отменена")
    await state.clear()
    await callback.answer()
''',

    'admin_handlers.py': '''
# Добавь этот код в существующий файл admin_handlers.py
# Добавь эту команду в существующий файл:

@router.message(Command("payment_status"))
async def payment_status_command(message: types.Message):
    """Статус платежной системы"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    text = (
        "🔄 <b>Статус платежной системы</b>\n\n"
        "❌ <b>Автоматические платежи отключены</b>\n\n"
        "📋 <b>Недоступные функции:</b>\n"
        "• Автоматическая оплата через ЮMoney\n"
        "• Автоматическое подтверждение платежей\n"
        "• Уведомления о новых платежах\n"
        "• Проверка статуса платежей\n\n"
        "✅ <b>Доступные функции:</b>\n"
        "• Ручная установка раскрытий (/set_reveals)\n"
        "• Информация о пользователях (/user_info)\n"
        "• Статистика платежей\n\n"
        "💡 <b>Рекомендации:</b>\n"
        "Для продажи раскрытий используйте команду:\n"
        "<code>/set_reveals ID_пользователя количество</code>\n\n"
        "Пользователи видят сообщение о необходимости\n"
        "написать @Gikkie для покупки раскрытий."
    )

    await message.answer(text, parse_mode="HTML")
'''
}

def apply_fixes():
    """Применить все исправления"""
    print("🔄 Применяю исправления...")
    
    for filename, content in files_to_fix.items():
        filepath = f"app/{filename}"
        
        if filename == 'admin_handlers.py':
            # Для admin_handlers.py добавляем команду, а не перезаписываем весь файл
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write('\n\n' + content)
            print(f"✅ Добавлена команда в {filename}")
        else:
            # Для других файлов перезаписываем
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Обновлен {filename}")
    
    print("🎉 Все исправления применены!")
    print("\n📋 Изменения:")
    print("• Цена 1 раскрытия изменена на 15.99₽")
    print("• Платежная система отключена")
    print("• Пользователи видят сообщение о @Gikkie")
    print("• Добавлена команда /payment_status для админа")
    print("• Функция установки раскрытий осталась рабочей")

if __name__ == "__main__":
    apply_fixes()
