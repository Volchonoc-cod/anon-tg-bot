import uuid
from aiogram import F, Router, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, AnonMessage
from app.keyboards import main_menu, message_actions_keyboard, recreate_link_keyboard, profile_menu
from app.config import ADMIN_IDS
from app.payment_service import payment_service

router = Router()

class AnonStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_reply = State()

async def delete_previous_messages(callback: CallbackQuery):
    """Удалить предыдущее сообщение бота перед отправкой нового"""
    try:
        await callback.message.delete()
    except Exception as e:
        print(f"⚠️ Не удалось удалить сообщение: {e}")
        pass

from app.anon_service import anon_service

@router.message(F.text == "/start")
async def cmd_start(message: Message):
    db = next(get_db())
    try:
        user = anon_service.get_or_create_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
        
        welcome_text = (
            "👋 Добро пожаловать в ShadowTalk!\n\n"
            "🔗 **Моя ссылка** - отправьте ее друзьям, чтобы получать анонимные сообщения\n"
            "🔄 **Пересоздать ссылку** - создать новую ссылку (старая перестанет работать)\n"
            "👁️ **Раскрыть отправителя** - раскрыть отправителя полученного сообщения\n"
            "💰 **Платные функции** - покупка раскрытий\n"
            "📊 **Мой профиль** - информация о вашем аккаунте\n\n"
            "💡 Отправляйте сообщения другим, переходя по их анонимным ссылкам!"
        )

        await message.answer(
            "⚠️ <b>Внимание!</b>\n\n"
            "При пересоздании ссылки:\n"
            "• Старая ссылка перестанет работать\n"
            "• Новая ссылка будет создана\n"
            "• История сообщений сохранится\n\n"
            "Вы уверены, что хотите пересоздать ссылку?",
            parse_mode="HTML",
            reply_markup=recreate_link_keyboard()
        )
        )
    finally:
        db.close()

@router.callback_query(F.data == "recreate_link_confirm")
async def confirm_recreate_link(callback: CallbackQuery):
    await delete_previous_messages(callback)
    
    db = next(get_db())
    try:
        user = anon_service.get_or_create_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name, callback.from_user.last_name)
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return

        user.anon_link_uid = str(uuid.uuid4())[:8]
        db.commit()

        bot_info = await callback.bot.get_me()
        new_link = f"https://t.me/{bot_info.username}?start={user.anon_link_uid}"

        await callback.message.answer(
            f"✅ <b>Новая ссылка создана!</b>\n\n"
            f"🔗 <b>Ваша новая анонимная ссылка:</b>\n\n"
            f"<code>{new_link}</code>\n\n"
            f"📤 <b>Старая ссылка больше не работает!</b>",
            parse_mode="HTML"
        )
        )
        await callback.answer()
    finally:
        db.close()

@router.callback_query(F.data == "recreate_link_cancel")
async def cancel_recreate_link(callback: CallbackQuery):
    await delete_previous_messages(callback)
    
