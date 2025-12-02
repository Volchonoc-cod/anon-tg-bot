from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.orm import Session
from sqlalchemy import func
from aiogram.types import InputFile
import os
from datetime import datetime
from app.database import get_db
from app.models import User, AnonMessage, Payment
from app.config import ADMIN_IDS
from app.backup_service import backup_service
from app.database_cleaner import db_cleaner
from app.payment_service import payment_service
from app.price_service import price_service
from app.broadcast_service import broadcast_service

router = Router()

class BroadcastStates(StatesGroup):
    waiting_broadcast_message = State()
    waiting_user_message = State()

def is_admin(user_id: int):
    return user_id in ADMIN_IDS

@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    db = next(get_db())

    # Статистика
    total_users = db.query(User).count()
    total_messages = db.query(AnonMessage).count()
    users_with_links = db.query(User).filter(User.anon_link_uid.isnot(None)).count()
    reported_messages = db.query(AnonMessage).filter(AnonMessage.is_reported == True).count()

    # Статистика по платежам
    total_payments = db.query(Payment).filter(Payment.status == "completed").count()
    total_revenue = db.query(func.sum(Payment.amount)).filter(Payment.status == "completed").scalar() or 0

    # Размер базы данных
    db_size = backup_service.get_db_size()

    text = (
        "👑 <b>Админ-панель</b>\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"📨 Сообщений: <b>{total_messages}</b>\n"
        f"🔗 Пользователей с ссылками: <b>{users_with_links}</b>\n"
        f"🚫 Жалоб на сообщения: <b>{reported_messages}</b>\n"
        f"💰 Всего платежей: <b>{total_payments}</b>\n"
        f"📈 Общая выручка: <b>{total_revenue / 100:.2f}₽</b>\n"
        f"💾 Размер базы: <b>{db_size:.2f} MB</b>\n\n"
        "💼 <b>Команды управления:</b>\n"
        "/admin_users - список пользователей\n"
        "/admin_messages - все сообщения\n"
        "/admin_reports - жалобы\n"
        "/admin_payments - платежи\n"
        "/backup - резервная копия\n"
        "/db_status - статус базы\n"
        "/cleanup_old_data - очистка старых данных\n"
        "/pending_payments - ожидающие платежи\n"
        "/user_info - информация о пользователе\n"
        "/set_reveals - установить раскрытия\n"
        "/payment_status - статус платежной системы\n"
        "/broadcast - рассылка сообщений\n"
        "/prices - управление ценами"
    )

    await message.answer(text, parse_mode="HTML")

# === СТАТИСТИКА И ОТЧЕТЫ ===

@router.message(Command("admin_users"))
async def admin_users(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    db = next(get_db())
    users = db.query(User).order_by(User.created_at.desc()).limit(10).all()

    text = "👥 <b>Последние 10 пользователей:</b>\n\n"

    for user in users:
        messages_count = db.query(AnonMessage).filter(AnonMessage.receiver_id == user.id).count()
        has_link = "✅" if user.anon_link_uid else "❌"
        text += f"👤 {user.first_name} (@{user.username})\n"
        text += f"   ID: {user.telegram_id}\n"
        text += f"   Сообщений: {messages_count}\n"
        text += f"   Раскрытий: {user.available_reveals}\n"
        text += f"   Ссылка: {has_link}\n"
        text += f"   Регистрация: {user.created_at.strftime('%d.%m.%Y')}\n\n"

    await message.answer(text, parse_mode="HTML")
    db.close()

@router.message(Command("admin_messages"))
async def admin_messages(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    db = next(get_db())
    messages = db.query(AnonMessage).order_by(AnonMessage.timestamp.desc()).limit(5).all()

    text = "📨 <b>Последние 5 сообщений:</b>\n\n"

    for msg in messages:
        receiver = db.query(User).filter(User.id == msg.receiver_id).first()

        if msg.sender_id:
            sender = db.query(User).filter(User.id == msg.sender_id).first()
            sender_info = f"👤 {sender.first_name}" if sender else "Неизвестно"
        else:
            sender_info = "🕵️ Аноним"

        anonymity = "🕵️ Анонимное" if msg.is_anonymous and not msg.is_revealed else "👤 Открытое"
        reported = " 🚫" if msg.is_reported else ""

        text += f"{anonymity}{reported} сообщение:\n"
        text += f"   📝 {msg.text[:50]}...\n"
        text += f"   👤 Отправитель: {sender_info}\n"
        text += f"   👥 Получатель: {receiver.first_name if receiver else 'Неизвестно'}\n"
        text += f"   🕐 {msg.timestamp.strftime('%d.%m.%Y %H:%M')}\n\n"

    await message.answer(text, parse_mode="HTML")
    db.close()

@router.message(Command("admin_reports"))
async def admin_reports(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    db = next(get_db())
    reported_messages = db.query(AnonMessage).filter(AnonMessage.is_reported == True).order_by(AnonMessage.timestamp.desc()).all()

    if not reported_messages:
        await message.answer("🚫 Нет жалоб на сообщения")
        return

    text = "🚫 <b>Жалобы на сообщения:</b>\n\n"

    for i, msg in enumerate(reported_messages, 1):
        receiver = db.query(User).filter(User.id == msg.receiver_id).first()

        if msg.sender_id:
            sender = db.query(User).filter(User.id == msg.sender_id).first()
            sender_info = f"👤 {sender.first_name}" if sender else "Неизвестно"
        else:
            sender_info = "🕵️ Аноним"

        text += f"{i}. ID: {msg.id}\n"
        text += f"   📝 {msg.text[:100]}...\n"
        text += f"   👤 Отправитель: {sender_info}\n"
        text += f"   👥 Получатель: {receiver.first_name if receiver else 'Неизвестно'}\n"
        text += f"   🕐 {msg.timestamp.strftime('%d.%m.%Y %H:%M')}\n\n"

    await message.answer(text, parse_mode="HTML")
    db.close()

@router.message(Command("admin_payments"))
async def admin_payments(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    db = next(get_db())
    payments = db.query(Payment).filter(Payment.status == "completed").order_by(Payment.completed_at.desc()).limit(10).all()

    text = "💰 <b>Последние 10 платежей:</b>\n\n"

    for payment in payments:
        user = db.query(User).filter(User.id == payment.user_id).first()
        amount_rub = payment.amount / 100

        type_names = {
            "reveal_1": "1 раскрытие",
            "reveal_10": "10 раскрытий",
            "reveal_30": "30 раскрытий",
            "reveal_50": "50 раскрытий",
            "month_sub": "Подписка месяц"
        }

        text += f"💳 {type_names.get(payment.payment_type, payment.payment_type)}\n"
        text += f"   👤 {user.first_name} (@{user.username})\n"
        text += f"   💰 {amount_rub:.2f}₽\n"
        text += f"   🕐 {payment.completed_at.strftime('%d.%m.%Y %H:%M')}\n\n"

    await message.answer(text, parse_mode="HTML")
    db.close()

@router.message(Command("pending_payments"))
async def show_pending_payments(message: types.Message):
    """Показать ожидающие платежи"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    db = next(get_db())
    try:
        pending_payments = db.query(Payment).filter(Payment.status == "pending").order_by(Payment.created_at.desc()).all()

        if not pending_payments:
            await message.answer("✅ Нет ожидающих платежей")
            return

        text = "⏳ <b>Ожидающие платежи:</b>\n\n"
        
        for payment in pending_payments:
            user = db.query(User).filter(User.id == payment.user_id).first()
            amount_rub = payment.amount / 100
            
            type_names = {
                "reveal_1": "1 раскрытие",
                "reveal_10": "10 раскрытий", 
                "reveal_30": "30 раскрытий",
                "reveal_50": "50 раскрытий"
            }
            
            text += (
                f"💳 <b>Платеж ID: {payment.id}</b>\n"
                f"👤 Пользователь: {user.first_name} (ID: {user.telegram_id})\n"
                f"📦 Услуга: {type_names.get(payment.payment_type, payment.payment_type)}\n"
                f"💰 Сумма: {amount_rub:.2f}₽\n"
                f"🕐 Создан: {payment.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"🔗 Подтвердить: /confirm_payment {payment.id}\n\n"
            )

        await message.answer(text, parse_mode="HTML")
    finally:
        db.close()

@router.message(Command("confirm_payment"))
async def confirm_payment_command(message: types.Message):
    """Подтверждение платежа админом"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer("❌ Использование: /confirm_payment ID_платежа")
            return

        payment_id = int(args[1])
        db = next(get_db())
        
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            await message.answer("❌ Платеж не найден")
            return

        if payment.status == "completed":
            await message.answer("✅ Платеж уже подтвержден")
            return

        success = payment_service.complete_payment_by_id(db, payment_id)

        if success:
            user = db.query(User).filter(User.id == payment.user_id).first()
            
            try:
                await message.bot.send_message(
                    user.telegram_id,
                    f"✅ <b>Платеж подтвержден!</b>\n\n"
                    f"💰 Сумма: {payment.amount / 100:.2f}₽\n"
                    f"📦 Услуга: {payment.payment_type}\n"
                    f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"Доступ активирован!",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"❌ Ошибка уведомления пользователя: {e}")

            await message.answer(
                f"✅ <b>Платеж подтвержден</b>\n\n"
                f"👤 Пользователь: {user.first_name}\n"
                f"💳 Сумма: {payment.amount / 100:.2f}₽\n"
                f"📦 Услуга: {payment.payment_type}\n"
                f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Ошибка подтверждения платежа")

        db.close()

    except (IndexError, ValueError):
        await message.answer("❌ Использование: /confirm_payment ID_платежа")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# === УПРАВЛЕНИЕ БАЗОЙ ДАННЫХ ===

@router.message(Command("backup"))
async def manual_backup(message: types.Message):
    """Ручное создание резервной копии"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    await message.answer("🔄 Создаю резервную копию базы данных...")
    backup_path = backup_service.create_backup()
    
    if backup_path:
        await message.answer("✅ Резервная копия создана!")
    else:
        await message.answer("❌ Ошибка создания резервной копии")

@router.message(Command("db_status"))
async def db_status(message: types.Message):
    """Показать статус базы данных"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    size_mb = backup_service.get_db_size()
    stats = backup_service.get_db_stats()

    status_text = (
        "📊 <b>Статус базы данных</b>\n\n"
        f"• Размер: {size_mb:.2f} MB\n"
        f"• Лимит предупреждения: {backup_service.max_size_mb} MB\n"
        f"• Критический лимит: {backup_service.critical_size_mb} MB\n\n"
        f"📈 <b>Статистика:</b>\n"
        f"• 👥 Пользователей: {stats.get('users', 'N/A')}\n"
        f"• 📨 Сообщений: {stats.get('messages', 'N/A')}\n"
        f"• 💰 Платежей: {stats.get('payments', 'N/A')}\n\n"
    )

    if size_mb > backup_service.critical_size_mb:
        status_text += "🚨 <b>КРИТИЧЕСКИЙ РАЗМЕР!</b>"
    elif size_mb > backup_service.max_size_mb:
        status_text += "⚠️ <b>Большой размер</b>"
    else:
        status_text += "✅ <b>Размер в норме</b>"

    await message.answer(status_text, parse_mode="HTML")

@router.message(Command("cleanup_old_data"))
async def cleanup_old_data(message: types.Message):
    """Очистка старых данных"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    await message.answer("🔄 Очищаю старые данные...")
    deleted_messages, deleted_payments = await db_cleaner.cleanup_old_data()

    await message.answer(
        f"🧹 <b>Очистка завершена</b>\n\n"
        f"• Удалено сообщений: {deleted_messages}\n"
        f"• Удалено платежей: {deleted_payments}\n"
        f"• Новый размер: {backup_service.get_db_size():.2f} MB",
        parse_mode="HTML"
    )

# === УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ===

@router.message(Command("user_info"))
async def user_info_command(message: types.Message):
    """Информация о пользователе"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer("❌ Использование: /user_info ID_пользователя")
            return

        telegram_id = int(args[1])
        db = next(get_db())
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        text = (
            f"👤 <b>Информация о пользователе</b>\n\n"
            f"🆔 ID: {user.id}\n"
            f"📱 Telegram ID: <code>{user.telegram_id}</code>\n"
            f"👤 Имя: {user.first_name}\n"
            f"🏷️ Username: @{user.username if user.username else 'не указан'}\n"
            f"👁️ Раскрытий: {user.available_reveals}\n"
            f"🔗 Ссылка: {'✅' if user.anon_link_uid else '❌'}\n"
            f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M')}"
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
            await message.answer("❌ Использование: /set_reveals ID_пользователя количество")
            return

        telegram_id = int(args[1])
        new_count = int(args[2])
        
        db = next(get_db())
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        success = payment_service.set_reveals(db, user.id, new_count)

        if success:
            await message.answer(f"✅ Установлено {new_count} раскрытий для пользователя {user.first_name} (ID: {user.telegram_id})")
        else:
            await message.answer("❌ Ошибка установки раскрытий")

        db.close()

    except (IndexError, ValueError):
        await message.answer("❌ Использование: /set_reveals ID_пользователя количество")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# === РАССЫЛКА СООБЩЕНИЙ ===

@router.message(Command("broadcast"))
async def broadcast_command(message: types.Message):
    """Команда рассылки сообщений"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    await message.answer(
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Выберите тип рассылки:\n"
        "• /broadcast_all - всем пользователям\n"
        "• /broadcast_user - конкретному пользователю\n\n"
        "⚠️ <b>Внимание:</b> Рассылка всем пользователям может занять несколько минут!",
        parse_mode="HTML"
    )

@router.message(Command("broadcast_all"))
async def broadcast_all_command(message: types.Message, state: FSMContext):
    """Рассылка всем пользователям"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    await message.answer(
        "📢 <b>Рассылка всем пользователям</b>\n\n"
        "Введите сообщение для рассылки:",
        parse_mode="HTML"
    )
    await state.set_state(BroadcastStates.waiting_broadcast_message)

@router.message(Command("broadcast_user"))
async def broadcast_user_command(message: types.Message, state: FSMContext):
    """Рассылка конкретному пользователю"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer(
                "📢 <b>Рассылка конкретному пользователю</b>\n\n"
                "Использование: /broadcast_user ID_пользователя\n\n"
                "Пример: /broadcast_user 123456789",
                parse_mode="HTML"
            )
            return

        telegram_id = int(args[1])
        await state.update_data(target_user_id=telegram_id)
        await message.answer(
            f"📢 <b>Рассылка пользователю</b>\n"
            f"🆔 ID: <code>{telegram_id}</code>\n\n"
            f"Введите сообщение для отправки:",
            parse_mode="HTML"
        )
        await state.set_state(BroadcastStates.waiting_user_message)

    except ValueError:
        await message.answer("❌ Неверный формат ID пользователя")

@router.message(BroadcastStates.waiting_broadcast_message)
async def process_broadcast_message(message: types.Message, state: FSMContext):
    """Обработка сообщения для рассылки всем"""
    from aiogram import Bot
    from app.config import BOT_TOKEN
    
    bot = Bot(token=BOT_TOKEN)
    broadcast_service.set_bot(bot)
    
    await broadcast_service.broadcast_to_all(
        message.text,
        message.from_user.id
    )
    
    await state.clear()

@router.message(BroadcastStates.waiting_user_message)
async def process_user_message(message: types.Message, state: FSMContext):
    """Обработка сообщения для конкретного пользователя"""
    from aiogram import Bot
    from app.config import BOT_TOKEN
    
    user_data = await state.get_data()
    telegram_id = user_data.get('target_user_id')
    
    if not telegram_id:
        await message.answer("❌ Ошибка: ID пользователя не найден")
        await state.clear()
        return

    bot = Bot(token=BOT_TOKEN)
    broadcast_service.set_bot(bot)
    
    await broadcast_service.send_to_user(
        telegram_id,
        message.text,
        message.from_user.id
    )
    
    await state.clear()

# === УПРАВЛЕНИЕ ЦЕНАМИ ===

@router.message(Command("prices"))
async def prices_command(message: types.Message):
    """Управление ценами"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    text = price_service.get_price_text()
    text += (
        "\n\n💼 <b>Команды управления ценами:</b>\n"
        "• /set_price пакет цена - изменить цену\n"
        "• /set_discount пакет скидка% [дни] - установить скидку\n"
        "• /add_package id название цена - добавить пакет\n"
        "• /toggle_package id - вкл/выкл пакет\n\n"
        "📦 <b>Доступные пакеты:</b>\n"
    )
    
    packages = price_service.get_all_packages()
    for package_id, package in packages.items():
        status = "✅" if package["active"] else "❌"
        text += f"{status} <code>{package_id}</code> - {package['name']}\n"

    await message.answer(text, parse_mode="HTML")

@router.message(Command("set_price"))
async def set_price_command(message: types.Message):
    """Установить цену для пакета"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        args = message.text.split()
        if len(args) < 3:
            await message.answer(
                "❌ Использование: /set_price пакет цена\n\n"
                "Пример: /set_price reveal_1 1999\n"
                "Установит цену 19.99₽ за 1 раскрытие"
            )
            return

        package_id = args[1]
        price = int(args[2])
        
        if price_service.update_price(package_id, price):
            await message.answer(
                f"✅ Цена для пакета обновлена!\n\n"
                f"{price_service.get_price_text()}",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Пакет не найден")

    except ValueError:
        await message.answer("❌ Неверный формат цены")

@router.message(Command("set_discount"))
async def set_discount_command(message: types.Message):
    """Установить скидку на пакет"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        args = message.text.split()
        if len(args) < 3:
            await message.answer(
                "❌ Использование: /set_discount пакет скидка% [дни]\n\n"
                "Пример: /set_discount reveal_10 20 3\n"
                "Установит скидку 20% на 10 раскрытий на 3 дня"
            )
            return

        package_id = args[1]
        discount = int(args[2])
        days = int(args[3]) if len(args) > 3 else 7
        
        if price_service.set_discount(package_id, discount, days):
            await message.answer(
                f"✅ Скидка установлена!\n\n"
                f"{price_service.get_price_text()}",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Пакет не найден")

    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат параметров")

@router.message(Command("add_package"))
async def add_package_command(message: types.Message):
    """Добавить новый пакет"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        args = message.text.split()
        if len(args) < 4:
            await message.answer(
                "❌ Использование: /add_package id название цена\n\n"
                "Пример: /add_package reveal_5 '5 раскрытий' 7999\n"
                "Добавит пакет 5 раскрытий за 79.99₽"
            )
            return

        package_id = args[1]
        name = ' '.join(args[2:-1]).strip("'\"")
        price = int(args[-1])
        
        if price_service.add_new_package(package_id, name, price):
            await message.answer(
                f"✅ Новый пакет добавлен!\n\n"
                f"🎁 {name} - {price_service.format_price(price)}\n\n"
                f"{price_service.get_price_text()}",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Пакет с таким ID уже существует")

    except ValueError:
        await message.answer("❌ Неверный формат цены")

@router.message(Command("toggle_package"))
async def toggle_package_command(message: types.Message):
    """Включить/выключить пакет"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer(
                "❌ Использование: /toggle_package id\n\n"
                "Пример: /toggle_package reveal_1"
            )
            return

        package_id = args[1]
        
        if price_service.toggle_package(package_id):
            package = price_service.get_package_info(package_id)
            status = "включен" if package["active"] else "выключен"
            await message.answer(f"✅ Пакет {package['name']} {status}!")
        else:
            await message.answer("❌ Пакет не найден")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# === СТАТУС ПЛАТЕЖНОЙ СИСТЕМЫ ===

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
        "• Уведомления о новых платежей\n"
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
