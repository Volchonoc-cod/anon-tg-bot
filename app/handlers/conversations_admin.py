"""
Админ-панель для управления переписками пользователей
"""
from aiogram import F, Router, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Tuple, Optional
from sqlalchemy import text

from app.database import get_engine
from app.database_utils import safe_execute_query_fetchall, safe_execute_query_fetchone, safe_execute_scalar
from app.config import ADMIN_IDS
from app.keyboards_admin import admin_conversations_menu, admin_user_conversations_menu, admin_message_history_keyboard
from app.keyboards import main_menu

logger = logging.getLogger(__name__)

router = Router()

class ConversationStates(StatesGroup):
    waiting_user_search = State()
    waiting_conversation_select = State()

def is_admin(user_id: int):
    return user_id in ADMIN_IDS

def admin_filter(message: types.Message) -> bool:
    """Фильтр для админских команд"""
    return message.from_user.id in ADMIN_IDS

# ==================== МЕНЮ ПЕРЕПИСОК ====================

@router.message(F.text == "💬 Переписки")
async def admin_conversations(message: types.Message):
    """Главное меню переписок"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        # Получаем статистику по перепискам
        total_users_with_conversations = safe_execute_scalar(
            "SELECT COUNT(DISTINCT sender_id) + COUNT(DISTINCT receiver_id) FROM anon_messages WHERE sender_id IS NOT NULL"
        ) or 0
        
        total_conversations = safe_execute_scalar(
            """
            SELECT COUNT(DISTINCT CASE 
                WHEN sender_id < receiver_id THEN sender_id || '-' || receiver_id 
                ELSE receiver_id || '-' || sender_id 
            END)
            FROM anon_messages 
            WHERE sender_id IS NOT NULL AND receiver_id IS NOT NULL
            """
        ) or 0
        
        today_messages = safe_execute_scalar(
            "SELECT COUNT(*) FROM anon_messages WHERE DATE(timestamp) = DATE('now')"
        ) or 0
        
        week_messages = safe_execute_scalar(
            "SELECT COUNT(*) FROM anon_messages WHERE timestamp >= datetime('now', '-7 days')"
        ) or 0
        
        conversations_message = (
            "💬 <b>Управление переписками</b>\n\n"
            "📊 <b>Статистика переписок:</b>\n"
            f"• 👥 Пользователей с переписками: <b>{total_users_with_conversations}</b>\n"
            f"• 💬 Активных диалогов: <b>{total_conversations}</b>\n"
            f"• 📨 Сообщений сегодня: <b>{today_messages}</b>\n"
            f"• 📨 Сообщений за неделю: <b>{week_messages}</b>\n\n"
            "🔍 <b>Доступные действия:</b>\n"
            "• Просмотр переписок пользователей\n"
            "• Поиск пользователей по перепискам\n"
            "• Просмотр истории сообщений\n"
        )
        
        await message.answer(conversations_message, parse_mode="HTML", 
                           reply_markup=admin_conversations_menu())
        
    except Exception as e:
        logger.error(f"Ошибка в admin_conversations: {e}")
        await message.answer(f"❌ Ошибка получения статистики: {str(e)[:200]}")

@router.callback_query(F.data == "admin_conversations")
async def admin_conversations_callback(callback: types.CallbackQuery):
    """Callback для меню переписок"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        total_users_with_conversations = safe_execute_scalar(
            "SELECT COUNT(DISTINCT sender_id) + COUNT(DISTINCT receiver_id) FROM anon_messages WHERE sender_id IS NOT NULL"
        ) or 0
        
        total_conversations = safe_execute_scalar(
            """
            SELECT COUNT(DISTINCT CASE 
                WHEN sender_id < receiver_id THEN sender_id || '-' || receiver_id 
                ELSE receiver_id || '-' || sender_id 
            END)
            FROM anon_messages 
            WHERE sender_id IS NOT NULL AND receiver_id IS NOT NULL
            """
        ) or 0
        
        conversations_message = (
            "💬 <b>Управление переписками</b>\n\n"
            "📊 <b>Статистика переписок:</b>\n"
            f"• 👥 Пользователей с переписками: <b>{total_users_with_conversations}</b>\n"
            f"• 💬 Активных диалогов: <b>{total_conversations}</b>\n\n"
            "🔍 <b>Доступные действия:</b>\n"
            "Выберите опцию ниже"
        )
        
        await callback.message.edit_text(conversations_message, parse_mode="HTML", 
                                       reply_markup=admin_conversations_menu())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_conversations_callback: {e}")
        await callback.answer("❌ Произошла ошибка")

# ==================== СПИСОК ПОЛЬЗОВАТЕЛЕЙ С ПЕРЕПИСКАМИ ====================

@router.callback_query(F.data == "admin_conversations_list")
async def admin_conversations_list(callback: types.CallbackQuery):
    """Список пользователей с переписками"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        # Получаем пользователей с переписками
        users = safe_execute_query_fetchall("""
            SELECT u.id, u.telegram_id, u.first_name, u.username,
                   COUNT(DISTINCT CASE WHEN am.sender_id = u.id THEN am.receiver_id ELSE NULL END) as sent_to_count,
                   COUNT(DISTINCT CASE WHEN am.receiver_id = u.id THEN am.sender_id ELSE NULL END) as received_from_count,
                   COUNT(*) as total_messages,
                   MAX(am.timestamp) as last_message_time
            FROM users u
            LEFT JOIN anon_messages am ON u.id = am.sender_id OR u.id = am.receiver_id
            WHERE am.id IS NOT NULL
            GROUP BY u.id, u.telegram_id, u.first_name, u.username
            ORDER BY last_message_time DESC
            LIMIT 20
        """)
        
        if not users:
            await callback.message.edit_text(
                "📭 <b>Пользователей с переписками не найдено</b>",
                parse_mode="HTML",
                reply_markup=admin_conversations_menu()
            )
            await callback.answer()
            return
        
        conversations_message = "💬 <b>Пользователи с переписками</b>\n\n"
        
        for user in users:
            user_id = user[0]
            telegram_id = user[1]
            first_name = user[2]
            username = user[3] or "нет"
            sent_to_count = user[4] or 0
            received_from_count = user[5] or 0
            total_messages = user[6] or 0
            last_message_time = user[7]
            
            # Форматируем время последнего сообщения
            last_time = "давно"
            if last_message_time:
                try:
                    if isinstance(last_message_time, str):
                        last_time = last_message_time[:16].replace('T', ' ')
                    else:
                        last_time = last_message_time.strftime('%d.%m.%Y %H:%M')
                except:
                    pass
            
            conversations_message += (
                f"👤 <b>{first_name}</b>\n"
                f"🆔 ID: <code>{telegram_id}</code>\n"
                f"📊 Переписки: с {sent_to_count} пользователями\n"
                f"📨 Всего сообщений: {total_messages}\n"
                f"⏰ Последнее: {last_time}\n"
                f"🔍 <a href='https://t.me/{username}'>Профиль</a> | "
                f"💬 <a href='tg://btn/{callback.message.chat.id}?start=admin_conversation_{user_id}'>Смотреть переписки</a>\n"
                f"────────────────────\n"
            )
        
        # Добавляем кнопку поиска
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin_conversations_search"),
                InlineKeyboardButton(text="◀️ Назад", callback_data="admin_conversations")
            ]
        ])
        
        await callback.message.edit_text(conversations_message, parse_mode="HTML", disable_web_page_preview=True,
                                       reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_conversations_list: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка при загрузке списка")

# ==================== ПОИСК ПОЛЬЗОВАТЕЛЯ ДЛЯ ПРОСМОТРА ПЕРЕПИСОК ====================

@router.callback_query(F.data == "admin_conversations_search")
async def admin_conversations_search_start(callback: types.CallbackQuery, state: FSMContext):
    """Начать поиск пользователя для просмотра переписок"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    await callback.message.answer(
        "🔍 <b>Поиск пользователя для просмотра переписок</b>\n\n"
        "Введите ID пользователя, имя или username:\n"
        "Примеры:\n"
        "• <code>123456789</code> (Telegram ID)\n"
        "• <code>@username</code>\n"
        "• <code>Имя</code>",
        parse_mode="HTML"
    )
    await state.set_state(ConversationStates.waiting_user_search)
    await callback.answer()

@router.message(ConversationStates.waiting_user_search)
async def admin_conversations_search_result(message: types.Message, state: FSMContext):
    """Результат поиска пользователя для переписок"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    search_query = message.text.strip()
    
    try:
        users = []
        
        if search_query.isdigit():
            # Ищем по telegram_id
            user = safe_execute_query_fetchone(
                "SELECT * FROM users WHERE telegram_id = :telegram_id",
                {"telegram_id": int(search_query)}
            )
            if user:
                users.append(user)
        
        elif search_query.startswith('@'):
            # Ищем по username
            username = search_query[1:]
            users = safe_execute_query_fetchall(
                "SELECT * FROM users WHERE username LIKE :username",
                {"username": f"%{username}%"}
            )
        else:
            # Ищем по имени
            users = safe_execute_query_fetchall(
                "SELECT * FROM users WHERE first_name LIKE :first_name OR last_name LIKE :first_name",
                {"first_name": f"%{search_query}%"}
            )
        
        if not users:
            await message.answer("❌ Пользователи не найдены")
            await state.clear()
            return
        
        if len(users) == 1:
            user = users[0]
            user_id = user[0] if user else 0
            
            # Показываем меню переписок пользователя
            await show_user_conversations(message, user_id)
        
        else:
            users_found = f"🔍 <b>Найдено пользователей:</b> {len(users)}\n\n"
            
            for i, user in enumerate(users[:10], 1):
                user_id = user[0] if user else 0
                telegram_id = user[1] if user and len(user) > 1 else "N/A"
                first_name = user[3] if user and len(user) > 3 else "Без имени"
                username = user[2] or "нет" if user and len(user) > 2 else "нет"
                
                # Получаем количество переписок
                conversations_count = safe_execute_scalar("""
                    SELECT COUNT(DISTINCT CASE 
                        WHEN sender_id = :user_id THEN receiver_id 
                        ELSE sender_id 
                    END)
                    FROM anon_messages 
                    WHERE sender_id = :user_id OR receiver_id = :user_id
                """, {"user_id": user_id}) or 0
                
                users_found += (
                    f"{i}. 👤 <b>{first_name}</b>\n"
                    f"   🆔 ID: <code>{telegram_id}</code>\n"
                    f"   💬 Переписок: {conversations_count}\n"
                    f"   📝 <a href='tg://btn/{message.chat.id}?start=admin_conversation_{user_id}'>Смотреть переписки</a>\n"
                    f"   ────────────────────\n"
                )
            
            if len(users) > 10:
                users_found += f"\n⚠️ Показано первых 10 из {len(users)} результатов"
            
            await message.answer(users_found, parse_mode="HTML", disable_web_page_preview=True)
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_conversations_search_result: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка поиска: {str(e)[:100]}")
        await state.clear()

# ==================== ПЕРЕПИСКИ КОНКРЕТНОГО ПОЛЬЗОВАТЕЛЯ ====================

async def show_user_conversations(message: types.Message, user_id: int):
    """Показать все переписки пользователя"""
    try:
        # Получаем информацию о пользователе
        user = safe_execute_query_fetchone(
            "SELECT telegram_id, first_name, username FROM users WHERE id = :user_id",
            {"user_id": user_id}
        )
        
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        telegram_id = user[0]
        first_name = user[1]
        username = user[2] or "не указан"
        
        # Получаем всех собеседников пользователя
        conversations = safe_execute_query_fetchall("""
            SELECT 
                other_user.id as other_user_id,
                other_user.telegram_id as other_telegram_id,
                other_user.first_name as other_first_name,
                other_user.username as other_username,
                COUNT(*) as message_count,
                MAX(am.timestamp) as last_message_time,
                SUM(CASE WHEN am.sender_id = :user_id THEN 1 ELSE 0 END) as sent_count,
                SUM(CASE WHEN am.receiver_id = :user_id THEN 1 ELSE 0 END) as received_count
            FROM (
                SELECT DISTINCT 
                    CASE WHEN sender_id = :user_id THEN receiver_id ELSE sender_id END as other_id
                FROM anon_messages 
                WHERE sender_id = :user_id OR receiver_id = :user_id
            ) as conv_ids
            JOIN users other_user ON conv_ids.other_id = other_user.id
            JOIN anon_messages am ON (
                (am.sender_id = :user_id AND am.receiver_id = other_user.id) OR 
                (am.receiver_id = :user_id AND am.sender_id = other_user.id)
            )
            GROUP BY other_user.id, other_user.telegram_id, other_user.first_name, other_user.username
            ORDER BY last_message_time DESC
        """, {"user_id": user_id})
        
        if not conversations:
            user_info = (
                f"👤 <b>Пользователь: {first_name}</b>\n"
                f"🆔 ID: <code>{telegram_id}</code>\n"
                f"🏷️ Username: @{username}\n\n"
                f"📭 <b>У пользователя нет переписок</b>"
            )
            await message.answer(user_info, parse_mode="HTML")
            return
        
        user_info = (
            f"👤 <b>Пользователь: {first_name}</b>\n"
            f"🆔 ID: <code>{telegram_id}</code>\n"
            f"🏷️ Username: @{username}\n\n"
            f"💬 <b>Все переписки:</b>\n"
        )
        
        # Группируем переписки
        sent_conversations = []  # Куда пользователь писал
        received_conversations = []  # Кто писал пользователю
        
        for conv in conversations:
            other_user_id = conv[0]
            other_telegram_id = conv[1]
            other_first_name = conv[2]
            other_username = conv[3] or "нет"
            message_count = conv[4] or 0
            sent_count = conv[6] or 0
            received_count = conv[7] or 0
            
            if sent_count > 0 and received_count > 0:
                # Взаимная переписка
                conversation_type = "💬 Взаимная"
            elif sent_count > 0:
                # Пользователь писал
                conversation_type = "📤 Отправлял"
                sent_conversations.append(conv)
                continue
            else:
                # Пользователю писали
                conversation_type = "📨 Получал"
                received_conversations.append(conv)
                continue
            
            # Форматируем время последнего сообщения
            last_message_time = conv[5]
            last_time = "давно"
            if last_message_time:
                try:
                    if isinstance(last_message_time, str):
                        last_time = last_message_time[:16].replace('T', ' ')
                    else:
                        last_time = last_message_time.strftime('%d.%m.%Y %H:%M')
                except:
                    pass
            
            user_info += (
                f"\n{conversation_type} с: <b>{other_first_name}</b>\n"
                f"🆔 ID: <code>{other_telegram_id}</code>\n"
                f"📨 Сообщений: {message_count} ({sent_count} отправлено, {received_count} получено)\n"
                f"⏰ Последнее: {last_time}\n"
                f"📝 <a href='tg://btn/{message.chat.id}?start=view_conversation_{user_id}_{other_user_id}'>Смотреть переписку</a>\n"
                f"────────────────────"
            )
        
        # Добавляем разделы для отправленных и полученных сообщений
        if sent_conversations:
            user_info += f"\n\n📤 <b>Писал следующим пользователям:</b>"
            for conv in sent_conversations[:5]:  # Ограничиваем 5
                other_user_id = conv[0]
                other_telegram_id = conv[1]
                other_first_name = conv[2]
                message_count = conv[4] or 0
                sent_count = conv[6] or 0
                
                user_info += (
                    f"\n👤 <b>{other_first_name}</b> (ID: <code>{other_telegram_id}</code>)\n"
                    f"📤 Отправлено: {sent_count} сообщений\n"
                    f"📝 <a href='tg://btn/{message.chat.id}?start=view_conversation_{user_id}_{other_user_id}'>Смотреть</a>\n"
                    f"────────────────────"
                )
        
        if received_conversations:
            user_info += f"\n\n📨 <b>Писали следующие пользователи:</b>"
            for conv in received_conversations[:5]:  # Ограничиваем 5
                other_user_id = conv[0]
                other_telegram_id = conv[1]
                other_first_name = conv[2]
                message_count = conv[4] or 0
                received_count = conv[7] or 0
                
                user_info += (
                    f"\n👤 <b>{other_first_name}</b> (ID: <code>{other_telegram_id}</code>)\n"
                    f"📨 Получено: {received_count} сообщений\n"
                    f"📝 <a href='tg://btn/{message.chat.id}?start=view_conversation_{user_id}_{other_user_id}'>Смотреть</a>\n"
                    f"────────────────────"
                )
        
        # Создаем клавиатуру с действиями
        keyboard = admin_user_conversations_menu(user_id, len(conversations))
        
        await message.answer(user_info, parse_mode="HTML", disable_web_page_preview=True,
                           reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка в show_user_conversations: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка загрузки переписок: {str(e)[:200]}")

@router.callback_query(F.data.startswith("admin_view_conversations_"))
async def admin_view_conversations_callback(callback: types.CallbackQuery):
    """Callback для просмотра переписок пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        user_id = int(callback.data.replace("admin_view_conversations_", ""))
        await show_user_conversations(callback.message, user_id)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_view_conversations_callback: {e}")
        await callback.answer("❌ Произошла ошибка")

# ==================== ПРОСМОТР КОНКРЕТНОЙ ПЕРЕПИСКИ ====================

@router.callback_query(F.data.startswith("admin_view_conversation_"))
async def admin_view_conversation_detail(callback: types.CallbackQuery):
    """Просмотр конкретной переписки между двумя пользователями"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        # Формат: admin_view_conversation_{user1_id}_{user2_id}
        data_parts = callback.data.split("_")
        if len(data_parts) != 5:
            await callback.answer("❌ Неверный формат запроса")
            return
        
        user1_id = int(data_parts[3])
        user2_id = int(data_parts[4])
        
        # Получаем информацию о пользователях
        user1 = safe_execute_query_fetchone(
            "SELECT telegram_id, first_name, username FROM users WHERE id = :user_id",
            {"user_id": user1_id}
        )
        user2 = safe_execute_query_fetchone(
            "SELECT telegram_id, first_name, username FROM users WHERE id = :user_id",
            {"user_id": user2_id}
        )
        
        if not user1 or not user2:
            await callback.answer("❌ Пользователи не найдены")
            return
        
        user1_name = user1[1]
        user2_name = user2[1]
        user1_username = user1[2] or "нет"
        user2_username = user2[2] or "нет"
        
        # Получаем историю сообщений
        messages = safe_execute_query_fetchall("""
            SELECT 
                am.id,
                am.sender_id,
                am.receiver_id,
                am.message_text,
                am.timestamp,
                am.is_revealed,
                u1.first_name as sender_name,
                u2.first_name as receiver_name
            FROM anon_messages am
            LEFT JOIN users u1 ON am.sender_id = u1.id
            LEFT JOIN users u2 ON am.receiver_id = u2.id
            WHERE (am.sender_id = :user1_id AND am.receiver_id = :user2_id)
               OR (am.sender_id = :user2_id AND am.receiver_id = :user1_id)
            ORDER BY am.timestamp ASC
            LIMIT 50
        """, {"user1_id": user1_id, "user2_id": user2_id})
        
        if not messages:
            conversation_info = (
                f"💬 <b>Переписка между:</b>\n"
                f"👤 <b>{user1_name}</b> (ID: <code>{user1[0]}</code>) @{user1_username}\n"
                f"👤 <b>{user2_name}</b> (ID: <code>{user2[0]}</code>) @{user2_username}\n\n"
                f"📭 <b>Сообщений не найдено</b>"
            )
            await callback.message.edit_text(conversation_info, parse_mode="HTML")
            await callback.answer()
            return
        
        # Формируем историю переписки
        conversation_history = (
            f"💬 <b>Переписка между:</b>\n"
            f"👤 <b>{user1_name}</b> (ID: <code>{user1[0]}</code>) @{user1_username}\n"
            f"👤 <b>{user2_name}</b> (ID: <code>{user2[0]}</code>) @{user2_username}\n\n"
            f"📊 <b>Всего сообщений:</b> {len(messages)}\n"
            f"────────────────────\n\n"
        )
        
        # Отображаем сообщения в виде переписки
        for msg in messages:
            msg_id = msg[0]
            sender_id = msg[1]
            receiver_id = msg[2]
            message_text = msg[3]
            timestamp = msg[4]
            is_revealed = msg[5]
            sender_name = msg[6] or "Аноним"
            receiver_name = msg[7] or "Получатель"
            
            # Определяем направление сообщения
            if sender_id == user1_id:
                direction = "→"  # От user1 к user2
                sender_display = user1_name
            else:
                direction = "←"  # От user2 к user1
                sender_display = user2_name
            
            # Форматируем время
            try:
                if isinstance(timestamp, str):
                    message_time = timestamp[11:16]  # Берем только время HH:MM
                else:
                    message_time = timestamp.strftime('%H:%M')
            except:
                message_time = "??:??"
            
            # Обрезаем длинный текст
            display_text = message_text
            if len(display_text) > 100:
                display_text = display_text[:100] + "..."
            
            # Добавляем статус раскрытия
            reveal_status = "👁️" if is_revealed else "🕵️"
            
            conversation_history += (
                f"<b>{message_time}</b> {direction} <b>{sender_display}</b> {reveal_status}:\n"
                f"{display_text}\n"
                f"────────────────────\n"
            )
        
        # Добавляем статистику
        user1_sent = sum(1 for msg in messages if msg[1] == user1_id)
        user2_sent = sum(1 for msg in messages if msg[1] == user2_id)
        
        conversation_history += (
            f"\n📊 <b>Статистика:</b>\n"
            f"• {user1_name}: {user1_sent} сообщений\n"
            f"• {user2_name}: {user2_sent} сообщений\n"
            f"• Всего: {len(messages)} сообщений\n\n"
            f"🕐 <b>Период переписки:</b>\n"
        )
        
        # Показываем период переписки
        if messages:
            first_msg = messages[0]
            last_msg = messages[-1]
            
            try:
                if isinstance(first_msg[4], str):
                    first_time = first_msg[4][:16].replace('T', ' ')
                else:
                    first_time = first_msg[4].strftime('%d.%m.%Y %H:%M')
                
                if isinstance(last_msg[4], str):
                    last_time = last_msg[4][:16].replace('T', ' ')
                else:
                    last_time = last_msg[4].strftime('%d.%m.%Y %H:%M')
                
                conversation_history += f"Начало: {first_time}\n"
                conversation_history += f"Последнее: {last_time}\n"
            except:
                pass
        
        # Создаем клавиатуру для навигации
        keyboard = admin_message_history_keyboard(user1_id, user2_id, 1, 1)
        
        if len(conversation_history) > 4096:
            # Разбиваем на части если слишком длинное
            parts = [conversation_history[i:i+4000] for i in range(0, len(conversation_history), 4000)]
            for i, part in enumerate(parts):
                if i == 0:
                    await callback.message.edit_text(part, parse_mode="HTML", 
                                                   disable_web_page_preview=True,
                                                   reply_markup=keyboard if i == len(parts)-1 else None)
                else:
                    await callback.message.answer(part, parse_mode="HTML", 
                                                disable_web_page_preview=True,
                                                reply_markup=keyboard if i == len(parts)-1 else None)
        else:
            await callback.message.edit_text(conversation_history, parse_mode="HTML", 
                                           disable_web_page_preview=True,
                                           reply_markup=keyboard)
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_view_conversation_detail: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка")

# ==================== ПОИСК ПО СОДЕРЖАНИЮ СООБЩЕНИЙ ====================

@router.callback_query(F.data == "admin_search_messages")
async def admin_search_messages_start(callback: types.CallbackQuery, state: FSMContext):
    """Поиск по содержанию сообщений"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    await callback.message.answer(
        "🔍 <b>Поиск по содержанию сообщений</b>\n\n"
        "Введите текст для поиска в сообщениях:\n"
        "Пример: 'привет', 'как дела', 'люблю'\n\n"
        "⚠️ <b>Внимание:</b> Поиск может занять некоторое время",
        parse_mode="HTML"
    )
    await state.set_state(ConversationStates.waiting_conversation_select)
    await callback.answer()

@router.message(ConversationStates.waiting_conversation_select)
async def admin_search_messages_result(message: types.Message, state: FSMContext):
    """Результаты поиска по сообщениям"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    search_text = message.text.strip()
    
    if len(search_text) < 2:
        await message.answer("❌ Введите минимум 2 символа для поиска")
        await state.clear()
        return
    
    try:
        # Ищем сообщения
        messages = safe_execute_query_fetchall("""
            SELECT 
                am.id,
                am.message_text,
                am.timestamp,
                am.is_revealed,
                sender.telegram_id as sender_tg_id,
                sender.first_name as sender_name,
                sender.username as sender_username,
                receiver.telegram_id as receiver_tg_id,
                receiver.first_name as receiver_name,
                receiver.username as receiver_username
            FROM anon_messages am
            LEFT JOIN users sender ON am.sender_id = sender.id
            LEFT JOIN users receiver ON am.receiver_id = receiver.id
            WHERE am.message_text LIKE :search_text
            ORDER BY am.timestamp DESC
            LIMIT 20
        """, {"search_text": f"%{search_text}%"})
        
        if not messages:
            await message.answer(f"❌ Сообщения с текстом '{search_text}' не найдены")
            await state.clear()
            return
        
        search_results = (
            f"🔍 <b>Результаты поиска:</b> '{search_text}'\n"
            f"📊 <b>Найдено сообщений:</b> {len(messages)}\n"
            f"────────────────────\n\n"
        )
        
        for i, msg in enumerate(messages, 1):
            msg_id = msg[0]
            message_text = msg[1]
            timestamp = msg[2]
            is_revealed = msg[3]
            sender_tg_id = msg[4]
            sender_name = msg[5] or "Аноним"
            sender_username = msg[6] or "нет"
            receiver_tg_id = msg[7]
            receiver_name = msg[8] or "Получатель"
            receiver_username = msg[9] or "нет"
            
            # Форматируем время
            try:
                if isinstance(timestamp, str):
                    message_time = timestamp[:16].replace('T', ' ')
                else:
                    message_time = timestamp.strftime('%d.%m.%Y %H:%M')
            except:
                message_time = "дата неизвестна"
            
            # Обрезаем текст
            display_text = message_text
            if len(display_text) > 80:
                display_text = display_text[:80] + "..."
            
            search_results += (
                f"{i}. 📨 <b>Сообщение ID: {msg_id}</b>\n"
                f"   📝 Текст: {display_text}\n"
                f"   👤 От: {sender_name} (ID: <code>{sender_tg_id}</code>)\n"
                f"   👥 Кому: {receiver_name} (ID: <code>{receiver_tg_id}</code>)\n"
                f"   🕐 Время: {message_time}\n"
                f"   👁️ Статус: {'Раскрыто' if is_revealed else 'Анонимно'}\n"
                f"   ────────────────────\n"
            )
        
        await message.answer(search_results, parse_mode="HTML")
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_search_messages_result: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка поиска: {str(e)[:100]}")
        await state.clear()

# ==================== АДМИНСКИЕ КОМАНДЫ ДЛЯ ПЕРЕПИСОК ====================

@router.message(Command("conversations"), admin_filter)
async def conversations_command(message: types.Message):
    """Команда для быстрого доступа к перепискам"""
    await admin_conversations(message)

@router.message(Command("find_conversation"), admin_filter)
async def find_conversation_command(message: types.Message, state: FSMContext):
    """Найти переписку по ID пользователей"""
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer(
                "❌ Использование: /find_conversation ID_пользователя\n\n"
                "Пример: /find_conversation 123456789\n"
                "Или: /find_conversation @username"
            )
            return
        
        search_query = args[1]
        await message.answer(f"🔍 Ищу пользователя: {search_query}")
        
        users = []
        
        if search_query.isdigit():
            user = safe_execute_query_fetchone(
                "SELECT * FROM users WHERE telegram_id = :telegram_id",
                {"telegram_id": int(search_query)}
            )
            if user:
                users.append(user)
        elif search_query.startswith('@'):
            username = search_query[1:]
            users = safe_execute_query_fetchall(
                "SELECT * FROM users WHERE username LIKE :username",
                {"username": f"%{username}%"}
            )
        else:
            users = safe_execute_query_fetchall(
                "SELECT * FROM users WHERE first_name LIKE :first_name",
                {"first_name": f"%{search_query}%"}
            )
        
        if not users:
            await message.answer("❌ Пользователи не найдены")
            return
        
        if len(users) == 1:
            user = users[0]
            user_id = user[0]
            await show_user_conversations(message, user_id)
        else:
            result_text = f"🔍 <b>Найдено пользователей:</b> {len(users)}\n\n"
            for i, user in enumerate(users[:5], 1):
                user_id = user[0]
                telegram_id = user[1]
                first_name = user[3]
                username = user[2] or "нет"
                
                result_text += (
                    f"{i}. 👤 <b>{first_name}</b>\n"
                    f"   🆔 ID: <code>{telegram_id}</code>\n"
                    f"   🏷️ @{username}\n"
                    f"   💬 /find_conversation_{user_id}\n"
                    f"   ────────────────────\n"
                )
            
            if len(users) > 5:
                result_text += f"\n⚠️ Показано первых 5 из {len(users)} результатов"
            
            await message.answer(result_text, parse_mode="HTML")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.message(F.text.startswith("/find_conversation_"), admin_filter)
async def find_conversation_by_id_command(message: types.Message):
    """Найти переписку по внутреннему ID пользователя"""
    try:
        user_id = int(message.text.replace("/find_conversation_", ""))
        await show_user_conversations(message, user_id)
    except ValueError:
        await message.answer("❌ Неверный формат ID")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# Экспортируем router для подключения в основном файле
__all__ = ['router']
