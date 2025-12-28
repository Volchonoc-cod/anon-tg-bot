from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from app.price_service import price_service
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# Главное админ-меню
def admin_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="💬 Переписки")],
            [KeyboardButton(text="💰 Цены"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="📢 Рассылка"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="🔄 Обновить"), KeyboardButton(text="🚪 Выйти из админки")]
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
# Добавьте в конец файла app/keyboards_admin.py:

def admin_settings_menu():
    """Клавиатура настроек"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💾 Бэкап БД", callback_data="admin_backup"),
                InlineKeyboardButton(text="🔄 Восстановить", callback_data="admin_restore")
            ],
            [
                InlineKeyboardButton(text="📊 Статус БД", callback_data="admin_db_status"),
                InlineKeyboardButton(text="🧹 Очистка", callback_data="admin_cleanup")
            ],
            [
                InlineKeyboardButton(text="📁 Бэкапы", callback_data="admin_backups_list"),
                InlineKeyboardButton(text="📤 Экспорт", callback_data="admin_export")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main")
            ]
        ]
    )


def admin_conversations_menu():
    """Меню управления переписками"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Список пользователей с переписками", 
                                   callback_data="admin_conversations_list"),
            ],
            [
                InlineKeyboardButton(text="🔍 Найти пользователя", 
                                   callback_data="admin_conversations_search"),
                InlineKeyboardButton(text="🔎 Поиск по сообщениям", 
                                   callback_data="admin_search_messages")
            ],
            [
                InlineKeyboardButton(text="◀️ В админ-панель", callback_data="admin_main"),
                InlineKeyboardButton(text="🚪 Выйти из админки", callback_data="exit_admin")
            ]
        ]
    )

def admin_user_conversations_menu(user_id: int, conversations_count: int = 0):
    """Меню переписок конкретного пользователя"""
    buttons = [
        [
            InlineKeyboardButton(text="📋 Все переписки", 
                               callback_data=f"admin_view_conversations_{user_id}"),
        ],
        [
            InlineKeyboardButton(text="📊 Статистика сообщений", 
                               callback_data=f"admin_user_stats_{user_id}"),
        ]
    ]
    
    if conversations_count > 0:
        buttons.insert(1, [
            InlineKeyboardButton(text="💬 Последние диалоги", 
                               callback_data=f"admin_recent_conversations_{user_id}")
        ])
    
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад к перепискам", callback_data="admin_conversations"),
        InlineKeyboardButton(text="🚪 Выйти из админки", callback_data="exit_admin")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_message_history_keyboard(user1_id: int, user2_id: int, page: int = 1, total_pages: int = 1):
    """Клавиатура для навигации по истории сообщений"""
    buttons = []
    
    # Кнопки навигации если есть несколько страниц
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(
                text="◀️ Назад", 
                callback_data=f"admin_conversation_page_{user1_id}_{user2_id}_{page-1}"
            ))
        
        nav_buttons.append(InlineKeyboardButton(
            text=f"{page}/{total_pages}", 
            callback_data="no_action"
        ))
        
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(
                text="Вперед ▶️", 
                callback_data=f"admin_conversation_page_{user1_id}_{user2_id}_{page+1}"
            ))
        
        buttons.append(nav_buttons)
    
    # Основные кнопки действий
    buttons.append([
        InlineKeyboardButton(text="📥 Экспорт переписки", 
                           callback_data=f"admin_export_conversation_{user1_id}_{user2_id}"),
    ])
    
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад к пользователю", 
                           callback_data=f"admin_view_conversations_{user1_id}"),
        InlineKeyboardButton(text="🏠 В админ-панель", callback_data="admin_main")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

