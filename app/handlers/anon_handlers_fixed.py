import uuid
from aiogram import F, Router, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, AnonMessage
from app.keyboards import main_menu, message_actions_keyboard, recreate_link_keyboard, profile_menu, send_another_message_keyboard
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

        await message.answer(welcome_text, reply_markup=main_menu())
    finally:
        db.close()

@router.message(F.text == "🔗 Моя ссылка")
async def show_my_link(message: Message):
    db = next(get_db())
    try:
        user = anon_service.get_or_create_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        if not user.anon_link_uid:
            user.anon_link_uid = str(uuid.uuid4())[:8]
            db.commit()

        bot_info = await message.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={user.anon_link_uid}"

        await message.answer(
            f"🔗 **Ваша анонимная ссылка:**\n\n"
            f"`{link}`\n\n"
            f"📤 Отправьте эту ссылку друзьям, чтобы получать анонимные сообщения!",
            parse_mode="Markdown"
        )
    finally:
        db.close()

@router.message(F.text == "👁️ Раскрыть отправителя")
async def reveal_sender_menu(message: Message):
    await message.answer(
        "👁️ **Раскрытие отправителя**\n\n"
        "Чтобы раскрыть отправителя:\n"
        "1. Перейдите в чат с ботом\n"
        "2. Найдите сообщение, отправителя которого хотите раскрыть\n"
        "3. Нажмите кнопку \"👁️ Раскрыть отправителя\" под этим сообщением\n\n"
        "💡 Можно раскрыть отправителя любого полученного анонимного сообщения!"
    )

@router.message(F.text.startswith("/start "))
async def handle_anon_link(message: Message, state: FSMContext):
    link_uid = message.text.split(" ")[1] if len(message.text.split(" ")) > 1 else None

    if not link_uid:
        await cmd_start(message)
        return

    db = next(get_db())
    try:
        target_user = db.query(User).filter(User.anon_link_uid == link_uid).first()
        if not target_user:
            await message.answer("❌ Ссылка недействительна")
            return

        current_user = anon_service.get_or_create_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
        if current_user and current_user.id == target_user.id:
            await message.answer("❌ Нельзя отправлять сообщения самому себе")
            return

        await state.update_data(
            target_user_id=target_user.id,
            target_user_name=target_user.first_name
        )
        await state.set_state(AnonStates.waiting_for_message)

        await message.answer(
            f"💌 Вы пишете анонимное сообщение для *{target_user.first_name}*\n\n"
            f"📝 Введите ваше сообщение:",
            parse_mode="Markdown"
        )
    finally:
        db.close()

@router.message(AnonStates.waiting_for_message)
async def send_anon_message(message: Message, state: FSMContext):
    if not message.text or message.text.strip() == "":
        await message.answer("❌ Сообщение не может быть пустым. Введите текст сообщения:")
        return

    user_data = await state.get_data()
    target_user_id = user_data.get('target_user_id')
    target_user_name = user_data.get('target_user_name')

    if not target_user_id:
        await message.answer("❌ Ошибка: получатель не найден")
        await state.clear()
        return

    db = next(get_db())
    try:
        sender = anon_service.get_or_create_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
        if not sender:
            await message.answer("❌ Ошибка отправителя")
            await state.clear()
            return

        anon_message = AnonMessage(
            sender_id=sender.id,
            receiver_id=target_user_id,
            text=message.text,
            is_anonymous=True
        )
        db.add(anon_message)
        db.commit()
        db.refresh(anon_message)

        target_user = db.query(User).filter(User.id == target_user_id).first()
        try:
            await message.bot.send_message(
                target_user.telegram_id,
                f"💌 Вам анонимное сообщение:\n\n{message.text}",
                reply_markup=message_actions_keyboard(anon_message.id)
            )
            
            # ОТПРАВЛЯЕМ ПОДТВЕРЖДЕНИЕ С КНОПКОЙ "НАПИСАТЬ ЕЩЕ"
            await message.answer(
                "✅ Сообщение отправлено анонимно!",
                reply_markup=send_another_message_keyboard(target_user.anon_link_uid)
            )
        except Exception as e:
            await message.answer("❌ Не удалось отправить сообщение. Возможно, пользователь заблокировал бота.")

        await state.clear()
    finally:
        db.close()

@router.callback_query(F.data.startswith("send_another_"))
async def send_another_message(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Написать еще сообщение'"""
    target_link_uid = callback.data.replace("send_another_", "")
    
    db = next(get_db())
    try:
        target_user = db.query(User).filter(User.anon_link_uid == target_link_uid).first()
        if not target_user:
            await callback.answer("❌ Пользователь не найден")
            return

        await state.update_data(
            target_user_id=target_user.id,
            target_user_name=target_user.first_name
        )
        await state.set_state(AnonStates.waiting_for_message)

        await callback.message.answer(
            f"💌 Вы снова пишете анонимное сообщение для *{target_user.first_name}*\n\n"
            f"📝 Введите ваше сообщение:",
            parse_mode="Markdown"
        )
        await callback.answer()
    finally:
        db.close()

@router.callback_query(F.data.startswith("reply_"))
async def start_reply(callback: CallbackQuery, state: FSMContext):
    message_id = int(callback.data.split("_")[1])

    db = next(get_db())
    try:
        original_message = db.query(AnonMessage).filter(AnonMessage.id == message_id).first()
        if not original_message:
            await callback.answer("❌ Сообщение не найдено")
            return

        current_user = anon_service.get_or_create_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name, callback.from_user.last_name)
        if not current_user:
            await callback.answer("❌ Пользователь не найден")
            return

        if current_user.id != original_message.receiver_id:
            await callback.answer("❌ Вы не можете ответить на это сообщение")
            return

        if original_message.sender_id == current_user.id:
            await callback.answer("❌ Нельзя отвечать на свои собственные сообщения")
            return

        await state.update_data(
            replying_to_message_id=message_id,
            reply_receiver_id=original_message.sender_id,
            original_message_text=original_message.text
        )
        await state.set_state(AnonStates.waiting_for_reply)

        await callback.message.answer(
            f"💬 **Ответ на сообщение:**\n\n"
            f"📝 *{original_message.text[:200]}...*\n\n"
            f"✏️ Введите ваш ответ:",
            parse_mode="Markdown"
        )
        await callback.answer()
    finally:
        db.close()

@router.message(AnonStates.waiting_for_reply)
async def send_reply_message(message: Message, state: FSMContext):
    if not message.text or message.text.strip() == "":
        await message.answer("❌ Ответ не может быть пустым. Введите текст ответа:")
        return

    user_data = await state.get_data()
    reply_to_id = user_data.get('replying_to_message_id')
    receiver_id = user_data.get('reply_receiver_id')
    original_text = user_data.get('original_message_text')

    if not reply_to_id or not receiver_id:
        await message.answer("❌ Ошибка: данные ответа не найдены")
        await state.clear()
        return

    db = next(get_db())
    try:
        receiver_user = db.query(User).filter(User.id == receiver_id).first()
        if not receiver_user:
            await message.answer("❌ Пользователь не найден")
            await state.clear()
            return

        sender = anon_service.get_or_create_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
        if not sender:
            await message.answer("❌ Ошибка отправителя")
            await state.clear()
            return

        new_message = AnonMessage(
            sender_id=sender.id,
            receiver_id=receiver_id,
            text=message.text,
            reply_to_message_id=reply_to_id,
            is_anonymous=True
        )

        db.add(new_message)
        db.commit()
        db.refresh(new_message)

        try:
            await message.bot.send_message(
                receiver_user.telegram_id,
                f"💌 Вам ответ на ваше сообщение:\n\n"
                f"📝 *{original_text[:100]}...*\n\n"
                f"💬 **Ответ:** {message.text}",
                parse_mode="Markdown",
                reply_markup=message_actions_keyboard(new_message.id)
            )
            await message.answer("✅ Ответ отправлен!")
        except Exception as e:
            await message.answer("❌ Не удалось отправить ответ. Возможно, пользователь заблокировал бота.")

        await state.clear()
    finally:
        db.close()

@router.callback_query(F.data.startswith("reveal_"))
async def reveal_sender(callback: CallbackQuery):
    message_id = int(callback.data.split("_")[1])

    db = next(get_db())
    try:
        message_obj = db.query(AnonMessage).filter(AnonMessage.id == message_id).first()
        if not message_obj:
            await callback.answer("❌ Сообщение не найдено")
            return

        current_user = anon_service.get_or_create_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name, callback.from_user.last_name)
        if not current_user or current_user.id != message_obj.receiver_id:
            await callback.answer("❌ Вы не можете раскрыть отправителя этого сообщения")
            return

        if not message_obj.sender:
            await callback.answer("❌ Информация об отправителе недоступна")
            return

        if not payment_service.can_reveal_sender(current_user):
            await callback.answer("❌ Недостаточно средств для раскрытия. Купите в платных функциях.")
            return

        if not payment_service.use_reveal(db, current_user):
            await callback.answer("❌ Ошибка при использовании раскрытия")
            return

        message_obj.is_revealed = True
        db.commit()

        sender_info = f"👤 {message_obj.sender.first_name}"
        if message_obj.sender.username:
            sender_info += f" (@{message_obj.sender.username})"

        await callback.message.edit_text(
            f"👁️ **Отправитель раскрыт:**\n\n"
            f"{message_obj.text}\n\n"
            f"**От:** {sender_info}",
            reply_markup=message_actions_keyboard(message_id, can_reveal=False)
        )
        await callback.answer("👤 Отправитель раскрыт")
    finally:
        db.close()

@router.callback_query(F.data.startswith("report_"))
async def report_message(callback: CallbackQuery):
    message_id = int(callback.data.split("_")[1])

    db = next(get_db())
    try:
        message_obj = db.query(AnonMessage).filter(AnonMessage.id == message_id).first()
        if not message_obj:
            await callback.answer("❌ Сообщение не найдено")
            return

        message_obj.is_reported = True
        db.commit()

        for admin_id in ADMIN_IDS:
            try:
                await callback.bot.send_message(
                    admin_id,
                    f"🚨 **Жалоба на сообщение**\n\n"
                    f"ID сообщения: {message_id}\n"
                    f"Текст: {message_obj.text[:200]}...\n"
                    f"Отправитель: {message_obj.sender.first_name if message_obj.sender else 'Неизвестен'}\n"
                    f"Получатель: {message_obj.receiver.first_name}"
                )
            except Exception:
                continue

        await callback.answer("🚫 Жалоба отправлена администраторам")
    finally:
        db.close()

@router.message(F.text == "🔄 Пересоздать ссылку")
async def recreate_link(message: Message):
    db = next(get_db())
    try:
        user = anon_service.get_or_create_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        await message.answer(
            "⚠️ **Внимание!**\n\n"
            "При пересоздании ссылки:\n"
            "• Старая ссылка перестанет работать\n"
            "• Новая ссылка будет создана\n"
            "• История сообщений сохранится\n\n"
            "Вы уверены, что хотите пересоздать ссылку?",
            reply_markup=recreate_link_keyboard()
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
            f"✅ **Новая ссылка создана!**\n\n"
            f"🔗 Ваша новая анонимная ссылка:\n\n"
            f"`{new_link}`\n\n"
            f"📤 Старая ссылка больше не работает!",
            parse_mode="Markdown"
        )
        await callback.answer()
    finally:
        db.close()

@router.callback_query(F.data == "recreate_link_cancel")
async def cancel_recreate_link(callback: CallbackQuery):
    await delete_previous_messages(callback)
    
    await callback.message.answer("❌ Пересоздание ссылки отменено")
    await callback.answer()

@router.message(F.text == "📊 Мой профиль")
async def show_my_profile(message: Message):
    db = next(get_db())
    try:
        user = anon_service.get_or_create_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        total_received = db.query(AnonMessage).filter(AnonMessage.receiver_id == user.id).count()
        total_sent = db.query(AnonMessage).filter(AnonMessage.sender_id == user.id).count()
        
        reg_date = user.created_at.strftime('%d.%m.%Y в %H:%M')
        
        text = (
            f"👤 <b>Ваш профиль</b>\n\n"
            f"🆔 <b>Telegram ID:</b> <code>{user.telegram_id}</code>\n"
            f"👤 <b>Имя:</b> {user.first_name}\n"
            f"🏷️ <b>Username:</b> @{user.username if user.username else 'не указан'}\n"
            f"📅 <b>Регистрация:</b> {reg_date}\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"• 👁️ Доступные раскрытия: <b>{user.available_reveals}</b>\n"
            f"• 📨 Получено сообщений: <b>{total_received}</b>\n"
            f"• 📤 Отправлено сообщений: <b>{total_sent}</b>\n"
            f"• 🔗 Анонимная ссылка: {'✅ Активна' if user.anon_link_uid else '❌ Не создана'}\n\n"
            f"💡 <b>Управление профилем:</b>\n"
            f"Используйте кнопки ниже для управления настройками"
        )

        await message.answer(text, parse_mode="HTML", reply_markup=profile_menu())
    finally:
        db.close()


