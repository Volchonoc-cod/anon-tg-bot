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
from app.database_utils import (
    safe_execute_query_fetchall, 
    safe_execute_query_fetchone, 
    safe_execute_scalar
)
from app.config import ADMIN_IDS
from app.keyboards_admin import (
    admin_conversations_menu, 
    admin_user_conversations_menu, 
    admin_message_history_keyboard,
    admin_main_menu
)
from app.keyboards import main_menu

logger = logging.getLogger(__name__)

router = Router()

class ConversationStates(StatesGroup):
    waiting_user_search = State()
    waiting_conversation_select = State()
    waiting_message_search = State()
    waiting_export_options = State()
    waiting_cleanup_days = State()
    waiting_send_message = State()

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
        total_conversations = safe_execute_scalar("""
            SELECT COUNT(DISTINCT CASE 
                WHEN sender_id < receiver_id THEN sender_id || '-' || receiver_id 
                ELSE receiver_id || '-' || sender_id 
            END)
            FROM anon_messages 
            WHERE sender_id IS NOT NULL AND receiver_id IS NOT NULL
        """) or 0
        
        today_messages = safe_execute_scalar(
            "SELECT COUNT(*) FROM anon_messages WHERE DATE(timestamp) = DATE('now')"
        ) or 0
        
        week_messages = safe_execute_scalar(
            "SELECT COUNT(*) FROM anon_messages WHERE timestamp >= datetime('now', '-7 days')"
        ) or 0
        
        # Получаем количество пользователей с сообщениями
        users_with_messages = safe_execute_scalar("""
            SELECT COUNT(DISTINCT CASE 
                WHEN sender_id IS NOT NULL THEN sender_id 
                ELSE receiver_id 
            END)
            FROM anon_messages
        """) or 0
        
        # Получаем последнюю активность
        last_activity = safe_execute_scalar(
            "SELECT MAX(timestamp) FROM anon_messages"
        ) or "нет данных"
        
        if last_activity != "нет данных":
            try:
                if isinstance(last_activity, str):
                    last_activity = last_activity[:16].replace('T', ' ')
                else:
                    last_activity = last_activity.strftime('%d.%m.%Y %H:%M')
            except:
                pass
        
        conversations_message = (
            "💬 <b>Управление переписками</b>\n\n"
            "📊 <b>Статистика переписок:</b>\n"
            f"• 👥 Пользователей с переписками: <b>{users_with_messages}</b>\n"
            f"• 💬 Активных диалогов: <b>{total_conversations}</b>\n"
            f"• 📨 Сообщений сегодня: <b>{today_messages}</b>\n"
            f"• 📨 Сообщений за неделю: <b>{week_messages}</b>\n"
            f"• 🕐 Последняя активность: <b>{last_activity}</b>\n\n"
            "🔧 <b>Доступные действия:</b>\n"
            "• 📋 Список пользователей с переписками\n"
            "• 🔍 Поиск пользователя\n"
            "• 🔎 Поиск по содержанию сообщений\n"
            "• 💾 Экспорт переписок\n"
            "• 🧹 Очистка старых сообщений\n"
            "• ✉️ Отправить сообщение от имени бота\n"
        )
        
        await message.answer(conversations_message, parse_mode="HTML", 
                           reply_markup=admin_conversations_menu())
        
    except Exception as e:
        logger.error(f"Ошибка в admin_conversations: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка получения статистики: {str(e)[:200]}")

@router.callback_query(F.data == "admin_conversations")
async def admin_conversations_callback(callback: types.CallbackQuery):
    """Callback для меню переписок"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        total_conversations = safe_execute_scalar("""
            SELECT COUNT(DISTINCT CASE 
                WHEN sender_id < receiver_id THEN sender_id || '-' || receiver_id 
                ELSE receiver_id || '-' || sender_id 
            END)
            FROM anon_messages 
            WHERE sender_id IS NOT NULL AND receiver_id IS NOT NULL
        """) or 0
        
        users_with_messages = safe_execute_scalar("""
            SELECT COUNT(DISTINCT CASE 
                WHEN sender_id IS NOT NULL THEN sender_id 
                ELSE receiver_id 
            END)
            FROM anon_messages
        """) or 0
        
        conversations_message = (
            "💬 <b>Управление переписками</b>\n\n"
            "📊 <b>Статистика переписок:</b>\n"
            f"• 👥 Пользователей с переписками: <b>{users_with_messages}</b>\n"
            f"• 💬 Активных диалогов: <b>{total_conversations}</b>\n\n"
            "🔧 <b>Доступные действия:</b>\n"
            "Выберите опцию ниже"
        )
        
        await callback.message.edit_text(conversations_message, parse_mode="HTML", 
                                       reply_markup=admin_conversations_menu())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_conversations_callback: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка")

# ==================== СПИСОК ПОЛЬЗОВАТЕЛЕЙ С ПЕРЕПИСКАМИ ====================

@router.callback_query(F.data == "admin_conversations_list")
async def admin_conversations_list(callback: types.CallbackQuery):
    """Список пользователей с переписками (ИСПРАВЛЕННЫЙ ЗАПРОС)"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        # ИСПРАВЛЕННЫЙ ЗАПРОС: убрана функция GREATEST
        users = safe_execute_query_fetchall("""
            SELECT 
                u.id, 
                u.telegram_id, 
                u.first_name, 
                u.username,
                COUNT(DISTINCT am.receiver_id) as sent_to_count,
                COUNT(DISTINCT am2.sender_id) as received_from_count,
                (COUNT(DISTINCT am.receiver_id) + COUNT(DISTINCT am2.sender_id)) as total_contacts,
                MAX(
                    CASE 
                        WHEN am.timestamp IS NULL AND am2.timestamp IS NULL THEN '2000-01-01'
                        WHEN am.timestamp IS NULL THEN am2.timestamp
                        WHEN am2.timestamp IS NULL THEN am.timestamp
                        WHEN am.timestamp > am2.timestamp THEN am.timestamp
                        ELSE am2.timestamp
                    END
                ) as last_message_time
            FROM users u
            LEFT JOIN anon_messages am ON u.id = am.sender_id
            LEFT JOIN anon_messages am2 ON u.id = am2.receiver_id
            WHERE am.id IS NOT NULL OR am2.id IS NOT NULL
            GROUP BY u.id, u.telegram_id, u.first_name, u.username
            HAVING total_contacts > 0
            ORDER BY last_message_time DESC
            LIMIT 15
        """)
        
        if not users:
            await callback.message.answer(
                "📭 <b>Пользователей с переписками не найдено</b>",
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        conversations_message = "💬 <b>Пользователи с переписками</b>\n\n"
        
        for i, user in enumerate(users, 1):
            user_id = user[0]
            telegram_id = user[1]
            first_name = user[2] or "Без имени"
            username = user[3] or "нет"
            sent_to_count = user[4] or 0
            received_from_count = user[5] or 0
            total_contacts = user[6] or 0
            last_message_time = user[7]
            
            # Форматируем время последнего сообщения
            last_time = "давно"
            if last_message_time and str(last_message_time) != '2000-01-01':
                try:
                    if isinstance(last_message_time, str):
                        last_time = last_message_time[:16].replace('T', ' ')
                    else:
                        last_time = last_message_time.strftime('%d.%m.%Y %H:%M')
                except:
                    pass
            
            # Получаем общее количество сообщений
            total_messages = safe_execute_scalar("""
                SELECT COUNT(*) FROM anon_messages 
                WHERE sender_id = :user_id OR receiver_id = :user_id
            """, {"user_id": user_id}) or 0
            
            conversations_message += (
                f"{i}. 👤 <b>{first_name}</b>\n"
                f"   🆔 ID: <code>{telegram_id}</code>\n"
                f"   📊 Контакты: {total_contacts} (📤{sent_to_count}/📨{received_from_count})\n"
                f"   📨 Сообщений: {total_messages}\n"
                f"   ⏰ Последнее: {last_time}\n"
                f"   💬 /find_conversation_{user_id}\n"
                f"   ────────────────────\n"
            )
        
        # Добавляем кнопки
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin_conversations_search"),
                InlineKeyboardButton(text="🔎 Поиск сообщений", callback_data="admin_search_messages")
            ],
            [
                InlineKeyboardButton(text="💾 Экспорт", callback_data="admin_export_conversations"),
                InlineKeyboardButton(text="🧹 Очистка", callback_data="admin_cleanup_conversations")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="admin_conversations")
            ]
        ])
        
        await callback.message.edit_text(
            conversations_message, 
            parse_mode="HTML", 
            disable_web_page_preview=True,
            reply_markup=keyboard
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_conversations_list: {e}", exc_info=True)
        await callback.message.answer("❌ Произошла ошибка при загрузке списка")
        await callback.answer()

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
        "• <code>Имя</code>\n\n"
        "ℹ️ <i>Для поиска по сообщениям используйте кнопку '🔎 Поиск сообщений'</i>",
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
            user_id = user[0]
            
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
                
                # Получаем количество сообщений
                messages_count = safe_execute_scalar("""
                    SELECT COUNT(*) FROM anon_messages 
                    WHERE sender_id = :user_id OR receiver_id = :user_id
                """, {"user_id": user_id}) or 0
                
                users_found += (
                    f"{i}. 👤 <b>{first_name}</b>\n"
                    f"   🆔 ID: <code>{telegram_id}</code>\n"
                    f"   💬 Диалогов: {conversations_count}\n"
                    f"   📨 Сообщений: {messages_count}\n"
                    f"   📝 /find_conversation_{user_id}\n"
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
            "SELECT telegram_id, first_name, username, available_reveals FROM users WHERE id = :user_id",
            {"user_id": user_id}
        )
        
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        telegram_id = user[0]
        first_name = user[1] or "Без имени"
        username = user[2] or "не указан"
        available_reveals = user[3] or 0
        
        # Получаем статистику пользователя
        total_messages = safe_execute_scalar("""
            SELECT COUNT(*) FROM anon_messages 
            WHERE sender_id = :user_id OR receiver_id = :user_id
        """, {"user_id": user_id}) or 0
        
        sent_messages = safe_execute_scalar("""
            SELECT COUNT(*) FROM anon_messages 
            WHERE sender_id = :user_id
        """, {"user_id": user_id}) or 0
        
        received_messages = safe_execute_scalar("""
            SELECT COUNT(*) FROM anon_messages 
            WHERE receiver_id = :user_id
        """, {"user_id": user_id}) or 0
        
        # Получаем последнюю активность
        last_activity = safe_execute_scalar("""
            SELECT MAX(timestamp) FROM anon_messages 
            WHERE sender_id = :user_id OR receiver_id = :user_id
        """, {"user_id": user_id})
        
        if last_activity:
            try:
                if isinstance(last_activity, str):
                    last_activity = last_activity[:16].replace('T', ' ')
                else:
                    last_activity = last_activity.strftime('%d.%m.%Y %H:%M')
            except:
                last_activity = "неизвестно"
        else:
            last_activity = "не было активности"
        
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
                WHERE (sender_id = :user_id OR receiver_id = :user_id) 
                  AND sender_id IS NOT NULL
            ) as conv_ids
            JOIN users other_user ON conv_ids.other_id = other_user.id
            LEFT JOIN anon_messages am ON (
                (am.sender_id = :user_id AND am.receiver_id = other_user.id) OR 
                (am.receiver_id = :user_id AND am.sender_id = other_user.id)
            )
            GROUP BY other_user.id, other_user.telegram_id, other_user.first_name, other_user.username
            ORDER BY last_message_time DESC
            LIMIT 20
        """, {"user_id": user_id})
        
        user_info = (
            f"👤 <b>Профиль пользователя</b>\n\n"
            f"📋 <b>Основная информация:</b>\n"
            f"• Имя: <b>{first_name}</b>\n"
            f"• Telegram ID: <code>{telegram_id}</code>\n"
            f"• Username: @{username}\n"
            f"• Доступно раскрытий: <b>{available_reveals}</b>\n\n"
            f"📊 <b>Статистика переписок:</b>\n"
            f"• Всего сообщений: <b>{total_messages}</b>\n"
            f"• Отправлено: <b>{sent_messages}</b>\n"
            f"• Получено: <b>{received_messages}</b>\n"
            f"• Последняя активность: <b>{last_activity}</b>\n"
        )
        
        if not conversations:
            user_info += f"\n📭 <b>У пользователя нет переписок</b>"
            await message.answer(user_info, parse_mode="HTML")
            return
        
        user_info += f"\n💬 <b>Все переписки:</b> ({len(conversations)} диалогов)\n\n"
        
        # Группируем переписки
        mutual_conversations = []
        sent_only_conversations = []
        received_only_conversations = []
        
        for conv in conversations[:15]:  # Ограничиваем показ
            other_user_id = conv[0]
            other_telegram_id = conv[1]
            other_first_name = conv[2] or "Без имени"
            message_count = conv[4] or 0
            sent_count = conv[6] or 0
            received_count = conv[7] or 0
            
            if sent_count > 0 and received_count > 0:
                mutual_conversations.append((conv, "🤝"))
            elif sent_count > 0:
                sent_only_conversations.append((conv, "📤"))
            else:
                received_only_conversations.append((conv, "📨"))
        
        # Показываем взаимные переписки
        if mutual_conversations:
            user_info += f"🤝 <b>Взаимные переписки:</b>\n"
            for conv, emoji in mutual_conversations[:5]:
                other_user_id = conv[0]
                other_telegram_id = conv[1]
                other_first_name = conv[2] or "Без имени"
                message_count = conv[4] or 0
                
                user_info += (
                    f"{emoji} <b>{other_first_name}</b>\n"
                    f"   🆔 ID: <code>{other_telegram_id}</code>\n"
                    f"   📨 Сообщений: {message_count}\n"
                    f"   💬 /view_conversation_{user_id}_{other_user_id}\n"
                    f"   ──────────────────\n"
                )
        
        # Показываем отправленные
        if sent_only_conversations:
            user_info += f"\n📤 <b>Писал следующим:</b>\n"
            for conv, emoji in sent_only_conversations[:3]:
                other_user_id = conv[0]
                other_telegram_id = conv[1]
                other_first_name = conv[2] or "Без имени"
                sent_count = conv[6] or 0
                
                user_info += (
                    f"{emoji} <b>{other_first_name}</b>\n"
                    f"   🆔 ID: <code>{other_telegram_id}</code>\n"
                    f"   📤 Отправлено: {sent_count} сообщ.\n"
                    f"   💬 /view_conversation_{user_id}_{other_user_id}\n"
                    f"   ──────────────────\n"
                )
        
        # Показываем полученные
        if received_only_conversations:
            user_info += f"\n📨 <b>Писали следующие:</b>\n"
            for conv, emoji in received_only_conversations[:3]:
                other_user_id = conv[0]
                other_telegram_id = conv[1]
                other_first_name = conv[2] or "Без имени"
                received_count = conv[7] or 0
                
                user_info += (
                    f"{emoji} <b>{other_first_name}</b>\n"
                    f"   🆔 ID: <code>{other_telegram_id}</code>\n"
                    f"   📨 Получено: {received_count} сообщ.\n"
                    f"   💬 /view_conversation_{user_id}_{other_user_id}\n"
                    f"   ──────────────────\n"
                )
        
        # Предупреждение о неполном показе
        shown_count = min(len(mutual_conversations), 5) + min(len(sent_only_conversations), 3) + min(len(received_only_conversations), 3)
        if shown_count < len(conversations):
            user_info += f"\n⚠️ Показано {shown_count} из {len(conversations)} диалогов"
        
        # Создаем клавиатуру с действиями
        keyboard = admin_user_conversations_menu(user_id, len(conversations))
        
        # Разбиваем на части если сообщение слишком длинное
        if len(user_info) > 4096:
            parts = [user_info[i:i+4000] for i in range(0, len(user_info), 4000)]
            for i, part in enumerate(parts):
                if i == 0:
                    await message.answer(part, parse_mode="HTML", disable_web_page_preview=True,
                                      reply_markup=keyboard if i == len(parts)-1 else None)
                else:
                    await message.answer(part, parse_mode="HTML", disable_web_page_preview=True)
        else:
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
        
        await show_conversation_detail(callback.message, user1_id, user2_id)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_view_conversation_detail: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка")

async def show_conversation_detail(message: types.Message, user1_id: int, user2_id: int):
    """Показать детали переписки между двумя пользователями"""
    try:
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
            await message.answer("❌ Один из пользователей не найден")
            return
        
        user1_name = user1[1] or "Без имени"
        user2_name = user2[1] or "Без имени"
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
                am.is_revealed
            FROM anon_messages am
            WHERE (am.sender_id = :user1_id AND am.receiver_id = :user2_id)
               OR (am.sender_id = :user2_id AND am.receiver_id = :user1_id)
            ORDER BY am.timestamp ASC
            LIMIT 100
        """, {"user1_id": user1_id, "user2_id": user2_id})
        
        if not messages:
            conversation_info = (
                f"💬 <b>Переписка между:</b>\n"
                f"👤 <b>{user1_name}</b> (ID: <code>{user1[0]}</code>) @{user1_username}\n"
                f"👤 <b>{user2_name}</b> (ID: <code>{user2[0]}</code>) @{user2_username}\n\n"
                f"📭 <b>Сообщений не найдено</b>"
            )
            await message.answer(conversation_info, parse_mode="HTML")
            return
        
        # Получаем статистику
        user1_sent = sum(1 for msg in messages if msg[1] == user1_id)
        user2_sent = sum(1 for msg in messages if msg[1] == user2_id)
        revealed_count = sum(1 for msg in messages if msg[5])
        
        # Определяем период переписки
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
        except:
            first_time = "неизвестно"
            last_time = "неизвестно"
        
        conversation_info = (
            f"💬 <b>Переписка между:</b>\n"
            f"👤 <b>{user1_name}</b> (ID: <code>{user1[0]}</code>) @{user1_username}\n"
            f"👤 <b>{user2_name}</b> (ID: <code>{user2[0]}</code>) @{user2_username}\n\n"
            f"📊 <b>Статистика диалога:</b>\n"
            f"• Всего сообщений: <b>{len(messages)}</b>\n"
            f"• {user1_name}: <b>{user1_sent}</b> сообщений\n"
            f"• {user2_name}: <b>{user2_sent}</b> сообщений\n"
            f"• Раскрыто сообщений: <b>{revealed_count}</b>\n"
            f"• Начало: {first_time}\n"
            f"• Последнее: {last_time}\n"
            f"────────────────────\n\n"
            f"<b>История переписки:</b>\n"
        )
        
        # Отображаем сообщения
        for msg in messages[-50:]:  # Последние 50 сообщений
            msg_id = msg[0]
            sender_id = msg[1]
            message_text = msg[3]
            timestamp = msg[4]
            is_revealed = msg[5]
            
            # Определяем отправителя
            if sender_id == user1_id:
                sender_display = user1_name
                direction = "➡️"
            else:
                sender_display = user2_name
                direction = "⬅️"
            
            # Форматируем время
            try:
                if isinstance(timestamp, str):
                    message_time = timestamp[11:16]
                else:
                    message_time = timestamp.strftime('%H:%M')
            except:
                message_time = "??:??"
            
            # Обрезаем текст
            display_text = message_text
            if len(display_text) > 80:
                display_text = display_text[:80] + "..."
            
            # Экранируем HTML-символы
            display_text = display_text.replace('<', '&lt;').replace('>', '&gt;')
            
            # Статус раскрытия
            reveal_status = "👁️" if is_revealed else "🕵️"
            
            conversation_info += (
                f"<b>{message_time}</b> {direction} <b>{sender_display}</b> {reveal_status}:\n"
                f"{display_text}\n"
                f"────────────────────\n"
            )
        
        # Создаем клавиатуру для навигации
        keyboard = admin_message_history_keyboard(user1_id, user2_id, 1, 1)
        
        if len(conversation_info) > 4096:
            # Разбиваем на части
            parts = [conversation_info[i:i+4000] for i in range(0, len(conversation_info), 4000)]
            for i, part in enumerate(parts):
                if i == 0:
                    await message.answer(part, parse_mode="HTML", 
                                       disable_web_page_preview=True,
                                       reply_markup=keyboard if i == len(parts)-1 else None)
                else:
                    await message.answer(part, parse_mode="HTML", 
                                       disable_web_page_preview=True,
                                       reply_markup=keyboard if i == len(parts)-1 else None)
        else:
            await message.answer(conversation_info, parse_mode="HTML", 
                               disable_web_page_preview=True,
                               reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Ошибка в show_conversation_detail: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка загрузки переписки: {str(e)[:200]}")

# ==================== ПОИСК ПО СОДЕРЖАНИЮ СООБЩЕНИЙ (ИСПРАВЛЕННЫЙ) ====================

@router.callback_query(F.data == "admin_search_messages")
async def admin_search_messages_start(callback: types.CallbackQuery, state: FSMContext):
    """Поиск по содержанию сообщений (ИСПРАВЛЕННЫЙ)"""
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
    await state.set_state(ConversationStates.waiting_message_search)
    await callback.answer()

@router.message(ConversationStates.waiting_message_search)
async def admin_search_messages_result(message: types.Message, state: FSMContext):
    """Результаты поиска по сообщениям (ИСПРАВЛЕННЫЙ)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    search_text = message.text.strip()
    
    if len(search_text) < 2:
        await message.answer("❌ Введите минимум 2 символа для поиска")
        await state.clear()
        return
    
    try:
        # ИСПРАВЛЕННЫЙ ЗАПРОС: используем правильное имя колонки message_text
        messages = safe_execute_query_fetchall("""
            SELECT 
                am.id,
                am.message_text,
                am.timestamp,
                am.is_revealed,
                sender.telegram_id as sender_tg_id,
                sender.first_name as sender_name,
                receiver.telegram_id as receiver_tg_id,
                receiver.first_name as receiver_name
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
            f"📊 <b>Найдено сообщений:</b> {len(messages)}\n\n"
        )
        
        for i, msg in enumerate(messages, 1):
            msg_id = msg[0]
            message_text = msg[1]
            timestamp = msg[2]
            is_revealed = msg[3]
            sender_tg_id = msg[4]
            sender_name = msg[5] or "Аноним"
            receiver_tg_id = msg[6]
            receiver_name = msg[7] or "Получатель"
            
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
            if len(display_text) > 60:
                display_text = display_text[:60] + "..."
            
            # Экранируем HTML
            display_text = display_text.replace('<', '&lt;').replace('>', '&gt;')
            
            # Подсвечиваем искомый текст
            if search_text.lower() in message_text.lower():
                start_idx = message_text.lower().find(search_text.lower())
                if start_idx != -1:
                    end_idx = start_idx + len(search_text)
                    highlighted = (
                        message_text[:start_idx] + 
                        f"<b>{message_text[start_idx:end_idx]}</b>" + 
                        message_text[end_idx:]
                    )
                    if len(highlighted) > 70:
                        highlighted = highlighted[:70] + "..."
                    display_text = highlighted
            
            search_results += (
                f"{i}. 📨 <b>Сообщение ID: {msg_id}</b>\n"
                f"   📝 <i>{display_text}</i>\n"
                f"   👤 От: {sender_name} (ID: <code>{sender_tg_id}</code>)\n"
                f"   👥 Кому: {receiver_name} (ID: <code>{receiver_tg_id}</code>)\n"
                f"   🕐 Время: {message_time}\n"
                f"   👁️ Статус: {'✅ Раскрыто' if is_revealed else '🕵️ Анонимно'}\n"
                f"   ────────────────────\n"
            )
        
        # Добавляем статистику поиска
        total_found = safe_execute_scalar(
            "SELECT COUNT(*) FROM anon_messages WHERE message_text LIKE :search_text",
            {"search_text": f"%{search_text}%"}
        ) or 0
        
        search_results += f"\n📈 <b>Всего найдено сообщений:</b> {total_found}"
        
        await message.answer(search_results, parse_mode="HTML")
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_search_messages_result: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка поиска: {str(e)[:100]}")
        await state.clear()

# ==================== НОВЫЕ ФУНКЦИИ ДЛЯ ПЕРЕПИСОК ====================

# 1. ЭКСПОРТ ПЕРЕПИСОК
@router.callback_query(F.data == "admin_export_conversations")
async def admin_export_conversations_start(callback: types.CallbackQuery, state: FSMContext):
    """Начать экспорт переписок"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    await callback.message.answer(
        "💾 <b>Экспорт переписок</b>\n\n"
        "Выберите формат экспорта:\n\n"
        "📋 <b>CSV формат</b> - табличный формат, открывается в Excel\n"
        "📄 <b>TXT формат</b> - текстовый файл для чтения\n"
        "🗃️ <b>JSON формат</b> - структурированные данные для программ\n\n"
        "Введите нужный формат (csv, txt или json):",
        parse_mode="HTML"
    )
    await state.set_state(ConversationStates.waiting_export_options)
    await callback.answer()

@router.message(ConversationStates.waiting_export_options)
async def admin_export_conversations_process(message: types.Message, state: FSMContext):
    """Обработка экспорта переписок"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    export_format = message.text.strip().lower()
    
    if export_format not in ['csv', 'txt', 'json']:
        await message.answer("❌ Неверный формат. Используйте: csv, txt или json")
        await state.clear()
        return
    
    try:
        await message.answer(f"⏳ <b>Начинаю экспорт в формате {export_format.upper()}...</b>", parse_mode="HTML")
        
        # Получаем все переписки
        conversations = safe_execute_query_fetchall("""
            SELECT 
                u1.telegram_id as user1_id,
                u1.first_name as user1_name,
                u1.username as user1_username,
                u2.telegram_id as user2_id,
                u2.first_name as user2_name,
                u2.username as user2_username,
                am.message_text,
                am.timestamp,
                am.is_revealed,
                CASE 
                    WHEN am.sender_id = u1.id THEN u1.first_name 
                    ELSE u2.first_name 
                END as sender_name
            FROM anon_messages am
            JOIN users u1 ON am.sender_id = u1.id OR am.receiver_id = u1.id
            JOIN users u2 ON (am.sender_id = u2.id OR am.receiver_id = u2.id) AND u2.id != u1.id
            WHERE u1.id < u2.id
            ORDER BY am.timestamp DESC
            LIMIT 1000
        """)
        
        if not conversations:
            await message.answer("❌ Нет данных для экспорта")
            await state.clear()
            return
        
        # Создаем файл
        import os
        import csv
        import json
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conversations_export_{timestamp}.{export_format}"
        filepath = os.path.join('data', 'exports', filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        if export_format == 'csv':
            # CSV экспорт
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(['Дата', 'Время', 'Отправитель', 'Получатель', 'Сообщение', 'Статус'])
                
                for conv in conversations:
                    timestamp_str = conv[7]
                    if isinstance(timestamp_str, str):
                        date_part = timestamp_str[:10]
                        time_part = timestamp_str[11:16]
                    else:
                        date_part = timestamp_str.strftime('%Y-%m-%d')
                        time_part = timestamp_str.strftime('%H:%M')
                    
                    writer.writerow([
                        date_part,
                        time_part,
                        conv[9],  # sender_name
                        conv[2] if conv[9] != conv[2] else conv[5],  # receiver
                        conv[6][:500],  # message (обрезаем)
                        'Раскрыто' if conv[8] else 'Анонимно'
                    ])
        
        elif export_format == 'json':
            # JSON экспорт
            export_data = []
            for conv in conversations:
                export_data.append({
                    'timestamp': str(conv[7]),
                    'sender': {
                        'name': conv[9],
                        'telegram_id': conv[0] if conv[9] == conv[1] else conv[3]
                    },
                    'receiver': {
                        'name': conv[2] if conv[9] != conv[2] else conv[5],
                        'telegram_id': conv[3] if conv[9] == conv[1] else conv[0]
                    },
                    'message': conv[6],
                    'is_revealed': bool(conv[8])
                })
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        else:  # TXT формат
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Экспорт переписок\n")
                f.write(f"Дата экспорта: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
                f.write(f"Количество сообщений: {len(conversations)}\n")
                f.write("="*60 + "\n\n")
                
                for conv in conversations:
                    timestamp_str = str(conv[7])[:19].replace('T', ' ')
                    f.write(f"Дата: {timestamp_str}\n")
                    f.write(f"От: {conv[9]}\n")
                    f.write(f"Кому: {conv[2] if conv[9] != conv[2] else conv[5]}\n")
                    f.write(f"Статус: {'Раскрыто' if conv[8] else 'Анонимно'}\n")
                    f.write(f"Сообщение: {conv[6]}\n")
                    f.write("-"*40 + "\n")
        
        # Отправляем файл
        file_size = os.path.getsize(filepath) / 1024  # KB
        
        await message.answer(
            f"✅ <b>Экспорт завершен!</b>\n\n"
            f"📁 Файл: <code>{filename}</code>\n"
            f"📊 Сообщений: {len(conversations)}\n"
            f"📦 Размер: {file_size:.1f} KB\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            parse_mode="HTML"
        )
        
        # Отправляем файл если он не слишком большой
        if file_size < 500:  # Telegram лимит ~50MB, но для надежности 500KB
            from aiogram.types import FSInputFile
            await message.answer_document(
                FSInputFile(filepath),
                caption=f"💾 Экспорт переписок ({export_format.upper()})"
            )
        else:
            await message.answer("⚠️ Файл слишком большой для отправки в Telegram")
        
    except Exception as e:
        logger.error(f"Ошибка экспорта: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка экспорта: {str(e)[:200]}")
    
    await state.clear()

# 2. ОЧИСТКА СТАРЫХ СООБЩЕНИЙ
@router.callback_query(F.data == "admin_cleanup_conversations")
async def admin_cleanup_conversations_start(callback: types.CallbackQuery, state: FSMContext):
    """Очистка старых сообщений"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    await callback.message.answer(
        "🧹 <b>Очистка старых сообщений</b>\n\n"
        "Эта функция удалит сообщения старше указанного количества дней.\n\n"
        "⚠️ <b>Внимание:</b> Это действие нельзя отменить!\n\n"
        "Введите количество дней (удалятся сообщения старше этого срока):\n"
        "Рекомендуется: 30, 60, 90 или 180 дней",
        parse_mode="HTML"
    )
    await state.set_state(ConversationStates.waiting_cleanup_days)
    await callback.answer()

@router.message(ConversationStates.waiting_cleanup_days)
async def admin_cleanup_conversations_execute(message: types.Message, state: FSMContext):
    """Выполнение очистки старых сообщений"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        days = int(message.text.strip())
        
        if days < 1:
            await message.answer("❌ Количество дней должно быть больше 0")
            return
        
        await message.answer(f"🔍 <b>Ищу сообщения старше {days} дней...</b>", parse_mode="HTML")
        
        # Считаем сколько будет удалено
        deleted_count = safe_execute_scalar("""
            SELECT COUNT(*) FROM anon_messages 
            WHERE timestamp < datetime('now', '-' || :days || ' days')
        """, {"days": days}) or 0
        
        if deleted_count == 0:
            await message.answer(f"✅ Нет сообщений старше {days} дней")
            await state.clear()
            return
        
        # Создаем бэкап
        from app.database_manager import db_manager
        backup_path = db_manager.create_backup(f"before_cleanup_{days}d.db", send_to_admins=False)
        
        await message.answer(
            f"⚠️ <b>Будет удалено: {deleted_count} сообщений</b>\n\n"
            f"Создан бэкап: {os.path.basename(backup_path) if backup_path else 'не удалось'}\n\n"
            f"Подтвердите удаление (да/нет):",
            parse_mode="HTML"
        )
        
        await state.update_data(days=days, deleted_count=deleted_count)
        
    except ValueError:
        await message.answer("❌ Введите корректное число дней")
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при очистке: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")
        await state.clear()

@router.message(ConversationStates.waiting_cleanup_days)
async def admin_cleanup_conversations_confirm(message: types.Message, state: FSMContext):
    """Подтверждение очистки"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    confirmation = message.text.strip().lower()
    data = await state.get_data()
    
    if confirmation not in ['да', 'yes', 'y', '+']:
        await message.answer("❌ Очистка отменена")
        await state.clear()
        return
    
    try:
        days = data.get('days')
        deleted_count = data.get('deleted_count', 0)
        
        # Выполняем удаление
        result = safe_execute_scalar("""
            DELETE FROM anon_messages 
            WHERE timestamp < datetime('now', '-' || :days || ' days')
            RETURNING COUNT(*)
        """, {"days": days})
        
        actual_deleted = result or 0
        
        await message.answer(
            f"✅ <b>Очистка завершена!</b>\n\n"
            f"🗑️ Удалено сообщений: {actual_deleted}\n"
            f"📅 Старше: {days} дней\n"
            f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"💾 Бэкап создан перед очисткой",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при удалении: {e}")
        await message.answer(f"❌ Ошибка при удалении: {str(e)[:200]}")
    
    await state.clear()

# 3. ОТПРАВКА СООБЩЕНИЙ ОТ ИМЕНИ БОТА
@router.callback_query(F.data == "admin_send_bot_message")
async def admin_send_bot_message_start(callback: types.CallbackQuery, state: FSMContext):
    """Отправка сообщения от имени бота"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    await callback.message.answer(
        "✉️ <b>Отправка сообщения от имени бота</b>\n\n"
        "Введите Telegram ID пользователя, которому хотите отправить сообщение:\n\n"
        "ℹ️ <i>Сообщение будет отправлено от имени бота, а не анонимно</i>",
        parse_mode="HTML"
    )
    await state.set_state(ConversationStates.waiting_send_message)
    await callback.answer()

@router.message(ConversationStates.waiting_send_message)
async def admin_send_bot_message_process(message: types.Message, state: FSMContext):
    """Обработка отправки сообщения от имени бота"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        telegram_id = int(message.text.strip())
        
        # Проверяем существование пользователя
        user = safe_execute_query_fetchone(
            "SELECT id, first_name FROM users WHERE telegram_id = :telegram_id",
            {"telegram_id": telegram_id}
        )
        
        if not user:
            await message.answer("❌ Пользователь не найден")
            await state.clear()
            return
        
        user_id = user[0]
        user_name = user[1] or "пользователь"
        
        await state.update_data(target_user_id=user_id, target_telegram_id=telegram_id)
        
        await message.answer(
            f"👤 <b>Получатель:</b> {user_name} (ID: <code>{telegram_id}</code>)\n\n"
            f"Введите текст сообщения:",
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.answer("❌ Введите корректный Telegram ID")
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)[:100]}")
        await state.clear()

# 4. АНАЛИТИКА АКТИВНОСТИ
@router.callback_query(F.data == "admin_activity_analysis")
async def admin_activity_analysis(callback: types.CallbackQuery):
    """Анализ активности пользователей в переписках"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        # Активность за последние 7 дней
        week_activity = safe_execute_query_fetchall("""
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as message_count,
                COUNT(DISTINCT sender_id) as active_senders,
                COUNT(DISTINCT receiver_id) as active_receivers
            FROM anon_messages 
            WHERE timestamp >= datetime('now', '-7 days')
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        """)
        
        # Самые активные пользователи
        top_active = safe_execute_query_fetchall("""
            SELECT 
                u.telegram_id,
                u.first_name,
                COUNT(*) as total_messages,
                SUM(CASE WHEN am.sender_id = u.id THEN 1 ELSE 0 END) as sent,
                SUM(CASE WHEN am.receiver_id = u.id THEN 1 ELSE 0 END) as received,
                MAX(am.timestamp) as last_activity
            FROM users u
            JOIN anon_messages am ON u.id = am.sender_id OR u.id = am.receiver_id
            WHERE am.timestamp >= datetime('now', '-30 days')
            GROUP BY u.id, u.telegram_id, u.first_name
            ORDER BY total_messages DESC
            LIMIT 10
        """)
        
        # Самые длинные переписки
        longest_conversations = safe_execute_query_fetchall("""
            SELECT 
                u1.first_name as user1,
                u2.first_name as user2,
                COUNT(*) as message_count,
                MIN(am.timestamp) as start_date,
                MAX(am.timestamp) as last_date
            FROM anon_messages am
            JOIN users u1 ON am.sender_id = u1.id OR am.receiver_id = u1.id
            JOIN users u2 ON (am.sender_id = u2.id OR am.receiver_id = u2.id) AND u2.id > u1.id
            GROUP BY u1.id, u2.id, u1.first_name, u2.first_name
            HAVING COUNT(*) > 10
            ORDER BY message_count DESC
            LIMIT 5
        """)
        
        analysis_text = "📊 <b>Анализ активности переписок</b>\n\n"
        
        # Активность по дням
        analysis_text += "📈 <b>Активность за 7 дней:</b>\n"
        total_week_messages = 0
        for activity in week_activity[:5]:  # Последние 5 дней
            date_str = activity[0]
            if isinstance(date_str, str):
                date_display = date_str[-5:]  # Последние 5 символов (MM-DD)
            else:
                date_display = activity[0].strftime('%m-%d')
            
            analysis_text += (
                f"• {date_display}: {activity[1]} сообщ. "
                f"({activity[2]}+{activity[3]} пользоват.)\n"
            )
            total_week_messages += activity[1]
        
        analysis_text += f"📅 Всего за неделю: <b>{total_week_messages}</b> сообщений\n\n"
        
        # Топ активных пользователей
        analysis_text += "🏆 <b>Самые активные пользователи:</b>\n"
        for i, user in enumerate(top_active[:5], 1):
            user_name = user[1] or f"User_{user[0]}"
            analysis_text += (
                f"{i}. {user_name}: {user[2]} сообщ. "
                f"(📤{user[3]}/📨{user[4]})\n"
            )
        
        analysis_text += "\n💬 <b>Самые длинные переписки:</b>\n"
        for conv in longest_conversations:
            analysis_text += (
                f"• {conv[0]} ↔ {conv[1]}: {conv[2]} сообщ.\n"
            )
        
        # Статистика раскрытий
        revealed_stats = safe_execute_scalar(
            "SELECT COUNT(*) FROM anon_messages WHERE is_revealed = 1"
        ) or 0
        total_messages = safe_execute_scalar(
            "SELECT COUNT(*) FROM anon_messages"
        ) or 1
        
        reveal_percentage = (revealed_stats / total_messages) * 100
        
        analysis_text += f"\n👁️ <b>Раскрытия:</b> {revealed_stats}/{total_messages} ({reveal_percentage:.1f}%)\n"
        
        await callback.message.answer(analysis_text, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка анализа активности: {e}", exc_info=True)
        await callback.answer("❌ Ошибка анализа")

# 5. ВОССТАНОВЛЕНИЕ УДАЛЕННЫХ СООБЩЕНИЙ
@router.callback_query(F.data == "admin_recover_messages")
async def admin_recover_messages(callback: types.CallbackQuery):
    """Восстановление удаленных сообщений из бэкапа"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        # Ищем последние бэкапы
        from app.database_manager import db_manager
        backups = db_manager.list_backups()
        
        if not backups:
            await callback.message.answer("📭 <b>Бэкапы не найдены</b>", parse_mode="HTML")
            await callback.answer()
            return
        
        # Показываем последние 3 бэкапа
        backup_info = "💾 <b>Доступные бэкапы для восстановления:</b>\n\n"
        
        for i, backup in enumerate(reversed(backups[-3:]), 1):
            backup_name = backup["name"]
            created = backup["created"].strftime("%d.%m.%Y %H:%M")
            size_mb = backup["size_mb"]
            valid = "✅" if backup["is_valid"] else "❌"
            
            # Получаем информацию о сообщениях в бэкапе
            import sqlite3
            try:
                conn = sqlite3.connect(backup["path"])
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM anon_messages")
                msg_count = cursor.fetchone()[0] or 0
                conn.close()
            except:
                msg_count = "?"
            
            backup_info += (
                f"{i}. <code>{backup_name}</code>\n"
                f"   📅 {created} | 📊 {size_mb:.1f} MB\n"
                f"   📨 Сообщений: {msg_count} | {valid}\n"
                f"   🔄 /recover_from_{i}\n\n"
            )
        
        await callback.message.answer(backup_info, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка восстановления: {e}", exc_info=True)
        await callback.answer("❌ Ошибка")

# ==================== АДМИНСКИЕ КОМАНДЫ ДЛЯ ПЕРЕПИСОК ====================

@router.message(Command("conversations"), admin_filter)
async def conversations_command(message: types.Message):
    """Команда для быстрого доступа к перепискам"""
    await admin_conversations(message)

@router.message(Command("find_conversation"), admin_filter)
async def find_conversation_command(message: types.Message):
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
                first_name = user[3] or "Без имени"
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

@router.message(F.text.startswith("/view_conversation_"), admin_filter)
async def view_conversation_by_ids_command(message: types.Message):
    """Посмотреть переписку между двумя пользователями"""
    try:
        # Формат: /view_conversation_user1id_user2id
        parts = message.text.replace("/view_conversation_", "").split("_")
        if len(parts) != 2:
            await message.answer("❌ Неверный формат: /view_conversation_id1_id2")
            return
        
        user1_id = int(parts[0])
        user2_id = int(parts[1])
        await show_conversation_detail(message, user1_id, user2_id)
    except ValueError:
        await message.answer("❌ Неверный формат ID")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

@router.callback_query(F.data == "back_to_conversations")
async def back_to_conversations(callback: types.CallbackQuery):
    """Вернуться к меню переписок"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return
    
    await admin_conversations(callback.message)
    await callback.answer()

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: types.CallbackQuery):
    """Вернуться к админ-панели"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return
    
    from app.handlers.admin_panel import admin_panel
    await admin_panel(callback.message)
    await callback.answer()

# Экспортируем router для подключения в основном файле
__all__ = ['router']
