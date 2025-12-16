"""
Админ-панель для управления ботом
"""
from aiogram import F, Router, types, Bot  
import os
import sys
import time
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
import asyncio
from aiogram.types import Message, CallbackQuery, FSInputFile
import json
from app.database_manager import db_manager
from app.database import get_db, force_reconnect, get_engine
from app.models import User, AnonMessage, Payment
from app.config import ADMIN_IDS
from app.keyboards_admin import (
    admin_main_menu, admin_users_menu, admin_prices_menu,
    admin_stats_menu, admin_broadcast_menu, admin_user_actions_menu,
    admin_price_management_menu, admin_confirm_keyboard, admin_pagination_keyboard,
    exit_admin_keyboard, admin_settings_menu
)
from app.keyboards import main_menu
from app.price_service import price_service
from app.broadcast_service import broadcast_service
from app.payment_service import payment_service
from app.database_utils import (
    safe_execute_query,
    get_user_by_id,
    get_users_count,
    get_messages_count,
    get_payments_count,
    get_revenue
)
import logging

logger = logging.getLogger(__name__)

router = Router()

class AdminStates(StatesGroup):
    waiting_user_search = State()
    waiting_broadcast_message = State()
    waiting_user_message = State()
    waiting_price_edit = State()
    waiting_reveals_set = State()
    waiting_price_value = State()
    waiting_discount_value = State()
    waiting_reveals_count = State()
    waiting_balance_change = State()
    waiting_system_message = State()

def is_admin(user_id: int):
    return user_id in ADMIN_IDS

def admin_filter(message: Message) -> bool:
    return message.from_user.id in ADMIN_IDS

# ==================== СИСТЕМНЫЕ КОМАНДЫ ====================

@router.message(Command("admin"))
@router.message(F.text == "👑 Админ-панель")
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        engine = get_engine()
        with engine.connect() as conn:
            # Проверяем наличие таблиц
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result.fetchall()]
            
            if 'users' not in tables:
                await message.answer("⚠️ <b>Таблица users не найдена</b>", parse_mode="HTML")
                return
            
            # Получаем статистику через SQL с использованием text()
            result = conn.execute(text("SELECT COUNT(*) FROM users"))
            total_users = result.scalar() or 0
            
            # Для даты используем параметризованные запросы
            today = datetime.now().date()
            result = conn.execute(
                text("SELECT COUNT(*) FROM users WHERE DATE(created_at) = :today"),
                {"today": today}
            )
            today_users = result.scalar() or 0
            
            result = conn.execute(text("SELECT COUNT(*) FROM anon_messages"))
            total_messages = result.scalar() or 0
            
            result = conn.execute(
                text("SELECT COUNT(*) FROM anon_messages WHERE DATE(timestamp) = :today"),
                {"today": today}
            )
            today_messages = result.scalar() or 0
            
            result = conn.execute(text("SELECT COUNT(*) FROM payments WHERE status = 'completed'"))
            total_payments = result.scalar() or 0
            
            result = conn.execute(text("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'completed'"))
            total_revenue = result.scalar() or 0

            week_ago = datetime.now() - timedelta(days=7)
            result = conn.execute(
                text("SELECT COUNT(DISTINCT sender_id) FROM anon_messages WHERE timestamp >= :week_ago"),
                {"week_ago": week_ago}
            )
            active_users = result.scalar() or 0

        admin_message = (
            "👑 <b>Админ-панель ShadowTalk</b>\n\n"
            "📊 <b>Ключевая статистика:</b>\n"
            f"• 👥 Всего пользователей: <b>{total_users}</b>\n"
            f"• 🆕 Новых сегодня: <b>{today_users}</b>\n"
            f"• 🔥 Активных за неделю: <b>{active_users}</b>\n"
            f"• 📨 Всего сообщений: <b>{total_messages}</b>\n"
            f"• 📨 Сообщений сегодня: <b>{today_messages}</b>\n"
            f"• 💰 Всего продаж: <b>{total_payments}</b>\n"
            f"• 🏦 Общая выручка: <b>{total_revenue / 100:.2f}₽</b>\n\n"
            "🚀 <b>Быстрые действия:</b>\n"
            "Используйте кнопки ниже для управления ботом"
        )

        await message.answer(admin_message, parse_mode="HTML", reply_markup=admin_main_menu())
        
    except Exception as e:
        logger.error(f"Ошибка в admin_panel: {e}")
        await message.answer(f"❌ Ошибка получения статистики: {str(e)[:200]}")

# ==================== УПРАВЛЕНИЕ БАЗОЙ ДАННЫХ ====================

@router.message(Command("reload_db"), admin_filter)
async def cmd_reload_db(message: Message):
    """Принудительно перезагрузить подключение к БД"""
    try:
        await message.answer("🔄 Принудительная перезагрузка подключения к БД...")
        
        # Перезагружаем подключение
        force_reconnect()
        
        # Ждем перезагрузки
        await asyncio.sleep(1)
        
        # Получаем актуальную статистику
        engine = get_engine()
        with engine.connect() as conn:
            # Проверяем наличие таблиц
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result.fetchall()]
            
            # Получаем статистику
            user_count = 0
            message_count = 0
            
            if 'users' in tables:
                result = conn.execute(text("SELECT COUNT(*) FROM users"))
                user_count = result.scalar() or 0
            
            if 'anon_messages' in tables:
                result = conn.execute(text("SELECT COUNT(*) FROM anon_messages"))
                message_count = result.scalar() or 0
        
        # Получаем информацию о файле БД
        db_info = db_manager.get_db_info()
        
        response_message = (
            f"✅ <b>Подключение к БД перезагружено!</b>\n\n"
            f"📊 <b>Актуальная статистика:</b>\n"
            f"📁 Файл: {os.path.basename(db_manager.db_path)}\n"
            f"📦 Размер: {db_info.get('size_mb', 0):.2f} MB\n"
            f"📂 Таблиц: {len(tables)}\n"
            f"👥 Пользователей: {user_count}\n"
            f"💬 Сообщений: {message_count}\n\n"
            f"✅ <b>Теперь все модули видят актуальные данные</b>"
        )
        
        await message.answer(response_message, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка перезагрузки БД: {str(e)}")

@router.message(Command("backup"), admin_filter)
async def cmd_backup(message: Message):
    """Создать бэкап БД"""
    try:
        await message.answer("💾 Создание бэкапа...")
        
        backup_path = db_manager.create_backup()
        
        if backup_path:
            backup_name = os.path.basename(backup_path)
            backup_size = os.path.getsize(backup_path) / (1024 * 1024)
            
            response = (
                f"✅ <b>Бэкап создан успешно!</b>\n\n"
                f"📁 Имя: <code>{backup_name}</code>\n"
                f"📊 Размер: {backup_size:.2f} MB\n"
                f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}"
            )
            
            try:
                await message.answer_document(
                    FSInputFile(backup_path),
                    caption=response,
                    parse_mode="HTML"
                )
            except:
                await message.answer(response, parse_mode="HTML")
        else:
            await message.answer("❌ Не удалось создать бэкап.")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")

@router.message(Command("backups"), admin_filter)
async def cmd_backups(message: Message):
    """Показать список бэкапов"""
    try:
        backups = db_manager.list_backups()
        
        if not backups:
            await message.answer("📭 Бэкапы не найдены")
            return
        
        response = "📂 <b>Список бэкапов:</b>\n\n"
        
        for i, backup in enumerate(reversed(backups[-10:]), 1):
            created = backup["created"].strftime("%d.%m.%Y %H:%M")
            size_mb = backup["size_mb"]
            valid = "✅" if backup["is_valid"] else "❌"
            
            response += (
                f"{i}. <code>{backup['name']}</code>\n"
                f"   📅 {created} | 📊 {size_mb:.2f} MB | {valid}\n\n"
            )
        
        db_info = db_manager.get_db_info()
        response += (
            f"📊 <b>Статистика БД:</b>\n"
            f"Размер: {db_info.get('size_mb', 0):.2f} MB\n"
            f"Таблиц: {len(db_info.get('tables', []))}\n"
            f"Всего бэкапов: {len(backups)}"
        )
        
        await message.answer(response, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@router.message(Command("restore"), admin_filter)
async def cmd_restore(message: Message):
    """Восстановить БД из бэкапа"""
    try:
        backups = db_manager.list_backups()
        
        if not backups:
            await message.answer("📭 Бэкапы не найдены")
            return
        
        response = "🔄 <b>Выберите бэкап для восстановления:</b>\n\n"
        
        for i, backup in enumerate(reversed(backups[-5:]), 1):
            created = backup["created"].strftime("%d.%m.%Y %H:%M")
            size_mb = backup["size_mb"]
            valid = "✅" if backup["is_valid"] else "❌"
            
            response += (
                f"{i}. <code>{backup['name']}</code>\n"
                f"   📅 {created} | 📊 {size_mb:.2f} MB | {valid}\n"
                f"   Команда: /restore_{i}\n\n"
            )
        
        response += "⚠️ <b>Внимание:</b> Текущая БД будет заменена!"
        
        await message.answer(response, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@router.message(F.text.startswith("/restore_"), admin_filter)
async def cmd_restore_selected(message: Message):
    """Восстановить из конкретного бэкапа"""
    try:
        cmd_parts = message.text.split("_")
        if len(cmd_parts) != 2:
            await message.answer("❌ Неверный формат команды")
            return
        
        try:
            backup_index = int(cmd_parts[1])
        except ValueError:
            await message.answer("❌ Неверный номер бэкапа")
            return
        
        backups = db_manager.list_backups()
        if not 1 <= backup_index <= min(5, len(backups)):
            await message.answer("❌ Неверный номер бэкапа")
            return
        
        selected_backup = list(reversed(backups[-5:]))[backup_index - 1]
        
        success = db_manager.restore_from_backup(selected_backup["path"])
        
        if success:
            await message.answer("🔄 Перезагружаю подключение к БД...")
            force_reconnect()
            
            await asyncio.sleep(2)
            
            db_info = db_manager.get_db_info()
            
            engine = get_engine()
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM users"))
                user_count = result.scalar() or 0
                
                result = conn.execute(text("SELECT COUNT(*) FROM anon_messages"))
                message_count = result.scalar() or 0
            
            response = (
                f"✅ <b>БД успешно восстановлена и перезагружена!</b>\n\n"
                f"📁 Из: {selected_backup['name']}\n"
                f"📅 Дата бэкапа: {selected_backup['created'].strftime('%d.%m.%Y %H:%M')}\n"
                f"📊 Размер: {db_info.get('size_mb', 0):.2f} MB\n"
                f"📂 Таблиц: {len(db_info.get('tables', []))}\n"
                f"👥 Пользователей: {user_count}\n"
                f"💬 Сообщений: {message_count}\n\n"
                f"✅ <b>Подключение к БД обновлено!</b>"
            )
        else:
            response = "❌ Не удалось восстановить БД"
        
        await message.answer(response, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@router.message(F.document, admin_filter)
async def handle_database_upload(message: types.Message, bot: Bot):
    """Обработка загрузки базы данных"""
    if not is_admin(message.from_user.id):
        return

    document = message.document
    
    if not document.file_name or not document.file_name.endswith('.db'):
        await message.answer("❌ Можно загружать только файлы баз данных (.db)")
        return
    
    MAX_SIZE = 100 * 1024 * 1024
    if document.file_size > MAX_SIZE:
        await message.answer(f"❌ Файл слишком большой. Максимальный размер: {MAX_SIZE // (1024*1024)}MB")
        return
    
    await message.answer("💾 Загружаю файл базы данных...")
    
    try:
        upload_dir = 'uploads'
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, document.file_name)
        
        file = await bot.get_file(document.file_id)
        await bot.download_file(file.file_path, file_path)
        
        if not db_manager.validate_backup(file_path):
            os.remove(file_path)
            await message.answer("❌ Файл не является валидной базой данных SQLite")
            return
        
        file_size_mb = document.file_size / (1024 * 1024)
        
        await message.answer(
            f"📁 <b>Файл загружен:</b>\n\n"
            f"📦 Имя: <code>{document.file_name}</code>\n"
            f"📊 Размер: {file_size_mb:.2f} MB\n\n"
            f"⚠️ <b>Внимание:</b> Текущая база данных будет заменена!\n\n"
            f"Подтвердите восстановление:",
            parse_mode="HTML",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="✅ Восстановить", 
                            callback_data=f"confirm_restore_{document.file_name}"
                        ),
                        types.InlineKeyboardButton(
                            text="❌ Отмена", 
                            callback_data="cancel_restore"
                        )
                    ]
                ]
            )
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки файла: {e}")
        await message.answer(f"❌ Ошибка загрузки файла: {str(e)[:200]}")

@router.callback_query(F.data.startswith("confirm_restore_"))
async def confirm_restore_database(callback: types.CallbackQuery, bot: Bot):
    """Подтверждение восстановления из загруженного файла"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    file_name = callback.data.replace("confirm_restore_", "")
    file_path = os.path.join('uploads', file_name)
    
    if not os.path.exists(file_path):
        await callback.answer("❌ Файл не найден")
        return
    
    await callback.answer("🔄 Начинаю восстановление...")
    
    try:
        await callback.message.answer("💾 Создаю резервную копию текущей БД...")
        current_backup = db_manager.create_backup("before_upload_backup.db", send_to_admins=False)
        
        if current_backup:
            await callback.message.answer(f"✅ Текущая БД сохранена: {os.path.basename(current_backup)}")
        
        await callback.message.answer("🔄 Восстанавливаю базу данных...")
        
        success = db_manager.restore_from_backup(file_path)
        
        if success:
            await callback.message.answer("🔄 Перезагружаю подключение к БД...")
            force_reconnect()
            
            await asyncio.sleep(2)
            
            db_info = db_manager.get_db_info()
            
            engine = get_engine()
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM users"))
                user_count = result.scalar() or 0
                
                result = conn.execute(text("SELECT COUNT(*) FROM anon_messages"))
                message_count = result.scalar() or 0
            
            new_backup = db_manager.create_backup("after_restore_backup.db")
            
            response_message = (
                f"✅ <b>База данных успешно восстановлена и перезагружена!</b>\n\n"
                f"📁 Из файла: <code>{file_name}</code>\n"
                f"📊 Размер: {db_info.get('size_mb', 0):.2f} MB\n"
                f"📂 Таблиц: {len(db_info.get('tables', []))}\n"
                f"👥 Пользователей: {user_count}\n"
                f"💬 Сообщений: {message_count}\n"
                f"📝 Записей: {db_info.get('total_records', 0)}\n\n"
                f"✅ <b>Подключение к БД обновлено!</b>\n"
                f"👥 Теперь видно {user_count} пользователей"
            )
            
            await callback.message.answer(response_message, parse_mode="HTML")
            
            try:
                from app.config import ADMIN_IDS
                
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_document(
                            chat_id=admin_id,
                            document=FSInputFile(db_manager.db_path),
                            caption=(
                                f"📁 Восстановленная база данных\n"
                                f"⏰ {datetime.now().strftime('%H:%M:%S')}\n"
                                f"📊 {db_info.get('size_mb', 0):.2f} MB\n"
                                f"👥 {user_count} пользователей"
                            )
                        )
                        logger.info(f"📤 БД отправлена админу {admin_id}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки БД админу {admin_id}: {e}")
                        
            except Exception as e:
                logger.error(f"❌ Ошибка отправки БД админам: {e}")
            
        else:
            await callback.message.answer("❌ Ошибка восстановления базы данных")
        
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"🗑️ Удален загруженный файл: {file_name}")
            except Exception as e:
                logger.error(f"❌ Ошибка удаления файла {file_name}: {e}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка восстановления: {e}")
        await callback.message.answer(f"❌ Ошибка восстановления: {str(e)[:200]}")
    finally:
        await callback.answer()

@router.callback_query(F.data == "cancel_restore")
async def cancel_restore_database(callback: types.CallbackQuery):
    """Отмена восстановления"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return
    
    try:
        upload_dir = 'uploads'
        if os.path.exists(upload_dir):
            for filename in os.listdir(upload_dir):
                file_path = os.path.join(upload_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
    except Exception as e:
        logger.error(f"❌ Ошибка очистки uploads: {e}")
    
    await callback.message.answer("❌ Восстановление отменено")
    await callback.answer()

# ==================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ====================

@router.message(F.text == "👥 Пользователи")
async def admin_users(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        # Используем функции из database_utils
        total_users = get_users_count()
        
        today = datetime.now().date()
        result = safe_execute_query(
            "SELECT COUNT(*) FROM users WHERE DATE(created_at) = :today",
            {"today": today}
        )
        today_users = result.scalar() or 0
        
        users_message = (
            f"👥 <b>Управление пользователями</b>\n\n"
            f"📈 <b>Статистика:</b>\n"
            f"• Всего пользователей: <b>{total_users}</b>\n"
            f"• Новых сегодня: <b>{today_users}</b>\n\n"
            f"🔧 <b>Доступные действия:</b>\n"
            f"Выберите опцию ниже"
        )
        
        await message.answer(users_message, parse_mode="HTML", reply_markup=admin_users_menu())
        
    except Exception as e:
        logger.error(f"Ошибка в admin_users: {e}")
        await message.answer(f"❌ Ошибка получения статистики: {str(e)[:200]}")

@router.callback_query(F.data == "admin_users")
async def admin_users_callback(callback: types.CallbackQuery):
    """Callback для управления пользователями"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        total_users = get_users_count()
        
        today = datetime.now().date()
        result = safe_execute_query(
            "SELECT COUNT(*) FROM users WHERE DATE(created_at) = :today",
            {"today": today}
        )
        today_users = result.scalar() or 0
        
        response_message = (
            f"👥 <b>Управление пользователями</b>\n\n"
            f"📈 <b>Статистика:</b>\n"
            f"• Всего пользователей: <b>{total_users}</b>\n"
            f"• Новых сегодня: <b>{today_users}</b>\n\n"
            f"🔧 <b>Доступные действия:</b>\n"
            f"Выберите опцию ниже"
        )
        
        await callback.message.edit_text(response_message, parse_mode="HTML", reply_markup=admin_users_menu())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_users_callback: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.callback_query(F.data == "admin_users_list")
async def admin_users_list(callback: types.CallbackQuery):
    """Список пользователей с пагинацией"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        page = 1
        users_per_page = 5
        offset = (page - 1) * users_per_page
        
        result = safe_execute_query(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT :limit OFFSET :offset",
            {"limit": users_per_page, "offset": offset}
        )
        users = result.fetchall()
        
        total_users = get_users_count()
        
        total_pages = (total_users + users_per_page - 1) // users_per_page
        
        users_message = f"📋 <b>Список пользователей</b> (страница {page}/{total_pages})\n\n"
        
        for user in users:
            user_id = user[0]
            telegram_id = user[1]
            first_name = user[3]
            username = user[2] or "не указан"
            available_reveals = user[10] or 0
            created_at = user[6]
            
            if isinstance(created_at, str):
                created_date = created_at[:10]
            else:
                created_date = created_at.strftime('%d.%m.%Y')
            
            result = safe_execute_query(
                "SELECT COUNT(*) FROM anon_messages WHERE sender_id = :user_id OR receiver_id = :user_id",
                {"user_id": user_id}
            )
            messages_count = result.scalar() or 0
            
            users_message += (
                f"👤 <b>{first_name}</b>\n"
                f"🆔 ID: <code>{telegram_id}</code>\n"
                f"📨 Сообщений: {messages_count}\n"
                f"👁️ Раскрытий: {available_reveals}\n"
                f"📅 Регистрация: {created_date}\n"
                f"────────────────────\n"
            )
        
        if len(users_message) > 4096:
            users_message = users_message[:4000] + "\n... (сообщение обрезано)"
        
        await callback.message.edit_text(users_message, parse_mode="HTML", 
                                       reply_markup=admin_pagination_keyboard(page, total_pages, "users"))
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_users_list: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.callback_query(F.data.startswith("admin_page_users_"))
async def admin_users_page(callback: types.CallbackQuery):
    """Пагинация списка пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        page = int(callback.data.split("_")[3])
        users_per_page = 5
        offset = (page - 1) * users_per_page
        
        result = safe_execute_query(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT :limit OFFSET :offset",
            {"limit": users_per_page, "offset": offset}
        )
        users = result.fetchall()
        
        total_users = get_users_count()
        
        total_pages = (total_users + users_per_page - 1) // users_per_page
        
        users_message = f"📋 <b>Список пользователей</b> (страница {page}/{total_pages})\n\n"
        
        for user in users:
            user_id = user[0]
            telegram_id = user[1]
            first_name = user[3]
            username = user[2] or "не указан"
            available_reveals = user[10] or 0
            created_at = user[6]
            
            if isinstance(created_at, str):
                created_date = created_at[:10]
            else:
                created_date = created_at.strftime('%d.%m.%Y')
            
            result = safe_execute_query(
                "SELECT COUNT(*) FROM anon_messages WHERE sender_id = :user_id OR receiver_id = :user_id",
                {"user_id": user_id}
            )
            messages_count = result.scalar() or 0
            
            users_message += (
                f"👤 <b>{first_name}</b>\n"
                f"🆔 ID: <code>{telegram_id}</code>\n"
                f"📨 Сообщений: {messages_count}\n"
                f"👁️ Раскрытий: {available_reveals}\n"
                f"📅 Регистрация: {created_date}\n"
                f"────────────────────\n"
            )
        
        await callback.message.edit_text(users_message, parse_mode="HTML",
                                       reply_markup=admin_pagination_keyboard(page, total_pages, "users"))
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_users_page: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.callback_query(F.data == "admin_users_search")
async def admin_users_search_start(callback: types.CallbackQuery, state: FSMContext):
    """Начать поиск пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    await callback.message.answer(
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Введите ID пользователя, имя или username:\n"
        "Примеры:\n"
        "• <code>123456789</code> (Telegram ID)\n"
        "• <code>@username</code>\n"
        "• <code>Имя</code>",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_user_search)
    await callback.answer()

@router.message(AdminStates.waiting_user_search)
async def admin_users_search_result(message: types.Message, state: FSMContext):
    """Результат поиска пользователя"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    search_query = message.text.strip()
    
    try:
        users = []
        
        if search_query.isdigit():
            result = safe_execute_query(
                "SELECT * FROM users WHERE telegram_id = :telegram_id",
                {"telegram_id": int(search_query)}
            )
            user = result.fetchone()
            if user:
                users.append(user)
        
        elif search_query.startswith('@'):
            username = search_query[1:]
            result = safe_execute_query(
                "SELECT * FROM users WHERE username LIKE :username",
                {"username": f"%{username}%"}
            )
            users = result.fetchall()
        
        else:
            result = safe_execute_query(
                "SELECT * FROM users WHERE first_name LIKE :first_name",
                {"first_name": f"%{search_query}%"}
            )
            users = result.fetchall()
        
        if not users:
            await message.answer("❌ Пользователи не найдены")
            await state.clear()
            return
        
        if len(users) == 1:
            user = users[0]
            user_id = user[0]
            telegram_id = user[1]
            first_name = user[3]
            username = user[2] or "не указан"
            available_reveals = user[10] or 0
            anon_link_uid = user[5] or "нет"
            created_at = user[6]
            
            result = safe_execute_query(
                "SELECT COUNT(*) FROM anon_messages WHERE sender_id = :user_id",
                {"user_id": user_id}
            )
            sent_messages = result.scalar() or 0
            
            result = safe_execute_query(
                "SELECT COUNT(*) FROM anon_messages WHERE receiver_id = :user_id",
                {"user_id": user_id}
            )
            received_messages = result.scalar() or 0
            
            result = safe_execute_query(
                "SELECT COUNT(*) FROM payments WHERE user_id = :user_id AND status = 'completed'",
                {"user_id": user_id}
            )
            total_payments = result.scalar() or 0
            
            result = safe_execute_query(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE user_id = :user_id AND status = 'completed'",
                {"user_id": user_id}
            )
            total_spent = result.scalar() or 0
            
            if isinstance(created_at, str):
                created_date = created_at[:19].replace('T', ' ')
            else:
                created_date = created_at.strftime('%d.%m.%Y %H:%M')
            
            user_info = (
                f"👤 <b>Детальная информация</b>\n\n"
                f"🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>\n"
                f"👤 <b>Имя:</b> {first_name}\n"
                f"🏷️ <b>Username:</b> @{username}\n"
                f"🔗 <b>Ссылка:</b> {'✅ Активна' if anon_link_uid != 'нет' else '❌ Нет'}\n"
                f"👁️ <b>Раскрытий:</b> {available_reveals}\n"
                f"📅 <b>Регистрация:</b> {created_date}\n\n"
                
                f"📊 <b>Статистика:</b>\n"
                f"• 📤 Отправлено сообщений: <b>{sent_messages}</b>\n"
                f"• 📨 Получено сообщений: <b>{received_messages}</b>\n"
                f"• 💳 Совершено покупок: <b>{total_payments}</b>\n"
                f"• 💰 Потрачено: <b>{total_spent / 100:.2f}₽</b>\n"
            )
            
            await message.answer(user_info, parse_mode="HTML", 
                               reply_markup=admin_user_actions_menu(user_id))
        else:
            users_found = f"🔍 <b>Найдено пользователей:</b> {len(users)}\n\n"
            for i, user in enumerate(users[:10], 1):
                users_found += (
                    f"{i}. 👤 <b>{user[3]}</b>\n"
                    f"   🆔 ID: <code>{user[1]}</code>\n"
                    f"   🏷️ @{user[2] or 'нет'}\n"
                    f"   ────────────────────\n"
                )
            
            if len(users) > 10:
                users_found += f"\n⚠️ Показано первых 10 из {len(users)} результатов"
            
            await message.answer(users_found, parse_mode="HTML")
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_users_search_result: {e}")
        await message.answer(f"❌ Ошибка поиска: {str(e)}")
        await state.clear()

@router.callback_query(F.data.startswith("admin_user_set_reveals_"))
async def admin_user_set_reveals_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало установки раскрытий пользователю"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    user_id = int(callback.data.replace("admin_user_set_reveals_", ""))
    
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminStates.waiting_reveals_count)
    
    await callback.message.answer(
        "👁️ <b>Установка раскрытий пользователю</b>\n\n"
        "Введите количество раскрытий:",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(AdminStates.waiting_reveals_count)
async def admin_user_set_reveals_finish(message: types.Message, state: FSMContext):
    """Завершение установки раскрытий"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        reveals_count = int(message.text)
        if reveals_count < 0:
            await message.answer("❌ Количество раскрытий не может быть отрицательным")
            return
            
        user_data = await state.get_data()
        user_id = user_data.get('target_user_id')
        
        from app.database import get_session_local
        
        SessionLocal = get_session_local()
        db = SessionLocal()
        
        try:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                await message.answer("❌ Пользователь не найден")
                return

            if payment_service.set_reveals(db, user_id, reveals_count):
                await message.answer(
                    f"✅ <b>Раскрытия установлены!</b>\n\n"
                    f"👤 Пользователь: {user.first_name}\n"
                    f"👁️ Количество раскрытий: {reveals_count}",
                    parse_mode="HTML"
                )
            else:
                await message.answer("❌ Ошибка установки раскрытий")
        finally:
            db.close()
            
    except ValueError:
        await message.answer("❌ Введите корректное число")
    finally:
        await state.clear()

# ==================== УПРАВЛЕНИЕ ЦЕНАМИ ====================

@router.message(F.text == "💰 Цены")
async def admin_prices(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    prices_message = (
        "💰 <b>Управление ценами</b>\n\n"
        "🎯 <b>Доступные пакеты:</b>\n"
        "Управляйте ценами и скидками на раскрытия\n\n"
        "🔧 <b>Доступные действия:</b>\n"
        "• Изменение цен\n"
        "• Установка скидок\n"
        "• Включение/выключение пакетов\n"
    )
    
    await message.answer(prices_message, parse_mode="HTML", reply_markup=admin_prices_menu())

@router.callback_query(F.data == "admin_prices")
async def admin_prices_callback(callback: types.CallbackQuery):
    """Обработчик кнопки 'Управление ценами'"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    prices_message = (
        "💰 <b>Управление ценами</b>\n\n"
        "🎯 <b>Доступные пакеты:</b>\n"
        "Управляйте ценами и скидками на раскрытия\n\n"
        "🔧 <b>Доступные действия:</b>\n"
        "• Изменение цен\n"
        "• Установка скидок\n"
        "• Включение/выключение пакетов\n"
    )
    
    await callback.message.edit_text(prices_message, parse_mode="HTML", reply_markup=admin_prices_menu())
    await callback.answer()

@router.callback_query(F.data.startswith("admin_price_"))
async def admin_price_actions(callback: types.CallbackQuery):
    """Действия с ценами - ОБЩИЙ ОБРАБОТЧИК"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    data = callback.data
    
    if data.startswith("admin_price_"):
        package_id = data.replace("admin_price_", "")
        if package_id in price_service.get_all_packages():
            package = price_service.get_package_info(package_id)
            
            price_text = price_service.format_price(package["current_price"])
            base_price_text = price_service.format_price(package["base_price"])
            
            package_message = (
                f"🎯 <b>Управление пакетом</b>\n\n"
                f"📦 <b>Название:</b> {package['name']}\n"
                f"💰 <b>Текущая цена:</b> {price_text}\n"
                f"🏷️ <b>Базовая цена:</b> {base_price_text}\n"
                f"🔥 <b>Скидка:</b> {package['discount']}%\n"
                f"📊 <b>Статус:</b> {'🟢 Активен' if package['active'] else '🔴 Выключен'}\n\n"
                f"🔧 <b>Доступные действия:</b>"
            )
            
            await callback.message.edit_text(package_message, parse_mode="HTML", 
                                           reply_markup=admin_price_management_menu(package_id))
    
    await callback.answer()

@router.message(AdminStates.waiting_price_value)
async def admin_price_edit_finish(message: types.Message, state: FSMContext):
    """Завершение изменения цены"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        new_price = int(message.text)
        if new_price <= 0:
            await message.answer("❌ Цена должна быть положительным числом")
            return
            
        user_data = await state.get_data()
        package_id = user_data.get('editing_package')
        
        if price_service.update_price(package_id, new_price):
            package = price_service.get_package_info(package_id)
            await message.answer(
                f"✅ <b>Цена обновлена!</b>\n\n"
                f"📦 {package['name']}\n"
                f"💰 Новая цена: {price_service.format_price(package['current_price'])}",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Ошибка обновления цены")
            
    except ValueError:
        await message.answer("❌ Введите корректное число")
    finally:
        await state.clear()

@router.message(AdminStates.waiting_discount_value)
async def admin_price_discount_finish(message: types.Message, state: FSMContext):
    """Завершение установки скидки"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        discount = int(message.text)
        if discount < 0 or discount > 100:
            await message.answer("❌ Скидка должна быть от 0 до 100%")
            return
            
        user_data = await state.get_data()
        package_id = user_data.get('discount_package')
        
        if price_service.set_discount(package_id, discount):
            package = price_service.get_package_info(package_id)
            await message.answer(
                f"✅ <b>Скидка установлена!</b>\n\n"
                f"📦 {package['name']}\n"
                f"💰 Новая цена: {price_service.format_price(package['current_price'])}\n"
                f"🔥 Скидка: {discount}%",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Ошибка установки скидки")
            
    except ValueError:
        await message.answer("❌ Введите корректное число")
    finally:
        await state.clear()

# ==================== СТАТИСТИКА ====================

@router.message(F.text == "📊 Статистика")
async def admin_stats(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        total_users = get_users_count()
        
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        result = safe_execute_query(
            "SELECT COUNT(*) FROM users WHERE DATE(created_at) >= :week_ago",
            {"week_ago": week_ago}
        )
        week_users = result.scalar() or 0
        
        total_messages = get_messages_count()
        
        result = safe_execute_query(
            "SELECT COUNT(*) FROM anon_messages WHERE DATE(timestamp) >= :week_ago",
            {"week_ago": week_ago}
        )
        week_messages = result.scalar() or 0
        
        total_payments = get_payments_count()
        total_revenue = get_revenue()
        
        package_stats = {}
        for package_id in price_service.get_all_packages():
            result = safe_execute_query(
                "SELECT COUNT(*) FROM payments WHERE payment_type = :package_id AND status = 'completed'",
                {"package_id": package_id}
            )
            count = result.scalar() or 0
            package_stats[package_id] = count

        stats_message = (
            "📊 <b>Детальная статистика</b>\n\n"
            "👥 <b>Пользователи:</b>\n"
            f"• Всего: <b>{total_users}</b>\n"
            f"• Новых за неделю: <b>{week_users}</b>\n\n"
            "📨 <b>Сообщения:</b>\n"
            f"• Всего: <b>{total_messages}</b>\n"
            f"• За неделю: <b>{week_messages}</b>\n\n"
            "💰 <b>Финансы:</b>\n"
            f"• Всего продаж: <b>{total_payments}</b>\n"
            f"• Общая выручка: <b>{total_revenue / 100:.2f}₽</b>\n\n"
            "🎯 <b>Продажи по пакетам:</b>\n"
        )
        
        for package_id, count in package_stats.items():
            package = price_service.get_package_info(package_id)
            stats_message += f"• {package['name']}: <b>{count}</b>\n"
        
        await message.answer(stats_message, parse_mode="HTML", reply_markup=admin_stats_menu())
        
    except Exception as e:
        logger.error(f"Ошибка в admin_stats: {e}")
        await message.answer(f"❌ Ошибка получения статистики: {str(e)[:200]}")

@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: types.CallbackQuery):
    """Обработчик кнопки статистики"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        total_users = get_users_count()
        
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        result = safe_execute_query(
            "SELECT COUNT(*) FROM users WHERE DATE(created_at) >= :week_ago",
            {"week_ago": week_ago}
        )
        week_users = result.scalar() or 0
        
        total_messages = get_messages_count()
        
        result = safe_execute_query(
            "SELECT COUNT(*) FROM anon_messages WHERE DATE(timestamp) >= :week_ago",
            {"week_ago": week_ago}
        )
        week_messages = result.scalar() or 0
        
        total_payments = get_payments_count()
        total_revenue = get_revenue()
        
        package_stats = {}
        for package_id in price_service.get_all_packages():
            result = safe_execute_query(
                "SELECT COUNT(*) FROM payments WHERE payment_type = :package_id AND status = 'completed'",
                {"package_id": package_id}
            )
            count = result.scalar() or 0
            package_stats[package_id] = count

        stats_message = (
            "📊 <b>Детальная статистика</b>\n\n"
            "👥 <b>Пользователи:</b>\n"
            f"• Всего: <b>{total_users}</b>\n"
            f"• Новых за неделю: <b>{week_users}</b>\n\n"
            "📨 <b>Сообщения:</b>\n"
            f"• Всего: <b>{total_messages}</b>\n"
            f"• За неделю: <b>{week_messages}</b>\n\n"
            "💰 <b>Финансы:</b>\n"
            f"• Всего продаж: <b>{total_payments}</b>\n"
            f"• Общая выручка: <b>{total_revenue / 100:.2f}₽</b>\n\n"
            "🎯 <b>Продажи по пакетам:</b>\n"
        )
        
        for package_id, count in package_stats.items():
            package = price_service.get_package_info(package_id)
            stats_message += f"• {package['name']}: <b>{count}</b>\n"
        
        await callback.message.edit_text(stats_message, parse_mode="HTML", reply_markup=admin_stats_menu())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_stats_callback: {e}")
        await callback.answer("❌ Произошла ошибка")

# ==================== РАССЫЛКА ====================

@router.message(F.text == "📢 Рассылка")
async def admin_broadcast(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        total_users = get_users_count()
        
        result = safe_execute_query("SELECT COUNT(*) FROM users WHERE anon_link_uid IS NOT NULL")
        active_users = result.scalar() or 0
        
        broadcast_message = (
            "📢 <b>Система рассылок</b>\n\n"
            f"👥 <b>Статистика аудитории:</b>\n"
            f"• Всего пользователей: <b>{total_users}</b>\n"
            f"• Активных пользователей: <b>{active_users}</b>\n\n"
            "🔧 <b>Доступные рассылки:</b>\n"
            "• Всем пользователям\n"
            "• Конкретному пользователю\n"
        )
        
        await message.answer(broadcast_message, parse_mode="HTML", reply_markup=admin_broadcast_menu())
        
    except Exception as e:
        logger.error(f"Ошибка в admin_broadcast: {e}")
        await message.answer(f"❌ Ошибка получения статистики: {str(e)[:200]}")

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: types.CallbackQuery):
    """Обработчик кнопки рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        total_users = get_users_count()
        
        result = safe_execute_query("SELECT COUNT(*) FROM users WHERE anon_link_uid IS NOT NULL")
        active_users = result.scalar() or 0
        
        broadcast_message = (
            "📢 <b>Система рассылок</b>\n\n"
            f"👥 <b>Статистика аудитории:</b>\n"
            f"• Всего пользователей: <b>{total_users}</b>\n"
            f"• Активных пользователей: <b>{active_users}</b>\n\n"
            "🔧 <b>Доступные рассылки:</b>\n"
            "• Всем пользователям\n"
            "• Конкретному пользователю\n"
        )
        
        await callback.message.edit_text(broadcast_message, parse_mode="HTML", reply_markup=admin_broadcast_menu())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_broadcast_callback: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.callback_query(F.data == "admin_broadcast_all")
async def admin_broadcast_all_start(callback: types.CallbackQuery, state: FSMContext):
    """Начать рассылку всем пользователям"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    await callback.message.answer(
        "📢 <b>Рассылка всем пользователям</b>\n\n"
        "Введите сообщение для рассылки:\n\n"
        "💡 <b>Подсказки:</b>\n"
        "• Используйте HTML разметку для форматирования\n"
        "• Можно добавлять эмодзи 🎉\n"
        "• Будьте вежливы с пользователями",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_broadcast_message)
    await callback.answer()

@router.message(AdminStates.waiting_broadcast_message)
async def admin_broadcast_all_send(message: types.Message, state: FSMContext):
    """Отправить рассылку всем пользователям"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    from aiogram import Bot
    from app.config import BOT_TOKEN
    
    bot = Bot(token=BOT_TOKEN)
    broadcast_service.set_bot(bot)
    
    await message.answer("🔄 <b>Начинаю рассылку...</b>", parse_mode="HTML")
    
    await broadcast_service.broadcast_to_all(
        message.text,
        message.from_user.id
    )
    
    await state.clear()

@router.callback_query(F.data == "admin_broadcast_user")
async def admin_broadcast_user_start(callback: types.CallbackQuery, state: FSMContext):
    """Начать рассылку конкретному пользователю"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    await callback.message.answer(
        "👤 <b>Рассылка конкретному пользователю</b>\n\n"
        "Введите Telegram ID пользователя:",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_user_message)
    await callback.answer()

@router.message(AdminStates.waiting_user_message)
async def admin_broadcast_user_send(message: types.Message, state: FSMContext):
    """Отправить сообщение конкретному пользователю"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        telegram_id = int(message.text)
        
        await state.update_data(target_user_id=telegram_id)
        await state.set_state(AdminStates.waiting_broadcast_message)
        
        await message.answer(
            f"👤 <b>Рассылка пользователю</b>\n"
            f"🆔 ID: <code>{telegram_id}</code>\n\n"
            f"Введите сообщение для отправки:",
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.answer("❌ Неверный формат ID пользователя")

# ==================== НАСТРОЙКИ ====================

@router.message(F.text == "⚙️ Настройки")
async def admin_settings(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    settings_message = (
        "⚙️ <b>Настройки системы</b>\n\n"
        "🔧 <b>Основные настройки:</b>\n"
        "• Резервное копирование\n"
        "• Очистка базы данных\n"
        "• Логирование\n"
        "• Мониторинг\n\n"
        "📊 <b>Статус системы:</b>\n"
        "• База данных: ✅ Работает\n"
        "• Платежная система: ⚠️ Ручной режим\n"
        "• Рассылки: ✅ Доступны\n"
        "• Логи: ✅ Включены\n\n"
        "💡 Для тонкой настройки используйте команды:\n"
        "<code>/backup</code> - резервная копия\n"
        "<code>/db_status</code> - статус БД\n"
        "<code>/cleanup_old_data</code> - очистка"
    )
    
    await message.answer(settings_message, parse_mode="HTML", reply_markup=admin_settings_menu())

# ==================== ОБНОВЛЕНИЕ ====================

@router.message(F.text == "🔄 Обновить")
async def admin_refresh(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    await admin_panel(message)
    await message.answer("✅ <b>Данные обновлены!</b>", parse_mode="HTML")

# ==================== ВЫХОД ИЗ АДМИНКИ ====================

@router.message(F.text == "🚪 Выйти из админки")
async def exit_admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    await message.answer(
        "🚪 <b>Выход из админ-панели</b>\n\n"
        "Вы уверены, что хотите выйти из админ-панели?",
        parse_mode="HTML",
        reply_markup=exit_admin_keyboard()
    )

@router.callback_query(F.data == "exit_admin")
async def exit_admin_callback(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    await callback.message.answer(
        "🚪 <b>Выход из админ-панели</b>\n\n"
        "Вы уверены, что хотите выйти из админ-панели?",
        parse_mode="HTML",
        reply_markup=exit_admin_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "confirm_exit_admin")
async def confirm_exit_admin(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    await callback.message.answer(
        "✅ <b>Вы вышли из админ-панели</b>\n\n"
        "Теперь вы в обычном режиме пользователя.",
        parse_mode="HTML",
        reply_markup=main_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "admin_cancel_exit_admin")
async def admin_cancel_exit(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    await admin_panel(callback.message)
    await callback.answer("✅ Выход отменен")

@router.callback_query(F.data == "admin_main")
async def admin_back_to_main(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    await admin_panel(callback.message)
    await callback.answer()

# ==================== АДМИНСКИЕ КОМАНДЫ ====================

@router.message(Command("backup_now"), admin_filter)
async def backup_now_command(message: types.Message):
    """Немедленное создание backup"""
    await message.answer("🔄 Создаю резервную копию...")
    
    try:
        from app.backup_service import backup_service
        
        backup_path = backup_service.create_backup()
        
        if backup_path:
            backup_name = os.path.basename(backup_path)
            file_size = os.path.getsize(backup_path)
            file_size_mb = file_size / (1024 * 1024)
            
            await message.answer(
                f"✅ <b>Backup создан!</b>\n\n"
                f"📁 Файл: <code>{backup_name}</code>\n"
                f"📦 Размер: {file_size_mb:.2f} MB\n"
                f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"📤 Файл автоматически отправлен в Telegram всем админам.",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Ошибка создания backup")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("payment_status"), admin_filter)
async def payment_status_command(message: types.Message):
    """Статус платежной системы"""
    try:
        total_payments = get_payments_count()
        
        result = safe_execute_query("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
        pending_payments = result.scalar() or 0
        
        total_revenue = get_revenue()
        
        status_message = (
            "🔄 <b>Статус платежной системы</b>\n\n"
            "❌ <b>Автоматические платежи отключены</b>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"• 💰 Всего продаж: <b>{total_payments}</b>\n"
            f"• ⏳ Ожидающих платежей: <b>{pending_payments}</b>\n"
            f"• 🏦 Общая выручка: <b>{total_revenue / 100:.2f}₽</b>\n\n"
            "💡 <b>Рекомендации:</b>\n"
            "Для продажи раскрытий используйте команду:\n"
            "<code>/set_reveals ID_пользователя количество</code>"
        )
        
        await message.answer(status_message, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка в payment_status_command: {e}")
        await message.answer(f"❌ Ошибка получения статистики: {str(e)[:200]}")

@router.message(Command("user_info"), admin_filter)
async def user_info_command(message: types.Message):
    """Информация о пользователе"""
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer(
                "❌ Использование: /user_info ID_пользователя\n\n"
                "Пример: /user_info 123456789"
            )
            return

        telegram_id = int(args[1])
        
        result = safe_execute_query(
            "SELECT * FROM users WHERE telegram_id = :telegram_id",
            {"telegram_id": telegram_id}
        )
        user = result.fetchone()
        
        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        user_id = user[0]
        telegram_id = user[1]
        first_name = user[3]
        username = user[2] or "не указан"
        available_reveals = user[10] or 0
        anon_link_uid = user[5] or "нет"
        created_at = user[6]
        
        result = safe_execute_query(
            "SELECT COUNT(*) FROM anon_messages WHERE sender_id = :user_id",
            {"user_id": user_id}
        )
        sent_messages = result.scalar() or 0
        
        result = safe_execute_query(
            "SELECT COUNT(*) FROM anon_messages WHERE receiver_id = :user_id",
            {"user_id": user_id}
        )
        received_messages = result.scalar() or 0
        
        result = safe_execute_query(
            "SELECT COUNT(*) FROM payments WHERE user_id = :user_id AND status = 'completed'",
            {"user_id": user_id}
        )
        total_payments = result.scalar() or 0
        
        result = safe_execute_query(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE user_id = :user_id AND status = 'completed'",
            {"user_id": user_id}
        )
        total_spent = result.scalar() or 0
        
        if isinstance(created_at, str):
            created_date = created_at[:19].replace('T', ' ')
        else:
            created_date = created_at.strftime('%d.%m.%Y %H:%M')
        
        user_info = (
            f"👤 <b>Информация о пользователе</b>\n\n"
            f"🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>\n"
            f"👤 <b>Имя:</b> {first_name}\n"
            f"🏷️ <b>Username:</b> @{username}\n"
            f"🔗 <b>Ссылка:</b> {'✅ Активна' if anon_link_uid != 'нет' else '❌ Нет'}\n"
            f"👁️ <b>Раскрытий:</b> {available_reveals}\n"
            f"📅 <b>Регистрация:</b> {created_date}\n\n"
            
            f"📊 <b>Статистика:</b>\n"
            f"• 📤 Отправлено сообщений: <b>{sent_messages}</b>\n"
            f"• 📨 Получено сообщений: <b>{received_messages}</b>\n"
            f"• 💳 Совершено покупок: <b>{total_payments}</b>\n"
            f"• 💰 Потрачено: <b>{total_spent / 100:.2f}₽</b>\n"
        )
        
        await message.answer(user_info, parse_mode="HTML")

    except (IndexError, ValueError):
        await message.answer("❌ Использование: /user_info ID_пользователя")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("set_reveals"), admin_filter)
async def set_reveals_command(message: types.Message):
    """Установить количество раскрытий пользователю"""
    try:
        args = message.text.split()
        if len(args) < 3:
            await message.answer(
                "❌ Использование: /set_reveals ID_пользователя количество\n\n"
                "Пример: /set_reveals 123456789 10"
            )
            return

        telegram_id = int(args[1])
        new_count = int(args[2])
        
        from app.database import get_session_local
        
        SessionLocal = get_session_local()
        db = SessionLocal()
        
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                await message.answer("❌ Пользователь не найден")
                return

            if payment_service.set_reveals(db, user.id, new_count):
                await message.answer(
                    f"✅ <b>Раскрытия установлены!</b>\n\n"
                    f"👤 Пользователь: {user.first_name}\n"
                    f"👁️ Количество раскрытий: {new_count}",
                    parse_mode="HTML"
                )
            else:
                await message.answer("❌ Ошибка установки раскрытий")
        finally:
            db.close()

    except (IndexError, ValueError):
        await message.answer("❌ Использование: /set_reveals ID_пользователя количество")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("db_status"), admin_filter)
async def db_status_command(message: types.Message):
    """Статус базы данных"""
    try:
        from app.backup_service import backup_service
        size_mb = backup_service.get_db_size()
        stats = backup_service.get_db_stats()
        
        status_message = (
            "📊 <b>Статус базы данных</b>\n\n"
            f"💾 Размер: <b>{size_mb:.2f} MB</b>\n"
            f"👥 Пользователей: <b>{stats.get('users', 'N/A')}</b>\n"
            f"📨 Сообщений: <b>{stats.get('messages', 'N/A')}</b>\n"
            f"💰 Платежей: <b>{stats.get('payments', 'N/A')}</b>\n"
            f"⏳ Ожидающих платежей: <b>{stats.get('pending_payments', 'N/A')}</b>\n\n"
        )
        
        if size_mb > backup_service.critical_size_mb:
            status_message += "🚨 <b>КРИТИЧЕСКИЙ РАЗМЕР!</b>"
        elif size_mb > backup_service.max_size_mb:
            status_message += "⚠️ <b>Большой размер</b>"
        else:
            status_message += "✅ <b>Размер в норме</b>"
        
        await message.answer(status_message, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка получения статуса БД: {e}")

@router.message(Command("cleanup_old_data"), admin_filter)
async def cleanup_old_data_command(message: types.Message):
    """Очистка старых данных"""
    await message.answer("🔄 Очищаю старые данные...")
    
    try:
        from app.database_cleaner import db_cleaner
        deleted_messages, deleted_payments = await db_cleaner.cleanup_old_data()
        
        from app.backup_service import backup_service
        new_size = backup_service.get_db_size()
        
        await message.answer(
            "🧹 <b>Очистка завершена</b>\n\n"
            f"📨 Удалено сообщений: <b>{deleted_messages}</b>\n"
            f"💰 Удалено платежей: <b>{deleted_payments}</b>\n"
            f"💾 Новый размер БД: <b>{new_size:.2f} MB</b>",
            parse_mode="HTML"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка очистки данных: {e}")

@router.message(Command("upload_db"), admin_filter)
async def upload_db_command(message: types.Message):
    """Инструкция по загрузке базы данных"""
    await message.answer(
        "📁 <b>Загрузка базы данных</b>\n\n"
        "Для загрузки новой базы данных:\n"
        "1. Отправьте мне файл <code>.db</code>\n"
        "2. Подтвердите восстановление\n"
        "3. Подключение к БД автоматически перезагрузится\n\n"
        "⚠️ <b>Внимание:</b>\n"
        "• Текущая БД будет заменена\n"
        "• Создается резервная копия\n"
        "• Максимальный размер файла: 100MB\n"
        "• Файл должен быть SQLite базой данных\n\n"
        "<b>Быстрые команды:</b>\n"
        "<code>/backup_now</code> - создать backup\n"
        "<code>/backups</code> - список бэкапов\n"
        "<code>/upload_db</code> - загрузить БД\n"
        "<code>/db_status</code> - статус БД\n"
        "<code>/reload_db</code> - перезагрузить БД",
        parse_mode="HTML"
    )

@router.message(Command("stats"), admin_filter)
async def stats_command(message: types.Message):
    """Быстрая статистика"""
    try:
        total_users = get_users_count()
        total_messages = get_messages_count()
        total_payments = get_payments_count()
        total_revenue = get_revenue()
        
        stats_message = (
            "📊 <b>Быстрая статистика</b>\n\n"
            f"👥 Пользователей: <b>{total_users}</b>\n"
            f"📨 Сообщений: <b>{total_messages}</b>\n"
            f"💰 Продаж: <b>{total_payments}</b>\n"
            f"🏦 Выручка: <b>{total_revenue / 100:.2f}₽</b>"
        )
        
        await message.answer(stats_message, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка получения статистики: {e}")


@router.message(Command("check_backups"), admin_filter)
async def check_backups_command(message: Message):
    """Проверить все бэкапы на наличие данных"""
    try:
        from app.database_manager import db_manager
        
        backups = db_manager.list_backups()
        
        if not backups:
            await message.answer("📭 Бэкапы не найдены")
            return
        
        response = "🔍 <b>Проверка бэкапов:</b>\n\n"
        
        for backup in backups[-15:]:  # Последние 15 бэкапов
            try:
                import sqlite3
                conn = sqlite3.connect(backup["path"])
                cursor = conn.cursor()
                
                # Проверяем таблицы
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                tables = [row[0] for row in cursor.fetchall()]
                
                # Проверяем пользователей
                user_count = 0
                if 'users' in tables:
                    cursor.execute("SELECT COUNT(*) FROM users")
                    user_count = cursor.fetchone()[0]
                
                # Проверяем сообщения
                msg_count = 0
                if 'anon_messages' in tables:
                    cursor.execute("SELECT COUNT(*) FROM anon_messages")
                    msg_count = cursor.fetchone()[0]
                
                conn.close()
                
                # Проверяем размер
                backup_size_kb = backup["size"] / 1024
                
                # Определяем статус
                if user_count > 0 and backup_size_kb > 10:  # Больше 10KB
                    status = "✅"
                elif backup_size_kb < 10:  # Меньше 10KB - точно пустой
                    status = "❌ ПУСТОЙ"
                else:
                    status = "⚠️ СТРАННЫЙ"
                
                created_time = backup["created"].strftime("%d.%m %H:%M")
                
                response += (
                    f"📁 <code>{backup['name']}</code>\n"
                    f"   📅 {created_time} | 📊 {backup['size_mb']:.1f} MB\n"
                    f"   👥 {user_count} пользователей | ✉️ {msg_count} сообщений\n"
                    f"   📊 {len(tables)} таблиц | {status}\n\n"
                )
                
            except Exception as e:
                response += f"❌ {backup['name']}: ОШИБКА ({str(e)[:50]})\n\n"
        
        # Получаем информацию о текущей БД
        current_info = db_manager.get_db_info()
        response += (
            f"📊 <b>Текущая БД:</b>\n"
            f"Файл: <code>{os.path.basename(db_manager.db_path)}</code>\n"
            f"Размер: {current_info.get('size_mb', 0):.1f} MB\n"
            f"Пользователей: {current_info.get('table_stats', {}).get('users', 'N/A')}\n"
            f"Сообщений: {current_info.get('table_stats', {}).get('anon_messages', 'N/A')}\n\n"
            f"💡 <b>Что делать если бэкапы пустые:</b>\n"
            f"1. Используйте команду /full_backup\n"
            f"2. Остановите бота перед бэкапом\n"
            f"3. Проверьте командами /check_backups"
        )
        
        await message.answer(response, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки бэкапов: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")

@router.message(Command("full_backup"), admin_filter)
async def full_backup_command(message: Message):
    """Создать полный бэкап с данными (исправленный метод)"""
    try:
        await message.answer("💾 <b>Создаю ПОЛНЫЙ бэкап с данными...</b>\n\n"
                           "⚠️ <b>Внимание:</b> Бот будет приостановлен на время создания бэкапа", 
                           parse_mode="HTML")
        
        import sqlite3
        import datetime
        
        # Создаем уникальное имя
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"FULL_backup_{timestamp}.db"
        backup_path = os.path.join('backups', backup_name)
        
        # Показываем информацию о текущей БД
        current_info = db_manager.get_db_info()
        await message.answer(
            f"📊 <b>Информация о текущей БД:</b>\n"
            f"Файл: <code>{os.path.basename(db_manager.db_path)}</code>\n"
            f"Размер: {current_info.get('size_mb', 0):.1f} MB\n"
            f"Таблиц: {len(current_info.get('tables', []))}\n"
            f"Записей: {current_info.get('total_records', 0)}",
            parse_mode="HTML"
        )
        
        # Используем правильный метод копирования
        source_conn = None
        backup_conn = None
        
        try:
            # Подключаемся к исходной БД
            source_conn = sqlite3.connect(db_manager.db_path)
            
            # Создаем новую БД для бэкапа
            backup_conn = sqlite3.connect(backup_path)
            
            # Копируем ВСЮ базу данных (структура + данные)
            source_conn.backup(backup_conn)
            
            logger.info(f"✅ Бэкап создан через backup API: {backup_name}")
            
        except Exception as backup_api_error:
            await message.answer(f"⚠️ Backup API не сработал: {backup_api_error}\n"
                               "Пробую альтернативный метод...")
            
            # Закрываем соединения если открыты
            if source_conn:
                source_conn.close()
            if backup_conn:
                backup_conn.close()
            
            # Метод 2: Используем shutil с задержкой
            import time
            time.sleep(2)  # Даем время на закрытие всех соединений
            
            import shutil
            shutil.copy2(db_manager.db_path, backup_path)
            logger.info(f"✅ Бэкап создан через прямое копирование: {backup_name}")
        
        finally:
            # Закрываем соединения
            if source_conn:
                source_conn.close()
            if backup_conn:
                backup_conn.close()
        
        # Проверяем результат
        if os.path.exists(backup_path):
            backup_size = os.path.getsize(backup_path)
            
            # Подключаемся к бэкапу для проверки
            check_conn = sqlite3.connect(backup_path)
            cursor = check_conn.cursor()
            
            # Проверяем таблицы
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Проверяем пользователей
            user_count = 0
            if 'users' in tables:
                cursor.execute("SELECT COUNT(*) FROM users")
                user_count = cursor.fetchone()[0]
            
            # Проверяем сообщения
            msg_count = 0
            if 'anon_messages' in tables:
                cursor.execute("SELECT COUNT(*) FROM anon_messages")
                msg_count = cursor.fetchone()[0]
            
            check_conn.close()
            
            backup_size_kb = backup_size / 1024
            backup_size_mb = backup_size / (1024 * 1024)
            
            await message.answer(
                f"✅ <b>ПОЛНЫЙ бэкап создан!</b>\n\n"
                f"📁 Файл: <code>{backup_name}</code>\n"
                f"👥 Пользователей: <b>{user_count}</b>\n"
                f"✉️ Сообщений: <b>{msg_count}</b>\n"
                f"📊 Таблиц: <b>{len(tables)}</b>\n"
                f"📦 Размер: <b>{backup_size_mb:.1f} MB</b>\n"
                f"⏰ Время: {datetime.datetime.now().strftime('%H:%M:%S')}",
                parse_mode="HTML"
            )
            
            # Отправляем файл если он не слишком большой
            if backup_size_mb < 50:  # Telegram лимит ~50MB
                try:
                    await message.answer_document(
                        FSInputFile(backup_path),
                        caption=f"📁 Полный бэкап с данными\n👥 {user_count} пользователей"
                    )
                except Exception as e:
                    await message.answer(f"⚠️ Не удалось отправить файл (слишком большой?): {e}")
            else:
                await message.answer("⚠️ Файл слишком большой для отправки в Telegram")
            
            # Добавляем этот бэкап в менеджер
            if user_count > 0:
                logger.info(f"✅ Полный бэкап создан с {user_count} пользователями")
            else:
                await message.answer("🚨 <b>ВНИМАНИЕ:</b> В бэкапе 0 пользователей! Скорее всего проблема с созданием бэкапов.")
                
        else:
            await message.answer("❌ Файл бэкапа не был создан")
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания полного бэкапа: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")



@router.message(F.text.startswith("/check_backup_"), admin_filter)
async def check_specific_backup_command(message: Message):
    """Проверить конкретный бэкап по номеру"""
    try:
        from app.database_manager import db_manager
        
        cmd_parts = message.text.split("_")
        if len(cmd_parts) != 3:
            await message.answer("❌ Неверный формат команды")
            return
        
        try:
            backup_index = int(cmd_parts[2])
        except ValueError:
            await message.answer("❌ Неверный номер бэкапа")
            return
        
        backups = db_manager.list_backups()
        if not backups:
            await message.answer("📭 Бэкапы не найдены")
            return
        
        if not 1 <= backup_index <= len(backups):
            await message.answer(f"❌ Неверный номер бэкапа. Доступно: 1-{len(backups)}")
            return
        
        selected_backup = backups[backup_index - 1]
        
        try:
            import sqlite3
            conn = sqlite3.connect(selected_backup["path"])
            cursor = conn.cursor()
            
            # Получаем все таблицы
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Собираем статистику по всем таблицам
            table_stats = {}
            total_records = 0
            
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    table_stats[table] = count
                    total_records += count
                except:
                    table_stats[table] = 0
            
            conn.close()
            
            created_time = selected_backup["created"].strftime("%d.%m.%Y %H:%M:%S")
            modified_time = selected_backup["modified"].strftime("%d.%m.%Y %H:%M:%S")
            
            response = (
                f"🔍 <b>Детальная проверка бэкапа:</b>\n\n"
                f"📁 Файл: <code>{selected_backup['name']}</code>\n"
                f"📊 Размер: {selected_backup['size_mb']:.2f} MB\n"
                f"📅 Создан: {created_time}\n"
                f"🔄 Изменен: {modified_time}\n"
                f"📊 Таблиц: {len(tables)}\n"
                f"📝 Всего записей: {total_records}\n\n"
                f"📋 <b>Таблицы и записи:</b>\n"
            )
            
            # Показываем основные таблицы
            main_tables = ['users', 'anon_messages', 'payments']
            for table in main_tables:
                if table in table_stats:
                    response += f"• {table}: <b>{table_stats[table]}</b> записей\n"
            
            # Показываем остальные таблицы
            other_tables = [t for t in tables if t not in main_tables and not t.startswith('sqlite_')]
            if other_tables:
                response += f"\n📁 <b>Другие таблицы:</b>\n"
                for table in other_tables[:10]:  # Первые 10
                    response += f"• {table}: {table_stats.get(table, 0)} записей\n"
                if len(other_tables) > 10:
                    response += f"• ... и еще {len(other_tables) - 10} таблиц\n"
            
            # Сравниваем с текущей БД
            current_info = db_manager.get_db_info()
            current_records = current_info.get('total_records', 0)
            
            if current_records > 0 and total_records > 0:
                completeness = (total_records / current_records) * 100
                if completeness > 90:
                    status = "✅ ХОРОШИЙ"
                elif completeness > 50:
                    status = "⚠️ ЧАСТИЧНЫЙ"
                else:
                    status = "❌ ПЛОХОЙ"
                
                response += f"\n📊 <b>Сравнение с текущей БД:</b>\n"
                response += f"Записей в бэкапе: {total_records}\n"
                response += f"Записей в текущей: {current_records}\n"
                response += f"Полнота: {completeness:.1f}% - {status}\n"
            
            # Кнопка для восстановления
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔄 Восстановить из этого бэкапа", 
                            callback_data=f"restore_from_check_{backup_index}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🗑️ Удалить этот бэкап", 
                            callback_data=f"delete_backup_{backup_index}"
                        )
                    ]
                ]
            )
            
            await message.answer(response, parse_mode="HTML", reply_markup=keyboard)
            
        except Exception as e:
            await message.answer(f"❌ Ошибка проверки бэкапа: {str(e)[:200]}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка команды check_backup: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")

@router.callback_query(F.data.startswith("restore_from_check_"))
async def restore_from_check_callback(callback: CallbackQuery):
    """Восстановить из бэкапа проверенного командой /check_backup"""
    try:
        from app.database_manager import db_manager
        
        backup_index = int(callback.data.replace("restore_from_check_", ""))
        
        backups = db_manager.list_backups()
        if not 1 <= backup_index <= len(backups):
            await callback.answer("❌ Неверный номер бэкапа")
            return
        
        selected_backup = backups[backup_index - 1]
        
        await callback.message.answer(f"🔄 <b>Восстанавливаю из бэкапа:</b>\n"
                                    f"<code>{selected_backup['name']}</code>", 
                                    parse_mode="HTML")
        
        # Создаем бэкап текущей БД
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        current_backup = db_manager.create_backup(f"before_restore_{timestamp}.db", send_to_admins=False)
        
        if current_backup:
            await callback.message.answer(f"💾 <b>Текущая БД сохранена:</b>\n"
                                        f"<code>{os.path.basename(current_backup)}</code>", 
                                        parse_mode="HTML")
        
        # Восстанавливаем
        success = db_manager.restore_from_backup(selected_backup["path"])
        
        if success:
            await callback.message.answer("✅ <b>БД восстановлена!</b>\n"
                                        "🔄 Перезагружаю подключение...", 
                                        parse_mode="HTML")
            
            # Перезагружаем подключение
            force_reconnect()
            await asyncio.sleep(2)
            
            # Проверяем результат
            db_info = db_manager.get_db_info()
            user_count = db_info.get('table_stats', {}).get('users', 0)
            
            await callback.message.answer(
                f"✅ <b>Восстановление завершено!</b>\n\n"
                f"📊 <b>Результат:</b>\n"
                f"👥 Пользователей: <b>{user_count}</b>\n"
                f"📦 Размер: {db_info.get('size_mb', 0):.1f} MB\n"
                f"📊 Таблиц: {len(db_info.get('tables', []))}\n\n"
                f"💡 <b>Используйте команды:</b>\n"
                f"/stats - проверить статистику\n"
                f"/admin - открыть админ-панель",
                parse_mode="HTML"
            )
        else:
            await callback.message.answer("❌ <b>Ошибка восстановления!</b>\n\n"
                                        "Попробуйте другой бэкап или создайте новый с помощью /full_backup",
                                        parse_mode="HTML")
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка восстановления из проверенного бэкапа: {e}")
        await callback.message.answer(f"❌ Ошибка: {str(e)[:200]}")
        await callback.answer()



@router.message(Command("fix_backups"), admin_filter)
async def fix_backups_command(message: Message):
    """Исправить все пустые бэкапы, создав новые правильные"""
    try:
        await message.answer("🔧 <b>Начинаю исправление бэкапов...</b>", parse_mode="HTML")
        
        from app.database_manager import db_manager
        
        # Сначала создаем правильный полный бэкап
        await message.answer("💾 <b>Создаю правильный полный бэкап...</b>", parse_mode="HTML")
        
        import sqlite3
        import datetime
        import shutil
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fixed_backup_name = f"FIXED_backup_{timestamp}.db"
        fixed_backup_path = os.path.join('backups', fixed_backup_name)
        
        # Метод 1: Используем sqlite3 backup API
        try:
            source_conn = sqlite3.connect(db_manager.db_path)
            backup_conn = sqlite3.connect(fixed_backup_path)
            source_conn.backup(backup_conn)
            source_conn.close()
            backup_conn.close()
            method = "backup API"
        except Exception as e:
            # Метод 2: Используем прямое копирование с задержкой
            await message.answer(f"⚠️ Backup API не сработал, пробую прямое копирование...")
            time.sleep(3)  # Большая задержка
            shutil.copy2(db_manager.db_path, fixed_backup_path)
            method = "прямое копирование"
        
        # Проверяем созданный бэкап
        if os.path.exists(fixed_backup_path):
            # Проверяем данные в бэкапе
            check_conn = sqlite3.connect(fixed_backup_path)
            cursor = check_conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM anon_messages")
            msg_count = cursor.fetchone()[0]
            
            check_conn.close()
            
            backup_size = os.path.getsize(fixed_backup_path) / (1024 * 1024)
            
            await message.answer(
                f"✅ <b>Исправленный бэкап создан!</b>\n\n"
                f"📁 Файл: <code>{fixed_backup_name}</code>\n"
                f"🔧 Метод: {method}\n"
                f"👥 Пользователей: <b>{user_count}</b>\n"
                f"✉️ Сообщений: <b>{msg_count}</b>\n"
                f"📦 Размер: <b>{backup_size:.1f} MB</b>\n\n",
                parse_mode="HTML"
            )
            
            # Проверяем старые бэкапы
            backups = db_manager.list_backups()
            empty_count = 0
            
            for backup in backups:
                try:
                    conn = sqlite3.connect(backup["path"])
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM users")
                    old_user_count = cursor.fetchone()[0]
                    conn.close()
                    
                    if old_user_count == 0 and backup["size"] < 10240:  # Меньше 10KB
                        empty_count += 1
                except:
                    pass
            
            if empty_count > 0:
                await message.answer(
                    f"⚠️ <b>Обнаружено {empty_count} пустых бэкапов!</b>\n\n"
                    f"💡 <b>Рекомендации:</b>\n"
                    f"1. Удалите пустые бэкапы вручную\n"
                    f"2. Используйте только этот исправленный бэкап\n"
                    f"3. Для новых бэкапов используйте команду /full_backup\n\n"
                    f"📁 <b>Исправленный бэкап готов к использованию!</b>",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    f"✅ <b>Все бэкапы в порядке!</b>\n\n"
                    f"📁 Исправленный бэкап создан как резервная копия.",
                    parse_mode="HTML"
                )
            
            # Отправляем исправленный бэкап
            if backup_size < 20:  # Если меньше 20MB
                try:
                    await message.answer_document(
                        FSInputFile(fixed_backup_path),
                        caption=f"📁 ИСПРАВЛЕННЫЙ бэкап\n👥 {user_count} пользователей"
                    )
                except:
                    pass
        else:
            await message.answer("❌ <b>Не удалось создать исправленный бэкап!</b>\n\n"
                               "Попробуйте остановить бота и создать бэкап вручную.",
                               parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"❌ Ошибка исправления бэкапов: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")


@router.message(Command("emergency_fix_db"), admin_filter)
async def emergency_fix_db_command(message: Message):
    """ЭКСТРЕННОЕ исправление базы данных - создает таблицы если их нет"""
    try:
        await message.answer("🚨 <b>ЭКСТРЕННОЕ ИСПРАВЛЕНИЕ БАЗЫ ДАННЫХ!</b>\n"
                           "Создаю таблицы напрямую через SQLite...", 
                           parse_mode="HTML")
        
        import sqlite3
        import os
        
        # Удаляем старую БД если она повреждена
        db_path = 'data/bot.db'
        if os.path.exists(db_path):
            # Проверяем текущее состояние
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            current_tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            await message.answer(f"📊 <b>Текущее состояние БД:</b>\n"
                               f"Таблиц: {len(current_tables)}\n"
                               f"Список: {', '.join(current_tables) if current_tables else 'нет таблиц'}",
                               parse_mode="HTML")
        
        # Создаем таблицы
        await message.answer("🔄 <b>Создаю таблицы...</b>", parse_mode="HTML")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Таблица users
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT NOT NULL,
            last_name TEXT,
            anon_link_uid TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_banned BOOLEAN DEFAULT FALSE,
            ban_reason TEXT,
            available_reveals INTEGER DEFAULT 0,
            total_reveals_used INTEGER DEFAULT 0
        )
        ''')
        await message.answer("✅ Таблица 'users' создана")
        
        # Таблица anon_messages
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS anon_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            receiver_id INTEGER NOT NULL,
            message_text TEXT NOT NULL,
            message_type TEXT DEFAULT 'text',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_read BOOLEAN DEFAULT FALSE,
            read_at TIMESTAMP,
            is_revealed BOOLEAN DEFAULT FALSE,
            revealed_at TIMESTAMP,
            parent_message_id INTEGER,
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (receiver_id) REFERENCES users (id),
            FOREIGN KEY (parent_message_id) REFERENCES anon_messages (id)
        )
        ''')
        await message.answer("✅ Таблица 'anon_messages' создана")
        
        # Таблица payments
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            payment_id TEXT UNIQUE,
            payment_type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            currency TEXT DEFAULT 'RUB',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            metadata TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')
        await message.answer("✅ Таблица 'payments' создана")
        
        # Создаем индексы
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_anon_link ON users(anon_link_uid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_receiver ON anon_messages(receiver_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_sender ON anon_messages(sender_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON anon_messages(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)')
        await message.answer("✅ Индексы созданы")
        
        conn.commit()
        
        # Проверяем результат
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        new_tables = [row[0] for row in cursor.fetchall()]
        
        # Получаем статистику
        stats = []
        for table in new_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            stats.append(f"• {table}: {count} записей")
        
        conn.close()
        
        # Добавляем администратора
        from app.config import ADMIN_IDS
        if ADMIN_IDS:
            admin_id = ADMIN_IDS[0]
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute('''
                INSERT OR IGNORE INTO users (telegram_id, first_name, username, anon_link_uid)
                VALUES (?, ?, ?, ?)
                ''', (admin_id, 'Администратор', 'admin', f'admin_{admin_id}'))
                conn.commit()
                conn.close()
                await message.answer(f"✅ Администратор добавлен (ID: {admin_id})")
            except Exception as e:
                await message.answer(f"⚠️ Не удалось добавить администратора: {e}")
        
        # Перезагружаем подключение к БД
        force_reconnect()
        await asyncio.sleep(2)
        
        # Получаем финальную статистику
        from app.database import get_engine
        from sqlalchemy import text
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.scalar() or 0
        
        await message.answer(
            f"🎉 <b>БАЗА ДАННЫХ УСПЕШНО ИСПРАВЛЕНА!</b>\n\n"
            f"📊 <b>Структура:</b>\n"
            f"Таблиц: {len(new_tables)}\n"
            f"Список: {', '.join(new_tables)}\n\n"
            f"📈 <b>Статистика:</b>\n" + "\n".join(stats) + "\n\n"
            f"👥 <b>Пользователей в БД:</b> {user_count}\n\n"
            f"🔄 <b>Подключение к БД перезагружено!</b>",
            parse_mode="HTML"
        )
        
        # Создаем бэкап новой БД
        await message.answer("💾 Создаю бэкап исправленной БД...")
        await full_backup_command(message)
        
    except Exception as e:
        logger.error(f"❌ Ошибка экстренного исправления БД: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")

@router.message(Command("db_structure"), admin_filter)
async def db_structure_command(message: Message):
    """Показать структуру базы данных"""
    try:
        import sqlite3
        
        db_path = 'data/bot.db'
        
        if not os.path.exists(db_path):
            await message.answer("❌ Файл БД не найден")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Получаем все таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        
        response = "📊 <b>Структура базы данных:</b>\n\n"
        
        for table_info in tables:
            table_name = table_info[0]
            
            # Получаем структуру таблицы
            cursor.execute(f"PRAGMA table_info('{table_name}')")
            columns = cursor.fetchall()
            
            response += f"📋 <b>Таблица: {table_name}</b>\n"
            
            for col in columns:
                col_id, col_name, col_type, not_null, default_val, pk = col
                pk_mark = "🔑" if pk else ""
                response += f"  • {pk_mark} <code>{col_name}</code> ({col_type})"
                if default_val:
                    response += f" DEFAULT {default_val}"
                if not_null:
                    response += " NOT NULL"
                response += "\n"
            
            # Получаем количество записей
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                response += f"  📝 Записей: <b>{row_count}</b>\n\n"
            except:
                response += f"  📝 Записей: <b>0</b> (ошибка чтения)\n\n"
        
        conn.close()
        
        # Добавляем информацию о файле
        file_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
        file_size_mb = file_size / (1024 * 1024)
        
        response += f"📁 <b>Информация о файле:</b>\n"
        response += f"Путь: <code>{db_path}</code>\n"
        response += f"Размер: {file_size_mb:.2f} MB\n"
        response += f"Таблиц: {len(tables)}\n"
        
        # Проверяем обязательные таблицы
        required_tables = ['users', 'anon_messages', 'payments']
        found_tables = [t[0] for t in tables if t[0] in required_tables]
        
        if len(found_tables) < 3:
            response += f"\n🚨 <b>ПРОБЛЕМА:</b> Отсутствуют таблицы!\n"
            response += f"Найдено: {len(found_tables)} из 3\n"
            missing = [t for t in required_tables if t not in found_tables]
            response += f"Отсутствуют: {', '.join(missing)}\n"
            response += f"\n🔧 <b>Исправьте командой:</b>\n"
            response += f"<code>/emergency_fix_db</code>"
        
        if len(response) > 4096:
            await message.answer(response[:4000] + "\n... (сообщение обрезано)", parse_mode="HTML")
        else:
            await message.answer(response, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")

@router.message(Command("force_backup"), admin_filter)
async def force_backup_command(message: Message):
    """Создать бэкап БД с принудительным закрытием всех соединений"""
    try:
        await message.answer("🔄 <b>ПРИНУДИТЕЛЬНОЕ СОЗДАНИЕ БЭКАПА</b>\n"
                           "Закрываю все соединения с БД...", 
                           parse_mode="HTML")
        
        # Закрываем все соединения
        force_reconnect()
        await asyncio.sleep(3)  # Даем время на закрытие
        
        import sqlite3
        import datetime
        import shutil
        
        db_path = 'data/bot.db'
        
        if not os.path.exists(db_path):
            await message.answer("❌ Файл БД не найден")
            return
        
        # Создаем уникальное имя для бэкапа
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"FORCED_backup_{timestamp}.db"
        backup_path = os.path.join('backups', backup_name)
        
        await message.answer("💾 <b>Копирую файл БД...</b>", parse_mode="HTML")
        
        # Простое копирование файла (самый надежный метод)
        shutil.copy2(db_path, backup_path)
        
        # Проверяем бэкап
        if os.path.exists(backup_path):
            backup_size = os.path.getsize(backup_path)
            
            # Подключаемся к бэкапу для проверки
            conn = sqlite3.connect(backup_path)
            cursor = conn.cursor()
            
            # Проверяем таблицы
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Проверяем пользователей
            user_count = 0
            if 'users' in tables:
                cursor.execute("SELECT COUNT(*) FROM users")
                user_count = cursor.fetchone()[0]
            
            # Проверяем сообщения
            msg_count = 0
            if 'anon_messages' in tables:
                cursor.execute("SELECT COUNT(*) FROM anon_messages")
                msg_count = cursor.fetchone()[0]
            
            conn.close()
            
            backup_size_mb = backup_size / (1024 * 1024)
            
            await message.answer(
                f"✅ <b>БЭКАП УСПЕШНО СОЗДАН!</b>\n\n"
                f"📁 Файл: <code>{backup_name}</code>\n"
                f"👥 Пользователей: <b>{user_count}</b>\n"
                f"✉️ Сообщений: <b>{msg_count}</b>\n"
                f"📊 Таблиц: <b>{len(tables)}</b>\n"
                f"📦 Размер: <b>{backup_size_mb:.2f} MB</b>\n"
                f"⏰ Время: {datetime.datetime.now().strftime('%H:%M:%S')}",
                parse_mode="HTML"
            )
            
            # Отправляем файл если он не слишком большой
            if backup_size_mb < 20:
                try:
                    from aiogram.types import FSInputFile
                    await message.answer_document(
                        FSInputFile(backup_path),
                        caption=f"📁 ПРИНУДИТЕЛЬНЫЙ бэкап\n👥 {user_count} пользователей"
                    )
                except Exception as e:
                    await message.answer(f"⚠️ Не удалось отправить файл: {e}")
            else:
                await message.answer("⚠️ Файл слишком большой для отправки в Telegram")
            
            if user_count == 0:
                await message.answer("🚨 <b>ВНИМАНИЕ:</b> В бэкапе 0 пользователей!\n"
                                   "Возможно проблема с БД. Используйте команду:\n"
                                   "<code>/emergency_fix_db</code>", 
                                   parse_mode="HTML")
                
        else:
            await message.answer("❌ Не удалось создать бэкап")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")
























