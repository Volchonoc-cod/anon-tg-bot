from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from app.price_service import price_service

# Главное админ-меню
def admin_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="💰 Цены")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📢 Рассылка")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="🔄 Обновить")],
            [KeyboardButton(text="🚪 Выйти из админки")]
        ],
        resize_keyboard=True
    )

# Меню управления пользователями
def admin_users_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Список пользователей", callback_data="admin_users_list"),
                InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin_users_search")
            ],
            [
                InlineKeyboardButton(text="◀️ В админ-панель", callback_data="admin_main"),
                InlineKeyboardButton(text="🚪 Выйти из админки", callback_data="exit_admin")
            ]
        ]
    )

# Меню управления ценами
def admin_prices_menu():
    packages = price_service.get_all_packages()
    buttons = []
    
    for package_id, package in packages.items():
        status = "🟢" if package["active"] else "🔴"
        price_text = price_service.format_price(package["current_price"])
        discount_text = f" 🔥{package['discount']}%" if package["discount"] > 0 else ""
        
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {package['name']} - {price_text}{discount_text}", 
                callback_data=f"admin_price_{package_id}"
            )
        ])
    
    buttons.extend([
        [
            InlineKeyboardButton(text="◀️ В админ-панель", callback_data="admin_main"),
            InlineKeyboardButton(text="🚪 Выйти из админки", callback_data="exit_admin")
        ]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Меню управления конкретным пакетом
def admin_price_management_menu(package_id: str):
    package = price_service.get_package_info(package_id)
    status_text = "🔴 Выключить" if package["active"] else "🟢 Включить"
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить цену", callback_data=f"admin_price_edit_{package_id}")],
            [InlineKeyboardButton(text="🎯 Установить скидку", callback_data=f"admin_price_discount_{package_id}")],
            [InlineKeyboardButton(text=status_text, callback_data=f"admin_price_toggle_{package_id}")],
            [
                InlineKeyboardButton(text="◀️ Назад к ценам", callback_data="admin_prices"),
                InlineKeyboardButton(text="🚪 Выйти из админки", callback_data="exit_admin")
            ]
        ]
    )

# Меню статистики
def admin_stats_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="◀️ В админ-панель", callback_data="admin_main"),
                InlineKeyboardButton(text="🚪 Выйти из админки", callback_data="exit_admin")
            ]
        ]
    )

# Меню рассылки
def admin_broadcast_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📢 Всем пользователям", callback_data="admin_broadcast_all"),
                InlineKeyboardButton(text="👤 Конкретному пользователю", callback_data="admin_broadcast_user")
            ],
            [
                InlineKeyboardButton(text="◀️ В админ-панель", callback_data="admin_main"),
                InlineKeyboardButton(text="🚪 Выйти из админки", callback_data="exit_admin")
            ]
        ]
    )

# Клавиатура для действий с пользователем
def admin_user_actions_menu(user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👁️ Установить раскрытия", callback_data=f"admin_user_set_reveals_{user_id}"),
            ],
            [
                InlineKeyboardButton(text="◀️ Назад к пользователям", callback_data="admin_users"),
                InlineKeyboardButton(text="🚪 Выйти из админки", callback_data="exit_admin")
            ]
        ]
    )

# Клавиатура подтверждения
def admin_confirm_keyboard(action: str, target_id: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"admin_confirm_{action}_{target_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_cancel_{action}_{target_id}")
            ]
        ]
    )

# Клавиатура для пагинации
def admin_pagination_keyboard(page: int, total_pages: int, action: str):
    buttons = []
    
    if page > 1:
        buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_page_{action}_{page-1}"))
    
    buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="admin_page_current"))
    
    if page < total_pages:
        buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"admin_page_{action}_{page+1}"))
    
    return InlineKeyboardMarkup(inline_keyboard=[buttons])

# Клавиатура выхода из админки
def exit_admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, выйти", callback_data="confirm_exit_admin"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin_main")
            ]
        ]
    )
