"""
Админ-панель для управления переписками пользователей
ИСПРАВЛЕННАЯ ВЕРСИЯ: исправлено использование message_text вместо text
"""

import asyncio
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional

from aiogram import F, Router, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.database import get_engine
from app.database_utils import (
    safe_execute_query_fetchall, 
    safe_execute_query_fetchone, 
    safe_execute_scalar,
    safe_execute_query
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
    waiting_send_anonymous = State()
    waiting_anonymous_message = State()
    waiting_anonymous_target = State()

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
        last_activity_result = safe_execute_query_fetchone(
            "SELECT MAX(timestamp) FROM anon_messages"
        )
        
        if last_activity_result and last_activity_result[0]:
            last_activity = last_activity_result[0]
            try:
                if isinstance(last_activity, str):
                    last_activity = last_activity[:16].replace('T', ' ')
                else:
                    last_activity = last_activity.strftime('%d.%m.%Y %H:%M')
            except:
                last_activity = "неизвестно"
        else:
            last_activity = "не было активности"
        
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
            "• 🕵️‍♂️ Отправить анонимное сообщение\n"
            "• 📊 Анализ активности\n"
            "• 🔄 Восстановление сообщений\n"
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
                InlineKeyboardButton(text="🕵️‍♂️ Отпр. анонимно", callback_data="admin_send_anonymous"),
                InlineKeyboardButton(text="✉️ Отпр. от бота", callback_data="admin_send_bot_message")
            ],
            [
                InlineKeyboardButton(text="💾 Экспорт", callback_data="admin_export_conversations"),
                InlineKeyboardButton(text="🧹 Очистка", callback_data="admin_cleanup_conversations")
            ],
            [
                InlineKeyboardButton(text="📊 Анализ", callback_data="admin_activity_analysis"),
                InlineKeyboardButton(text="🔄 Восстановить", callback_data="admin_recover_messages")
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
        last_activity_result = safe_execute_query_fetchone("""
            SELECT MAX(timestamp) FROM anon_messages 
            WHERE sender_id = :user_id OR receiver_id = :user_id
        """, {"user_id": user_id})
        
        if last_activity_result and last_activity_result[0]:
            last_activity = last_activity_result[0]
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
    """Показать детали переписки между двумя пользователями (ИСПРАВЛЕННАЯ)"""
    try:
        # Получаем информацию о пользователях
        user1 = safe_execute_query_fetchone(
            "SELECT id, telegram_id, first_name, username FROM users WHERE id = :user_id",
            {"user_id": user1_id}
        )
        user2 = safe_execute_query_fetchone(
            "SELECT id, telegram_id, first_name, username FROM users WHERE id = :user_id",
            {"user_id": user2_id}
        )
        
        if not user1 or not user2:
            await message.answer("❌ Один из пользователей не найден")
            return
        
        user1_db_id = user1[0]
        user1_telegram_id = user1[1]
        user1_name = user1[2] or f"User_{user1[1]}"
        user1_username = user1[3] or "нет"
        
        user2_db_id = user2[0]
        user2_telegram_id = user2[1]
        user2_name = user2[2] or f"User_{user2[1]}"
        user2_username = user2[3] or "нет"
        
        # Получаем историю сообщений между этими пользователями
        messages = safe_execute_query_fetchall("""
            SELECT 
                am.id,
                am.sender_id,
                am.receiver_id,
                am.text,  
                am.timestamp,
                am.is_revealed
            FROM anon_messages am
            WHERE (am.sender_id = :user1_id AND am.receiver_id = :user2_id)
               OR (am.sender_id = :user2_id AND am.receiver_id = :user1_id)
            ORDER BY am.timestamp ASC
        """, {"user1_id": user1_db_id, "user2_id": user2_db_id})
        
        if not messages:
            conversation_info = (
                f"💬 <b>Переписка между:</b>\n"
                f"👤 <b>{user1_name}</b> (ID: <code>{user1_telegram_id}</code>) @{user1_username}\n"
                f"👤 <b>{user2_name}</b> (ID: <code>{user2_telegram_id}</code>) @{user2_username}\n\n"
                f"📭 <b>Сообщений не найдено</b>\n\n"
                f"🔍 <b>Отладка:</b>\n"
                f"• ID пользователя 1 в БД: {user1_db_id}\n"
                f"• ID пользователя 2 в БД: {user2_db_id}\n"
                f"• Проверка запроса: SELECT COUNT(*) FROM anon_messages WHERE (sender_id={user1_db_id} AND receiver_id={user2_db_id}) OR (sender_id={user2_db_id} AND receiver_id={user1_db_id})\n"
            )
            await message.answer(conversation_info, parse_mode="HTML")
            return
        
        # Получаем статистику
        user1_sent = sum(1 for msg in messages if msg[1] == user1_db_id)
        user2_sent = sum(1 for msg in messages if msg[1] == user2_db_id)
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
            f"👤 <b>{user1_name}</b> (ID: <code>{user1_telegram_id}</code>) @{user1_username}\n"
            f"👤 <b>{user2_name}</b> (ID: <code>{user2_telegram_id}</code>) @{user2_username}\n\n"
            f"📊 <b>Статистика диалога:</b>\n"
            f"• Всего сообщений: <b>{len(messages)}</b>\n"
            f"• {user1_name}: <b>{user1_sent}</b> сообщений\n"
            f"• {user2_name}: <b>{user2_sent}</b> сообщений\n"
            f"• Раскрыто сообщений: <b>{revealed_count}</b>\n"
            f"• Начало: {first_time}\n"
            f"• Последнее: {last_time}\n"
            f"────────────────────\n\n"
            f"<b>История переписки (последние {min(len(messages), 30)} из {len(messages)}):</b>\n"
        )
        
        # Отображаем сообщения (последние 30)
        for msg in messages[-30:]:
            msg_id = msg[0]
            sender_id = msg[1]
            receiver_id = msg[2]
            message_text = msg[3]  
            timestamp = msg[4]
            is_revealed = msg[5]
            
            # Определяем отправителя и получателя
            if sender_id == user1_db_id:
                sender_display = user1_name
                receiver_display = user2_name
                direction = "➡️"
            else:
                sender_display = user2_name
                receiver_display = user1_name
                direction = "⬅️"
            
            # Форматируем время
            try:
                if isinstance(timestamp, str):
                    message_time = timestamp[11:16]
                else:
                    message_time = timestamp.strftime('%H:%M')
            except:
                message_time = "??:??"
            
            # Обрезаем текст если слишком длинный
            display_text = message_text
            if len(display_text) > 100:
                display_text = display_text[:100] + "..."
            
            # Экранируем HTML-символы
            display_text = display_text.replace('<', '&lt;').replace('>', '&gt;')
            
            # Статус раскрытия
            reveal_status = "👁️" if is_revealed else "🕵️"
            
            conversation_info += (
                f"<b>{message_time}</b> {direction} <b>{sender_display}</b> → {receiver_display} {reveal_status}:\n"
                f"📝 {display_text}\n"
                f"<i>ID сообщения: {msg_id}</i>\n"
                f"────────────────────\n"
            )
        
        # Создаем клавиатуру для навигации
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🕵️‍♂️ Отпр. анонимно", callback_data=f"admin_send_anonymous_to_{user1_db_id}_{user2_db_id}"),
                InlineKeyboardButton(text="🔍 Поиск", callback_data=f"admin_search_in_{user1_db_id}_{user2_db_id}")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_view_conversations_{user1_db_id}")
            ]
        ])
        
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
        await message.answer(f"❌ Ошибка загрузки переписки: {str(e)[:200]}\n\n"
                           f"ID пользователей: {user1_id} и {user2_id}")

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
        # ИСПРАВЛЕННЫЙ ЗАПРОС: используем правильное имя колонки text
        messages = safe_execute_query_fetchall("""
            SELECT 
                am.id,
                am.text,  
                am.timestamp,
                am.is_revealed,
                sender.telegram_id as sender_tg_id,
                sender.first_name as sender_name,
                receiver.telegram_id as receiver_tg_id,
                receiver.first_name as receiver_name
            FROM anon_messages am
            LEFT JOIN users sender ON am.sender_id = sender.id
            LEFT JOIN users receiver ON am.receiver_id = receiver.id
            WHERE am.text LIKE :search_text  # ИСПРАВЛЕНО: было message_text
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
            message_text = msg[1]  # ИСПРАВЛЕНО: поле text
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
            "SELECT COUNT(*) FROM anon_messages WHERE text LIKE :search_text",  # ИСПРАВЛЕНО: было message_text
            {"search_text": f"%{search_text}%"}
        ) or 0
        
        search_results += f"\n📈 <b>Всего найдено сообщений:</b> {total_found}"
        
        await message.answer(search_results, parse_mode="HTML")
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_search_messages_result: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка поиска: {str(e)[:100]}")
        await state.clear()

# ==================== НОВАЯ ФУНКЦИЯ: ОТПРАВКА АНОНИМНЫХ СООБЩЕНИЙ ====================

@router.callback_query(F.data == "admin_send_anonymous")
async def admin_send_anonymous_start(callback: types.CallbackQuery, state: FSMContext):
    """Начать отправку анонимного сообщения от имени админа"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    await callback.message.answer(
        "🕵️‍♂️ <b>Отправка анонимного сообщения</b>\n\n"
        "Выберите действие:\n\n"
        "1️⃣ <b>Отправить существующему пользователю</b> - по его Telegram ID\n"
        "2️⃣ <b>Создать новую переписку</b> - между двумя пользователями\n\n"
        "Введите 1 или 2:",
        parse_mode="HTML"
    )
    await state.set_state(ConversationStates.waiting_send_anonymous)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_send_anonymous_to_"))
async def admin_send_anonymous_to_conversation(callback: types.CallbackQuery, state: FSMContext):
    """Отправить анонимное сообщение в существующую переписку"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        # Формат: admin_send_anonymous_to_{user1_id}_{user2_id}
        data_parts = callback.data.split("_")
        if len(data_parts) != 7:
            await callback.answer("❌ Неверный формат запроса")
            return
        
        user1_id = int(data_parts[4])
        user2_id = int(data_parts[5])
        
        await state.update_data(user1_id=user1_id, user2_id=user2_id, mode="existing")
        
        await callback.message.answer(
            "🕵️‍♂️ <b>Отправка анонимного сообщения</b>\n\n"
            f"💬 Переписка между пользователями ID: {user1_id} и {user2_id}\n\n"
            "Введите текст анонимного сообщения:\n\n"
            "💡 <i>Сообщение будет отправлено как анонимное от 'Неизвестного отправителя'</i>",
            parse_mode="HTML"
        )
        await state.set_state(ConversationStates.waiting_anonymous_message)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка отправки анонимного сообщения: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.message(ConversationStates.waiting_send_anonymous)
async def admin_send_anonymous_process(message: types.Message, state: FSMContext):
    """Обработка выбора режима отправки"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    mode = message.text.strip()
    
    if mode == "1":
        # Отправка существующему пользователю
        await message.answer(
            "👤 <b>Отправка анонимного сообщения пользователю</b>\n\n"
            "Введите Telegram ID получателя:\n"
            "Пример: <code>123456789</code>\n\n"
            "ℹ️ <i>Сообщение будет отправлено анонимно от 'Неизвестного отправителя'</i>",
            parse_mode="HTML"
        )
        await state.set_state(ConversationStates.waiting_anonymous_target)
        await state.update_data(mode="single")
        
    elif mode == "2":
        # Создание новой переписки
        await message.answer(
            "👥 <b>Создание новой анонимной переписки</b>\n\n"
            "Введите Telegram ID двух пользователей через пробел:\n"
            "Пример: <code>123456789 987654321</code>\n\n"
            "💡 <i>Первым будет отправитель, вторым - получатель</i>",
            parse_mode="HTML"
        )
        await state.set_state(ConversationStates.waiting_anonymous_target)
        await state.update_data(mode="new")
        
    else:
        await message.answer("❌ Неверный выбор. Введите 1 или 2")
        await state.clear()

@router.message(ConversationStates.waiting_anonymous_target)
async def admin_send_anonymous_target(message: types.Message, state: FSMContext):
    """Обработка цели для анонимного сообщения"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    data = await state.get_data()
    mode = data.get("mode")
    
    try:
        if mode == "single":
            # Отправка одному пользователю
            telegram_id = int(message.text.strip())
            
            # Находим пользователя
            user = safe_execute_query_fetchone(
                "SELECT id, first_name FROM users WHERE telegram_id = :telegram_id",
                {"telegram_id": telegram_id}
            )
            
            if not user:
                await message.answer(f"❌ Пользователь с ID {telegram_id} не найден")
                await state.clear()
                return
            
            user_id = user[0]
            user_name = user[1] or "пользователь"
            
            await state.update_data(
                receiver_id=user_id,
                receiver_telegram_id=telegram_id,
                receiver_name=user_name
            )
            
            await message.answer(
                f"👤 <b>Получатель:</b> {user_name} (ID: <code>{telegram_id}</code>)\n\n"
                f"Введите текст анонимного сообщения:\n\n"
                f"💡 <i>Отправитель будет показан как 'Неизвестный'</i>",
                parse_mode="HTML"
            )
            await state.set_state(ConversationStates.waiting_anonymous_message)
            
        elif mode == "new":
            # Создание новой переписки
            ids = message.text.strip().split()
            if len(ids) != 2:
                await message.answer("❌ Введите два ID через пробел")
                return
            
            sender_id = int(ids[0])
            receiver_id = int(ids[1])
            
            # Находим пользователей
            sender = safe_execute_query_fetchone(
                "SELECT id, first_name FROM users WHERE telegram_id = :telegram_id",
                {"telegram_id": sender_id}
            )
            receiver = safe_execute_query_fetchone(
                "SELECT id, first_name FROM users WHERE telegram_id = :telegram_id",
                {"telegram_id": receiver_id}
            )
            
            if not sender:
                await message.answer(f"❌ Отправитель с ID {sender_id} не найден")
                await state.clear()
                return
            
            if not receiver:
                await message.answer(f"❌ Получатель с ID {receiver_id} не найден")
                await state.clear()
                return
            
            await state.update_data(
                sender_id=sender[0],
                receiver_id=receiver[0],
                sender_telegram_id=sender_id,
                receiver_telegram_id=receiver_id,
                sender_name=sender[1] or "Отправитель",
                receiver_name=receiver[1] or "Получатель"
            )
            
            await message.answer(
                f"👥 <b>Новая переписка:</b>\n"
                f"📤 От: {sender[1]} (ID: <code>{sender_id}</code>)\n"
                f"📨 Кому: {receiver[1]} (ID: <code>{receiver_id}</code>)\n\n"
                f"Введите текст анонимного сообщения:\n\n"
                f"💡 <i>Сообщение будет отправлено анонимно</i>",
                parse_mode="HTML"
            )
            await state.set_state(ConversationStates.waiting_anonymous_message)
            
    except ValueError:
        await message.answer("❌ Введите корректные числовые ID")
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка обработки цели: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:100]}")
        await state.clear()

@router.message(ConversationStates.waiting_anonymous_message)
async def admin_send_anonymous_final(message: types.Message, state: FSMContext, bot: Bot):
    """Финальная отправка анонимного сообщения"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    data = await state.get_data()
    mode = data.get("mode")
    message_text = message.text.strip()
    
    if not message_text:
        await message.answer("❌ Сообщение не может быть пустым")
        await state.clear()
        return
    
    try:
        if mode == "single":
            # Отправка одному пользователю
            receiver_id = data.get("receiver_id")
            receiver_telegram_id = data.get("receiver_telegram_id")
            receiver_name = data.get("receiver_name")
            
            # Вставляем сообщение в БД (sender_id = NULL для анонимности)
            result = safe_execute_query(
                """
                INSERT INTO anon_messages (sender_id, receiver_id, text, timestamp, is_revealed)
                VALUES (NULL, :receiver_id, :message_text, datetime('now'), 0)
                """,  # ИСПРАВЛЕНО: text вместо message_text
                {"receiver_id": receiver_id, "message_text": message_text}
            )
            
            if result:
                # Отправляем уведомление получателю
                try:
                    await bot.send_message(
                        chat_id=receiver_telegram_id,
                        text=f"💌 Вам анонимное сообщение:\n\n{message_text}\n\n🕵️‍♂️ Отправитель скрыт",
                        parse_mode="HTML"
                    )
                    
                    await message.answer(
                        f"✅ <b>Анонимное сообщение отправлено!</b>\n\n"
                        f"👤 <b>Получатель:</b> {receiver_name}\n"
                        f"📝 <b>Сообщение:</b> {message_text[:50]}...\n"
                        f"🕵️‍♂️ <b>Статус:</b> Анонимно\n"
                        f"⏰ <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    await message.answer(
                        f"⚠️ <b>Сообщение сохранено в БД, но не отправлено:</b>\n\n"
                        f"Ошибка: {str(e)[:100]}\n\n"
                        f"Получатель получит сообщение при следующем запуске бота.",
                        parse_mode="HTML"
                    )
            else:
                await message.answer("❌ Ошибка сохранения сообщения в БД")
                
        elif mode == "new":
            # Создание новой переписки
            sender_id = data.get("sender_id")
            receiver_id = data.get("receiver_id")
            sender_telegram_id = data.get("sender_telegram_id")
            receiver_telegram_id = data.get("receiver_telegram_id")
            sender_name = data.get("sender_name")
            receiver_name = data.get("receiver_name")
            
            # Вставляем сообщение в БД
            result = safe_execute_query(
                """
                INSERT INTO anon_messages (sender_id, receiver_id, text, timestamp, is_revealed)
                VALUES (:sender_id, :receiver_id, :message_text, datetime('now'), 0)
                """,  
                {"sender_id": sender_id, "receiver_id": receiver_id, "message_text": message_text}
            )
            
            if result:
                # Отправляем уведомление получателю
                try:
                    await bot.send_message(
                        chat_id=receiver_telegram_id,
                        text=f"💌 Вам анонимное сообщение:\n\n{message_text}\n\n🕵️‍♂️ Отправитель скрыт",
                        parse_mode="HTML"
                    )
                    
                    await message.answer(
                        f"✅ <b>Новая анонимная переписка создана!</b>\n\n"
                        f"📤 <b>От:</b> {sender_name} (анонимно)\n"
                        f"📨 <b>Кому:</b> {receiver_name}\n"
                        f"📝 <b>Сообщение:</b> {message_text[:50]}...\n"
                        f"🕵️‍♂️ <b>Статус:</b> Анонимно\n"
                        f"⏰ <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
                        f"💬 <b>Просмотреть переписку:</b>\n"
                        f"/view_conversation_{sender_id}_{receiver_id}",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    await message.answer(
                        f"⚠️ <b>Переписка создана в БД, но сообщение не отправлено:</b>\n\n"
                        f"Ошибка: {str(e)[:100]}\n\n"
                        f"Получатель получит сообщение при следующем запуске бота.",
                        parse_mode="HTML"
                    )
            else:
                await message.answer("❌ Ошибка создания переписки в БД")
                
        elif mode == "existing":
            # Отправка в существующую переписку
            user1_id = data.get("user1_id")
            user2_id = data.get("user2_id")
            
            # Находим Telegram ID пользователей
            user1 = safe_execute_query_fetchone(
                "SELECT telegram_id, first_name FROM users WHERE id = :user_id",
                {"user_id": user1_id}
            )
            user2 = safe_execute_query_fetchone(
                "SELECT telegram_id, first_name FROM users WHERE id = :user_id",
                {"user_id": user2_id}
            )
            
            if not user1 or not user2:
                await message.answer("❌ Один из пользователей не найден")
                await state.clear()
                return
            
            # Выбираем случайного отправителя для имитации
            import random
            sender_id = random.choice([user1_id, user2_id])
            receiver_id = user1_id if sender_id == user2_id else user2_id
            
            sender_info = user1 if sender_id == user1_id else user2
            receiver_info = user2 if receiver_id == user2_id else user1
            
            # Вставляем сообщение в БД
            result = safe_execute_query(
                """
                INSERT INTO anon_messages (sender_id, receiver_id, text, timestamp, is_revealed)
                VALUES (:sender_id, :receiver_id, :message_text, datetime('now'), 0)
                """,  
                {"sender_id": sender_id, "receiver_id": receiver_id, "message_text": message_text}
            )
            
            if result:
                # Отправляем уведомление получателю
                try:
                    await bot.send_message(
                        chat_id=receiver_info[0],
                        text=f"💌 Вам анонимное сообщение:\n\n{message_text}\n\n🕵️‍♂️ Отправитель скрыт",
                        parse_mode="HTML"
                    )
                    
                    await message.answer(
                        f"✅ <b>Анонимное сообщение добавлено в переписку!</b>\n\n"
                        f"💬 <b>Переписка:</b> {sender_info[1]} ↔ {receiver_info[1]}\n"
                        f"📤 <b>От имени:</b> {sender_info[1]} (анонимно)\n"
                        f"📨 <b>Кому:</b> {receiver_info[1]}\n"
                        f"📝 <b>Сообщение:</b> {message_text[:50]}...\n"
                        f"🕵️‍♂️ <b>Статус:</b> Анонимно\n"
                        f"⏰ <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
                        f"💬 <b>Просмотреть обновленную переписку:</b>\n"
                        f"/view_conversation_{user1_id}_{user2_id}",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    await message.answer(
                        f"⚠️ <b>Сообщение добавлено в БД, но не отправлено:</b>\n\n"
                        f"Ошибка: {str(e)[:100]}\n\n"
                        f"Получатель получит сообщение при следующем запуске бота.",
                        parse_mode="HTML"
                    )
            else:
                await message.answer("❌ Ошибка добавления сообщения в БД")
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка отправки анонимного сообщения: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка отправки: {str(e)[:200]}")
        await state.clear()

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

# ==================== ОТЛАДОЧНЫЕ КОМАНДЫ ====================

@router.message(Command("debug_conversation"))
async def debug_conversation_command(message: types.Message):
    """Отладка переписки"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return
    
    try:
        args = message.text.split()
        if len(args) != 3:
            await message.answer("❌ Использование: /debug_conversation ID1 ID2")
            return
        
        user1_id = int(args[1])
        user2_id = int(args[2])
        
        # Проверяем существование пользователей в БД
        user1 = safe_execute_query_fetchone(
            "SELECT id, telegram_id, first_name FROM users WHERE id = :user_id",
            {"user_id": user1_id}
        )
        user2 = safe_execute_query_fetchone(
            "SELECT id, telegram_id, first_name FROM users WHERE id = :user_id",
            {"user_id": user2_id}
        )
        
        if not user1:
            await message.answer(f"❌ Пользователь 1 (ID в БД: {user1_id}) не найден")
            return
        if not user2:
            await message.answer(f"❌ Пользователь 2 (ID в БД: {user2_id}) не найден")
            return
        
        # Проверяем сообщения между ними
        messages = safe_execute_query_fetchall("""
            SELECT 
                am.id,
                am.sender_id,
                am.receiver_id,
                am.text, 
                am.timestamp
            FROM anon_messages am
            WHERE (am.sender_id = :user1_id AND am.receiver_id = :user2_id)
               OR (am.sender_id = :user2_id AND am.receiver_id = :user1_id)
            ORDER BY am.timestamp ASC
        """, {"user1_id": user1[0], "user2_id": user2[0]})
        
        debug_info = (
            f"🔍 <b>Отладка переписки:</b>\n\n"
            f"👤 <b>Пользователь 1:</b>\n"
            f"• ID в БД: {user1[0]}\n"
            f"• Telegram ID: {user1[1]}\n"
            f"• Имя: {user1[2]}\n\n"
            f"👤 <b>Пользователь 2:</b>\n"
            f"• ID в БД: {user2[0]}\n"
            f"• Telegram ID: {user2[1]}\n"
            f"• Имя: {user2[2]}\n\n"
            f"📨 <b>Сообщения:</b>\n"
            f"• Найдено: {len(messages)} сообщений\n"
        )
        
        if messages:
            debug_info += f"\n📋 <b>Примеры сообщений:</b>\n"
            for i, msg in enumerate(messages[:3], 1):
                debug_info += (
                    f"{i}. ID: {msg[0]}, От: {msg[1]}, Кому: {msg[2]}\n"
                    f"   Текст: {msg[3][:50]}...\n"
                    f"   Время: {msg[4]}\n"
                )
        
        await message.answer(debug_info, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка отладки: {e}")

@router.message(Command("check_messages"))
async def check_messages_command(message: types.Message):
    """Проверить все сообщения в БД"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return
    
    try:
        # Получаем общую статистику
        total_messages = safe_execute_scalar("SELECT COUNT(*) FROM anon_messages") or 0
        today_messages = safe_execute_scalar(
            "SELECT COUNT(*) FROM anon_messages WHERE DATE(timestamp) = DATE('now')"
        ) or 0
        
        # Получаем несколько последних сообщений
        recent_messages = safe_execute_query_fetchall("""
            SELECT 
                am.id,
                am.sender_id,
                am.receiver_id,
                am.text, 
                am.timestamp,
                u1.first_name as sender_name,
                u2.first_name as receiver_name
            FROM anon_messages am
            LEFT JOIN users u1 ON am.sender_id = u1.id
            LEFT JOIN users u2 ON am.receiver_id = u2.id
            ORDER BY am.timestamp DESC
            LIMIT 5
        """)
        
        check_info = (
            f"📊 <b>Проверка сообщений в БД:</b>\n\n"
            f"• Всего сообщений: <b>{total_messages}</b>\n"
            f"• Сообщений сегодня: <b>{today_messages}</b>\n\n"
            f"📨 <b>Последние сообщения:</b>\n"
        )
        
        if recent_messages:
            for msg in recent_messages:
                sender_name = msg[5] or f"User_{msg[1]}"
                receiver_name = msg[6] or f"User_{msg[2]}"
                message_preview = msg[3][:30] + "..." if len(msg[3]) > 30 else msg[3]
                
                check_info += (
                    f"• {sender_name} → {receiver_name}: {message_preview}\n"
                )
        else:
            check_info += "📭 Нет сообщений в базе данных\n"
        
        await message.answer(check_info, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка проверки: {e}")

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
