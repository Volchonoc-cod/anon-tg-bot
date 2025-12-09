from aiogram import F, Router, types, Bot  
import os
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import asyncio
from aiogram.types import Message, CallbackQuery, FSInputFile
import json
from app.database_manager import db_manager  # Импортируем менеджер БД
from app.database import get_db
from app.models import User, AnonMessage, Payment
from app.config import ADMIN_IDS
from app.keyboards_admin import (
    admin_main_menu, admin_users_menu, admin_prices_menu,
    admin_stats_menu, admin_broadcast_menu, admin_user_actions_menu,
    admin_price_management_menu, admin_confirm_keyboard, admin_pagination_keyboard,
    exit_admin_keyboard
)
from app.keyboards import main_menu
from app.price_service import price_service
from app.broadcast_service import broadcast_service
from app.payment_service import payment_service
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

def is_admin(user_id: int):
    return user_id in ADMIN_IDS

# Фильтр для админов
def admin_filter(message: Message) -> bool:
    return message.from_user.id in ADMIN_IDS

# Состояния для FSM
class BackupStates(StatesGroup):
    waiting_backup_name = State()
    waiting_restore_confirmation = State()

@router.message(Command("backup"), admin_filter)
async def cmd_backup(message: Message):
    """Создать бэкап БД"""
    try:
        # Показываем что начали
        await message.answer("💾 Создание бэкапа...")
        
        # Создаем бэкап
        backup_path = db_manager.create_backup()
        
        if backup_path:
            backup_name = os.path.basename(backup_path)
            backup_size = os.path.getsize(backup_path) / (1024 * 1024)  # MB
            
            response = (
                f"✅ <b>Бэкап создан успешно!</b>\n\n"
                f"📁 Имя: <code>{backup_name}</code>\n"
                f"📊 Размер: {backup_size:.2f} MB\n"
                f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}"
            )
            
            # Пытаемся отправить файл
            try:
                await message.answer_document(
                    FSInputFile(backup_path),
                    caption=response,
                    parse_mode="HTML"
                )
            except:
                # Если не получилось отправить файл, отправляем только сообщение
                await message.answer(response, parse_mode="HTML")
        else:
            await message.answer("❌ Не удалось создать бэкап. Проверьте логи.")
            
    except Exception as e:
        error_msg = str(e)[:200]  # Ограничиваем длину сообщения
        await message.answer(f"❌ Ошибка при создании бэкапа: {error_msg}")

@router.message(Command("backups"), admin_filter)
async def cmd_backups(message: Message):
    """Показать список бэкапов"""
    try:
        backups = db_manager.list_backups()
        
        if not backups:
            await message.answer("📭 Бэкапы не найдены")
            return
        
        # Формируем сообщение
        response = "📂 <b>Список бэкапов:</b>\n\n"
        
        for i, backup in enumerate(reversed(backups[-10:]), 1):  # Последние 10
            created = backup["created"].strftime("%d.%m.%Y %H:%M")
            size_mb = backup["size_mb"]
            valid = "✅" if backup["is_valid"] else "❌"
            
            response += (
                f"{i}. <code>{backup['name']}</code>\n"
                f"   📅 {created} | 📊 {size_mb:.2f} MB | {valid}\n\n"
            )
        
        # Добавляем статистику
        db_info = db_manager.get_db_info()
        response += (
            f"📊 <b>Статистика БД:</b>\n"
            f"Размер: {db_info.get('size_mb', 0):.2f} MB\n"
            f"Таблиц: {len(db_info.get('tables', []))}\n"
            f"Всего бэкапов: {len(backups)}"
        )
        
        await message.answer(response, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении списка бэкапов: {str(e)}")

@router.message(Command("restore"), admin_filter)
async def cmd_restore(message: Message, state: FSMContext):
    """Восстановить БД из бэкапа"""
    try:
        backups = db_manager.list_backups()
        
        if not backups:
            await message.answer("📭 Бэкапы не найдены для восстановления")
            return
        
        # Показываем последние 5 бэкапов
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
        # Получаем номер бэкапа из команды
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
        
        # Выбираем бэкап (последние 5, reverse order)
        selected_backup = list(reversed(backups[-5:]))[backup_index - 1]
        
        # Восстанавливаем
        success = db_manager.restore_from_backup(selected_backup["path"])
        
        if success:
            # Получаем информацию о восстановленной БД
            db_info = db_manager.get_db_info()
            
            response = (
                f"✅ <b>БД успешно восстановлена!</b>\n\n"
                f"📁 Из: {selected_backup['name']}\n"
                f"📅 Дата бэкапа: {selected_backup['created'].strftime('%d.%m.%Y %H:%M')}\n"
                f"📊 Размер: {db_info.get('size_mb', 0):.2f} MB\n"
                f"📂 Таблиц: {len(db_info.get('tables', []))}\n\n"
                f"🔄 <b>Перезапустите бота для применения изменений!</b>"
            )
        else:
            response = "❌ Не удалось восстановить БД"
        
        await message.answer(response, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка восстановления: {str(e)}")

@router.message(Command("dbinfo"), admin_filter)
async def cmd_dbinfo(message: Message):
    """Информация о базе данных"""
    try:
        db_info = db_manager.get_db_info()
        metadata = db_manager.load_metadata()
        backups = db_manager.list_backups()
        
        response = "💾 <b>Информация о базе данных:</b>\n\n"
        
        if db_info["exists"]:
            response += (
                f"📁 Файл: {os.path.basename(db_manager.db_path)}\n"
                f"📊 Размер: {db_info.get('size_mb', 0):.2f} MB\n"
                f"📂 Таблиц: {len(db_info.get('tables', []))}\n"
                f"📅 Изменен: {db_info.get('last_modified', 'N/A')}\n\n"
            )
            
            # Статистика по таблицам
            if db_info.get("table_stats"):
                response += "📈 <b>Статистика таблиц:</b>\n"
                for table, count in db_info["table_stats"].items():
                    response += f"  {table}: {count} записей\n"
                response += "\n"
        
        # Информация о бэкапах
        response += f"📂 <b>Бэкапы:</b> {len(backups)} файлов\n"
        if backups:
            latest = backups[-1]
            response += (
                f"Последний: {latest['name']}\n"
                f"Создан: {latest['created'].strftime('%d.%m.%Y %H:%M')}\n"
                f"Размер: {latest['size_mb']:.2f} MB\n"
            )
        
        # Метаданные
        if metadata:
            response += f"\n📋 <b>Метаданные:</b>\n"
            response += f"Версия: {metadata.get('version', 'N/A')}\n"
            response += f"Последний бэкап: {metadata.get('last_backup', 'N/A')}"
        
        await message.answer(response, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@router.message(Command("cleanbackups"), admin_filter)
async def cmd_cleanbackups(message: Message):
    """Очистить старые бэкапы"""
    try:
        deleted = db_manager.cleanup_old_backups()
        
        if deleted > 0:
            response = f"🧹 Удалено старых бэкапов: {deleted}"
        else:
            response = "📭 Старых бэкапов не найдено"
        
        await message.answer(response)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка очистки бэкапов: {str(e)}")

@router.message(Command("exportdb"), admin_filter)
async def cmd_exportdb(message: Message):
    """Экспортировать БД в SQL"""
    try:
        success = db_manager.export_to_sql()
        
        if success:
            sql_file = 'data/database_export.sql'
            if os.path.exists(sql_file):
                await message.answer_document(
                    FSInputFile(sql_file),
                    caption="✅ БД экспортирована в SQL формат"
                )
            else:
                await message.answer("✅ БД экспортирована, но файл не найден")
        else:
            await message.answer("❌ Ошибка экспорта БД")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка экспорта: {str(e)}")

# ==================== ЗАГРУЗКА БАЗЫ ДАННЫХ ====================

@router.message(F.document, admin_filter)
async def handle_database_upload(message: types.Message, bot: Bot):
    """Обработка загрузки базы данных"""
    if not is_admin(message.from_user.id):
        return

    document = message.document
    
    # Проверяем что это файл базы данных
    if not document.file_name or not document.file_name.endswith('.db'):
        await message.answer("❌ Можно загружать только файлы баз данных (.db)")
        return
    
    # Лимит размера файла (100MB)
    MAX_SIZE = 100 * 1024 * 1024
    if document.file_size > MAX_SIZE:
        await message.answer(f"❌ Файл слишком большой. Максимальный размер: {MAX_SIZE // (1024*1024)}MB")
        return
    
    await message.answer("💾 Загружаю файл базы данных...")
    
    try:
        # Создаем директорию для загрузок
        upload_dir = 'uploads'
        os.makedirs(upload_dir, exist_ok=True)
        
        # Скачиваем файл
        file_path = os.path.join(upload_dir, document.file_name)
        
        file = await bot.get_file(document.file_id)
        await bot.download_file(file.file_path, file_path)
        
        # Проверяем валидность базы данных
        if not db_manager.validate_backup(file_path):
            os.remove(file_path)
            await message.answer("❌ Файл не является валидной базой данных SQLite")
            return
        
        # Получаем информацию о файле
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
        # Создаем бэкап текущей БД
        await callback.message.answer("💾 Создаю резервную копию текущей БД...")
        current_backup = db_manager.create_backup("before_upload_backup.db", send_to_admins=False)
        
        if current_backup:
            await callback.message.answer(f"✅ Текущая БД сохранена: {os.path.basename(current_backup)}")
        
        # Восстанавливаем из загруженного файла
        await callback.message.answer("🔄 Восстанавливаю базу данных...")
        
        success = db_manager.restore_from_backup(file_path)
        
        if success:
            # Получаем информацию о восстановленной БД
            db_info = db_manager.get_db_info()
            
            # Создаем бэкап восстановленной БД
            new_backup = db_manager.create_backup("after_restore_backup.db")
            
            await callback.message.answer(
                f"✅ <b>База данных успешно восстановлена!</b>\n\n"
                f"📁 Из файла: <code>{file_name}</code>\n"
                f"📊 Размер: {db_info.get('size_mb', 0):.2f} MB\n"
                f"📂 Таблиц: {len(db_info.get('tables', []))}\n"
                f"📝 Записей: {db_info.get('total_records', 0)}\n\n"
                f"🔄 <b>Перезапустите бота для применения изменений!</b>",
                parse_mode="HTML"
            )
            
            # Отправляем файл БД всем админам
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
                                f"📊 {db_info.get('size_mb', 0):.2f} MB"
                            )
                        )
                        logger.info(f"📤 БД отправлена админу {admin_id}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки БД админу {admin_id}: {e}")
                        
            except Exception as e:
                logger.error(f"❌ Ошибка отправки БД админам: {e}")
            
        else:
            await callback.message.answer("❌ Ошибка восстановления базы данных")
        
        # Удаляем загруженный файл
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
    
    # Удаляем загруженный файл если есть
    try:
        upload_dir = 'uploads'
        if os.path.exists(upload_dir):
            # Удаляем все файлы из uploads
            for filename in os.listdir(upload_dir):
                file_path = os.path.join(upload_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
    except Exception as e:
        logger.error(f"❌ Ошибка очистки uploads: {e}")
    
    await callback.message.answer("❌ Восстановление отменено")
    await callback.answer()

@router.message(Command("upload_db"), admin_filter)
async def upload_db_command(message: types.Message):
    """Инструкция по загрузке базы данных"""
    await message.answer(
        "📁 <b>Загрузка базы данных</b>\n\n"
        "Для загрузки новой базы данных:\n"
        "1. Отправьте мне файл <code>.db</code>\n"
        "2. Подтвердите восстановление\n"
        "3. Перезапустите бота командой <code>/restart</code>\n\n"
        "⚠️ <b>Внимание:</b>\n"
        "• Текущая БД будет заменена\n"
        "• Создается резервная копия\n"
        "• Максимальный размер файла: 100MB\n"
        "• Файл должен быть SQLite базой данных\n\n"
        "<b>Быстрые команды:</b>\n"
        "<code>/backup_now</code> - создать backup\n"
        "<code>/backups</code> - список бэкапов\n"
        "<code>/upload_db</code> - загрузить БД\n"
        "<code>/db_status</code> - статус БД",
        parse_mode="HTML"
    )

# ==================== ИСПРАВЛЕННЫЕ ОБРАБОТЧИКИ ЦЕН ====================

@router.callback_query(F.data.startswith("admin_price_edit_"))
async def admin_price_edit_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало изменения цены"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    package_id = callback.data.replace("admin_price_edit_", "")
    package = price_service.get_package_info(package_id)
    
    await state.update_data(editing_package=package_id)
    await state.set_state(AdminStates.waiting_price_value)
    
    await callback.message.answer(
        f"💰 <b>Изменение цены для {package['name']}</b>\n\n"
        f"Текущая цена: {price_service.format_price(package['current_price'])}\n"
        f"Базовая цена: {price_service.format_price(package['base_price'])}\n\n"
        "Введите новую цену в копейках (например: 1999 для 19.99₽):",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_price_discount_"))
async def admin_price_discount_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало установки скидки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    package_id = callback.data.replace("admin_price_discount_", "")
    package = price_service.get_package_info(package_id)
    
    await state.update_data(discount_package=package_id)
    await state.set_state(AdminStates.waiting_discount_value)
    
    await callback.message.answer(
        f"🔥 <b>Установка скидки для {package['name']}</b>\n\n"
        f"Текущая цена: {price_service.format_price(package['current_price'])}\n"
        f"Текущая скидка: {package['discount']}%\n\n"
        "Введите размер скидки в процентах (0-100):",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_price_toggle_"))
async def admin_price_toggle(callback: types.CallbackQuery):
    """Включение/выключение пакета"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    package_id = callback.data.replace("admin_price_toggle_", "")
    
    if price_service.toggle_package(package_id):
        package = price_service.get_package_info(package_id)
        status = "включен" if package["active"] else "выключен"
        await callback.answer(f"✅ Пакет {package['name']} {status}!")
        
        # Обновляем сообщение
        price_text = price_service.format_price(package["current_price"])
        base_price_text = price_service.format_price(package["base_price"])
        
        text = (
            f"🎯 <b>Управление пакетом</b>\n\n"
            f"📦 <b>Название:</b> {package['name']}\n"
            f"💰 <b>Текущая цена:</b> {price_text}\n"
            f"🏷️ <b>Базовая цена:</b> {base_price_text}\n"
            f"🔥 <b>Скидка:</b> {package['discount']}%\n"
            f"📊 <b>Статус:</b> {'🟢 Активен' if package['active'] else '🔴 Выключен'}\n\n"
            f"🔧 <b>Доступные действия:</b>"
        )
        
        await callback.message.edit_text(text, parse_mode="HTML", 
                                       reply_markup=admin_price_management_menu(package_id))
    else:
        await callback.answer("❌ Ошибка переключения пакета")

# ==================== ВЫХОД ИЗ АДМИНКИ ====================

@router.message(F.text == "🚪 Выйти из админки")
async def exit_admin_panel(message: types.Message):
    """Кнопка выхода из админ-панели"""
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
    """Callback кнопка выхода из админки"""
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
    """Подтверждение выхода из админки"""
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

@router.callback_query(F.data == "admin_main")
async def admin_back_to_main(callback: types.CallbackQuery):
    """Вернуться в главное меню админ-панели"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    await admin_panel(callback.message)
    await callback.answer()

# ==================== ГЛАВНОЕ МЕНЮ ====================

@router.message(Command("admin"))
@router.message(F.text == "👑 Админ-панель")
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    db = next(get_db())
    
    try:
        total_users = db.query(User).count()
        today_users = db.query(User).filter(
            User.created_at >= datetime.now().date()
        ).count()
        
        total_messages = db.query(AnonMessage).count()
        today_messages = db.query(AnonMessage).filter(
            AnonMessage.timestamp >= datetime.now().date()
        ).count()
        
        total_payments = db.query(Payment).filter(Payment.status == "completed").count()
        total_revenue = db.query(func.sum(Payment.amount)).filter(Payment.status == "completed").scalar() or 0
        
        week_ago = datetime.now() - timedelta(days=7)
        active_users = db.query(AnonMessage.sender_id).filter(
            AnonMessage.timestamp >= week_ago
        ).distinct().count()

        text = (
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

        await message.answer(text, parse_mode="HTML", reply_markup=admin_main_menu())
        
    finally:
        db.close()

# ==================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ====================

@router.message(F.text == "👥 Пользователи")
async def admin_users(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    db = next(get_db())
    try:
        total_users = db.query(User).count()
        today_users = db.query(User).filter(
            User.created_at >= datetime.now().date()
        ).count()
        
        text = (
            f"👥 <b>Управление пользователями</b>\n\n"
            f"📈 <b>Статистика:</b>\n"
            f"• Всего пользователей: <b>{total_users}</b>\n"
            f"• Новых сегодня: <b>{today_users}</b>\n\n"
            f"🔧 <b>Доступные действия:</b>\n"
            f"Выберите опцию ниже"
        )
        
        await message.answer(text, parse_mode="HTML", reply_markup=admin_users_menu())
        
    finally:
        db.close()

@router.callback_query(F.data == "admin_users")
async def admin_users_callback(callback: types.CallbackQuery):
    """Callback для управления пользователями"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    db = next(get_db())
    try:
        total_users = db.query(User).count()
        today_users = db.query(User).filter(
            User.created_at >= datetime.now().date()
        ).count()
        
        text = (
            f"👥 <b>Управление пользователями</b>\n\n"
            f"📈 <b>Статистика:</b>\n"
            f"• Всего пользователей: <b>{total_users}</b>\n"
            f"• Новых сегодня: <b>{today_users}</b>\n\n"
            f"🔧 <b>Доступные действия:</b>\n"
            f"Выберите опцию ниже"
        )
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_users_menu())
        await callback.answer()
        
    finally:
        db.close()

@router.callback_query(F.data == "admin_users_list")
async def admin_users_list(callback: types.CallbackQuery):
    """Список пользователей с пагинацией"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    db = next(get_db())
    try:
        page = 1
        users_per_page = 5
        offset = (page - 1) * users_per_page
        
        users = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(users_per_page).all()
        total_users = db.query(User).count()
        total_pages = (total_users + users_per_page - 1) // users_per_page
        
        text = f"📋 <b>Список пользователей</b> (страница {page}/{total_pages})\n\n"
        
        for user in users:
            messages_count = db.query(AnonMessage).filter(
                (AnonMessage.sender_id == user.id) | (AnonMessage.receiver_id == user.id)
            ).count()
            
            text += (
                f"👤 <b>{user.first_name}</b>\n"
                f"🆔 ID: <code>{user.telegram_id}</code>\n"
                f"📨 Сообщений: {messages_count}\n"
                f"👁️ Раскрытий: {user.available_reveals}\n"
                f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y')}\n"
                f"────────────────────\n"
            )
        
        # Если текст слишком длинный, обрезаем его
        if len(text) > 4096:
            text = text[:4000] + "\n... (сообщение обрезано)"
        
        await callback.message.edit_text(text, parse_mode="HTML", 
                                       reply_markup=admin_pagination_keyboard(page, total_pages, "users"))
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_users_list: {e}")
        await callback.answer("❌ Произошла ошибка")
    finally:
        db.close()
        
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
        
        db = next(get_db())
        users = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(users_per_page).all()
        total_users = db.query(User).count()
        total_pages = (total_users + users_per_page - 1) // users_per_page
        
        text = f"📋 <b>Список пользователей</b> (страница {page}/{total_pages})\n\n"
        
        for user in users:
            messages_count = db.query(AnonMessage).filter(
                (AnonMessage.sender_id == user.id) | (AnonMessage.receiver_id == user.id)
            ).count()
            
            text += (
                f"👤 <b>{user.first_name}</b>\n"
                f"🆔 ID: <code>{user.telegram_id}</code>\n"
                f"📨 Сообщений: {messages_count}\n"
                f"👁️ Раскрытий: {user.available_reveals}\n"
                f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y')}\n"
                f"────────────────────\n"
            )
        
        await callback.message.edit_text(text, parse_mode="HTML",
                                       reply_markup=admin_pagination_keyboard(page, total_pages, "users"))
        await callback.answer()
        
    finally:
        db.close()

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
    db = next(get_db())
    
    try:
        users = []
        
        if search_query.isdigit():
            user = db.query(User).filter(User.telegram_id == int(search_query)).first()
            if user:
                users.append(user)
        
        elif search_query.startswith('@'):
            username = search_query[1:]
            users = db.query(User).filter(User.username.ilike(f"%{username}%")).all()
        
        else:
            users = db.query(User).filter(User.first_name.ilike(f"%{search_query}%")).all()
        
        if not users:
            await message.answer("❌ Пользователи не найдены")
            await state.clear()
            return
        
        if len(users) == 1:
            user = users[0]
            await show_user_details(message, user)
        else:
            text = f"🔍 <b>Найдено пользователей:</b> {len(users)}\n\n"
            for i, user in enumerate(users[:10], 1):
                text += (
                    f"{i}. 👤 <b>{user.first_name}</b>\n"
                    f"   🆔 ID: <code>{user.telegram_id}</code>\n"
                    f"   🏷️ @{user.username or 'нет'}\n"
                    f"   ────────────────────\n"
                )
            
            if len(users) > 10:
                text += f"\n⚠️ Показано первых 10 из {len(users)} результатов"
            
            await message.answer(text, parse_mode="HTML")
        
        await state.clear()
        
    finally:
        db.close()

async def show_user_details(message: types.Message, user: User):
    """Показать детальную информацию о пользователе"""
    db = next(get_db())
    
    try:
        sent_messages = db.query(AnonMessage).filter(AnonMessage.sender_id == user.id).count()
        received_messages = db.query(AnonMessage).filter(AnonMessage.receiver_id == user.id).count()
        total_payments = db.query(Payment).filter(Payment.user_id == user.id, Payment.status == "completed").count()
        total_spent = db.query(func.sum(Payment.amount)).filter(
            Payment.user_id == user.id, Payment.status == "completed"
        ).scalar() or 0
        
        text = (
            f"👤 <b>Детальная информация</b>\n\n"
            f"🆔 <b>Telegram ID:</b> <code>{user.telegram_id}</code>\n"
            f"👤 <b>Имя:</b> {user.first_name}\n"
            f"🏷️ <b>Username:</b> @{user.username or 'не указан'}\n"
            f"🔗 <b>Ссылка:</b> {'✅ Активна' if user.anon_link_uid else '❌ Нет'}\n"
            f"👁️ <b>Раскрытий:</b> {user.available_reveals}\n"
            f"📅 <b>Регистрация:</b> {user.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            
            f"📊 <b>Статистика:</b>\n"
            f"• 📤 Отправлено сообщений: <b>{sent_messages}</b>\n"
            f"• 📨 Получено сообщений: <b>{received_messages}</b>\n"
            f"• 💳 Совершено покупок: <b>{total_payments}</b>\n"
            f"• 💰 Потрачено: <b>{total_spent / 100:.2f}₽</b>\n"
        )
        
        await message.answer(text, parse_mode="HTML", reply_markup=admin_user_actions_menu(user.id))
        
    finally:
        db.close()

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
        
        db = next(get_db())
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            await message.answer("❌ Пользователь не найден")
            await state.clear()
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

    text = (
        "💰 <b>Управление ценами</b>\n\n"
        "🎯 <b>Доступные пакеты:</b>\n"
        "Управляйте ценами и скидками на раскрытия\n\n"
        "🔧 <b>Доступные действия:</b>\n"
        "• Изменение цен\n"
        "• Установка скидок\n"
        "• Включение/выключение пакетов\n"
    )
    
    await message.answer(text, parse_mode="HTML", reply_markup=admin_prices_menu())

@router.callback_query(F.data == "admin_prices")
async def admin_prices_callback(callback: types.CallbackQuery):
    """Обработчик кнопки 'Управление ценами'"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    text = (
        "💰 <b>Управление ценами</b>\n\n"
        "🎯 <b>Доступные пакеты:</b>\n"
        "Управляйте ценами и скидками на раскрытия\n\n"
        "🔧 <b>Доступные действия:</b>\n"
        "• Изменение цен\n"
        "• Установка скидок\n"
        "• Включение/выключение пакетов\n"
    )
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_prices_menu())
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
            
            text = (
                f"🎯 <b>Управление пакетом</b>\n\n"
                f"📦 <b>Название:</b> {package['name']}\n"
                f"💰 <b>Текущая цена:</b> {price_text}\n"
                f"🏷️ <b>Базовая цена:</b> {base_price_text}\n"
                f"🔥 <b>Скидка:</b> {package['discount']}%\n"
                f"📊 <b>Статус:</b> {'🟢 Активен' if package['active'] else '🔴 Выключен'}\n\n"
                f"🔧 <b>Доступные действия:</b>"
            )
            
            await callback.message.edit_text(text, parse_mode="HTML", 
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

    db = next(get_db())
    
    try:
        total_users = db.query(User).count()
        week_ago = datetime.now() - timedelta(days=7)
        week_users = db.query(User).filter(User.created_at >= week_ago).count()
        
        total_messages = db.query(AnonMessage).count()
        week_messages = db.query(AnonMessage).filter(AnonMessage.timestamp >= week_ago).count()
        
        total_payments = db.query(Payment).filter(Payment.status == "completed").count()
        total_revenue = db.query(func.sum(Payment.amount)).filter(Payment.status == "completed").scalar() or 0
        
        package_stats = {}
        for package_id in price_service.get_all_packages():
            count = db.query(Payment).filter(
                Payment.payment_type == package_id,
                Payment.status == "completed"
            ).count()
            package_stats[package_id] = count

        text = (
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
            text += f"• {package['name']}: <b>{count}</b>\n"
        
        await message.answer(text, parse_mode="HTML", reply_markup=admin_stats_menu())
        
    finally:
        db.close()

@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: types.CallbackQuery):
    """Обработчик кнопки статистики"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    db = next(get_db())
    
    try:
        total_users = db.query(User).count()
        week_ago = datetime.now() - timedelta(days=7)
        week_users = db.query(User).filter(User.created_at >= week_ago).count()
        
        total_messages = db.query(AnonMessage).count()
        week_messages = db.query(AnonMessage).filter(AnonMessage.timestamp >= week_ago).count()
        
        total_payments = db.query(Payment).filter(Payment.status == "completed").count()
        total_revenue = db.query(func.sum(Payment.amount)).filter(Payment.status == "completed").scalar() or 0
        
        package_stats = {}
        for package_id in price_service.get_all_packages():
            count = db.query(Payment).filter(
                Payment.payment_type == package_id,
                Payment.status == "completed"
            ).count()
            package_stats[package_id] = count

        text = (
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
            text += f"• {package['name']}: <b>{count}</b>\n"
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_stats_menu())
        await callback.answer()
        
    finally:
        db.close()

# ==================== РАССЫЛКА ====================

@router.message(F.text == "📢 Рассылка")
async def admin_broadcast(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    db = next(get_db())
    
    try:
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.anon_link_uid.isnot(None)).count()
        
        text = (
            "📢 <b>Система рассылок</b>\n\n"
            f"👥 <b>Статистика аудитории:</b>\n"
            f"• Всего пользователей: <b>{total_users}</b>\n"
            f"• Активных пользователей: <b>{active_users}</b>\n\n"
            "🔧 <b>Доступные рассылки:</b>\n"
            "• Всем пользователям\n"
            "• Конкретному пользователю\n"
        )
        
        await message.answer(text, parse_mode="HTML", reply_markup=admin_broadcast_menu())
        
    finally:
        db.close()

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: types.CallbackQuery):
    """Обработчик кнопки рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    db = next(get_db())
    
    try:
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.anon_link_uid.isnot(None)).count()
        
        text = (
            "📢 <b>Система рассылок</b>\n\n"
            f"👥 <b>Статистика аудитории:</b>\n"
            f"• Всего пользователей: <b>{total_users}</b>\n"
            f"• Активных пользователей: <b>{active_users}</b>\n\n"
            "🔧 <b>Доступные рассылки:</b>\n"
            "• Всем пользователям\n"
            "• Конкретному пользователю\n"
        )
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_broadcast_menu())
        await callback.answer()
        
    finally:
        db.close()

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

    text = (
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
    
    await message.answer(text, parse_mode="HTML")

# ==================== ОБНОВЛЕНИЕ ====================

@router.message(F.text == "🔄 Обновить")
async def admin_refresh(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    await admin_panel(message)
    await message.answer("✅ <b>Данные обновлены!</b>", parse_mode="HTML")

# ==================== ОБРАБОТЧИК ОТМЕНЫ ВЫХОДА ====================

@router.callback_query(F.data == "admin_cancel_exit_admin")
async def admin_cancel_exit(callback: types.CallbackQuery):
    """Отмена выхода из админки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен")
        return

    await admin_panel(callback.message)
    await callback.answer("✅ Выход отменен")

# ==================== АДМИНСКИЕ КОМАНДЫ ====================

@router.message(Command("backup"))
async def backup_command(message: types.Message):
    """Создание резервной копии базы данных"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    await message.answer("🔄 Создаю резервную копию базы данных...")
    
    try:
        from app.backup_service import backup_service
        backup_path = backup_service.create_backup()
        
        if backup_path:
            await message.answer(
                "✅ <b>Резервная копия создана!</b>\n\n"
                f"📁 Файл: <code>{os.path.basename(backup_path)}</code>\n"
                f"💾 Размер: {backup_service.get_db_size():.2f} MB",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Ошибка создания резервной копии")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка при создании резервной копии: {e}")

@router.message(Command("db_status"))
async def db_status_command(message: types.Message):
    """Статус базы данных"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        from app.backup_service import backup_service
        size_mb = backup_service.get_db_size()
        stats = backup_service.get_db_stats()
        
        status_text = (
            "📊 <b>Статус базы данных</b>\n\n"
            f"💾 Размер: <b>{size_mb:.2f} MB</b>\n"
            f"👥 Пользователей: <b>{stats.get('users', 'N/A')}</b>\n"
            f"📨 Сообщений: <b>{stats.get('messages', 'N/A')}</b>\n"
            f"💰 Платежей: <b>{stats.get('payments', 'N/A')}</b>\n"
            f"⏳ Ожидающих платежей: <b>{stats.get('pending_payments', 'N/A')}</b>\n\n"
        )
        
        if size_mb > backup_service.critical_size_mb:
            status_text += "🚨 <b>КРИТИЧЕСКИЙ РАЗМЕР!</b>"
        elif size_mb > backup_service.max_size_mb:
            status_text += "⚠️ <b>Большой размер</b>"
        else:
            status_text += "✅ <b>Размер в норме</b>"
        
        await message.answer(status_text, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка получения статуса БД: {e}")

@router.message(Command("cleanup_old_data"))
async def cleanup_old_data_command(message: types.Message):
    """Очистка старых данных"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

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

@router.message(Command("user_info"))
async def user_info_command(message: types.Message):
    """Информация о пользователе"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer(
                "❌ Использование: /user_info ID_пользователя\n\n"
                "Пример: /user_info 123456789"
            )
            return

        telegram_id = int(args[1])
        db = next(get_db())
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        # Статистика пользователя
        sent_messages = db.query(AnonMessage).filter(AnonMessage.sender_id == user.id).count()
        received_messages = db.query(AnonMessage).filter(AnonMessage.receiver_id == user.id).count()
        total_payments = db.query(Payment).filter(Payment.user_id == user.id, Payment.status == "completed").count()
        total_spent = db.query(func.sum(Payment.amount)).filter(
            Payment.user_id == user.id, Payment.status == "completed"
        ).scalar() or 0
        
        text = (
            f"👤 <b>Информация о пользователе</b>\n\n"
            f"🆔 <b>Telegram ID:</b> <code>{user.telegram_id}</code>\n"
            f"👤 <b>Имя:</b> {user.first_name}\n"
            f"🏷️ <b>Username:</b> @{user.username or 'не указан'}\n"
            f"🔗 <b>Ссылка:</b> {'✅ Активна' if user.anon_link_uid else '❌ Нет'}\n"
            f"👁️ <b>Раскрытий:</b> {user.available_reveals}\n"
            f"📅 <b>Регистрация:</b> {user.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            
            f"📊 <b>Статистика:</b>\n"
            f"• 📤 Отправлено сообщений: <b>{sent_messages}</b>\n"
            f"• 📨 Получено сообщений: <b>{received_messages}</b>\n"
            f"• 💳 Совершено покупок: <b>{total_payments}</b>\n"
            f"• 💰 Потрачено: <b>{total_spent / 100:.2f}₽</b>\n"
        )
        
        await message.answer(text, parse_mode="HTML")
        db.close()

    except (IndexError, ValueError):
        await message.answer("❌ Использование: /user_info ID_пользователя")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("set_reveals"))
async def set_reveals_command(message: types.Message):
    """Установить количество раскрытий пользователю"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

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
        
        db = next(get_db())
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

        db.close()

    except (IndexError, ValueError):
        await message.answer("❌ Использование: /set_reveals ID_пользователя количество")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("backup_now"))
async def backup_now_command(message: types.Message):
    """Немедленное создание backup"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return
    
    await message.answer("🔄 Создаю резервную копию...")
    
    try:
        from app.backup_service import backup_service
        
        # Создаем backup
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



@router.message(Command("payment_status"))
async def payment_status_command(message: types.Message):
    """Статус платежной системы"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    db = next(get_db())
    try:
        total_payments = db.query(Payment).filter(Payment.status == "completed").count()
        pending_payments = db.query(Payment).filter(Payment.status == "pending").count()
        total_revenue = db.query(func.sum(Payment.amount)).filter(Payment.status == "completed").scalar() or 0
        
        text = (
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
        
        await message.answer(text, parse_mode="HTML")
        
    finally:
        db.close()
