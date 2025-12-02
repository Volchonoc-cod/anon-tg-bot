from aiogram.filters import Command
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, AnonMessage
from app.keyboards import premium_menu, main_menu
from app.payment_service import payment_service
from app.config import ADMIN_IDS

router = Router()

class PaymentStates(StatesGroup):
    waiting_payment = State()

def is_admin(user_id: int):
    return user_id in ADMIN_IDS

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

@router.message(Command("premium"))
@router.message(F.text == "💰 Платные функции")
async def premium_menu_handler(message: types.Message):
    await show_premium_menu(message)

# Обработчики кнопок покупки - ВРЕМЕННО ОТКЛЮЧЕНЫ
@router.callback_query(F.data == "buy_reveal_1")
async def buy_reveal_1_handler(callback: types.CallbackQuery):
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
async def buy_reveal_10_handler(callback: types.CallbackQuery):
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
async def buy_reveal_30_handler(callback: types.CallbackQuery):
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
async def buy_reveal_50_handler(callback: types.CallbackQuery):
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

@router.callback_query(F.data == "user_info")
async def show_user_info(callback: types.CallbackQuery):
    """Обработчик кнопки 'Информация о себе'"""
    db = next(get_db())
    try:
        user = db.query(User).filter(User.telegram_id == callback.from_user.id).first()
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return

        # Статистика пользователя
        total_received = db.query(AnonMessage).filter(AnonMessage.receiver_id == user.id).count()
        total_sent = db.query(AnonMessage).filter(AnonMessage.sender_id == user.id).count()
        
        reg_date = user.created_at.strftime('%d.%m.%Y в %H:%M')
        
        text = (
            f"👤 <b>Информация о вас</b>\n\n"
            f"🆔 <b>Telegram ID:</b> <code>{user.telegram_id}</code>\n"
            f"👤 <b>Имя:</b> {user.first_name}\n"
            f"🏷️ <b>Username:</b> @{user.username if user.username else 'не указан'}\n"
            f"📅 <b>Регистрация:</b> {reg_date}\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"• 👁️ Доступные раскрытия: <b>{user.available_reveals}</b>\n"
            f"• 📨 Получено сообщений: <b>{total_received}</b>\n"
            f"• 📤 Отправлено сообщений: <b>{total_sent}</b>\n"
            f"• 🔗 Анонимная ссылка: {'✅ Активна' if user.anon_link_uid else '❌ Не создана'}\n\n"
            f"💡 <b>Для управления профилем</b> используйте главное меню"
        )

        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=premium_menu())
        await callback.answer()
    finally:
        db.close()

@router.callback_query(F.data == "back_to_main")
async def back_to_main_from_premium(callback: types.CallbackQuery):
    await callback.message.answer("Главное меню:", reply_markup=main_menu())
    await callback.answer()

@router.callback_query(F.data == "check_payment")
async def check_payment_handler(callback: types.CallbackQuery):
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
