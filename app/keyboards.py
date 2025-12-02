from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from app.price_service import price_service

# Главное меню
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔗 Моя ссылка"), KeyboardButton(text="🔄 Пересоздать ссылку")],
            [KeyboardButton(text="💰 Платные функции"), KeyboardButton(text="📊 Мой профиль")]
        ],
        resize_keyboard=True
    )

# Универсальная клавиатура для всех сообщений
def message_actions_keyboard(message_id: int, can_reveal: bool = True):
    buttons = [
        [
            InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_{message_id}"),
            InlineKeyboardButton(text="🚫 Пожаловаться", callback_data=f"report_{message_id}")
        ]
    ]

    if can_reveal:
        buttons.append([
            InlineKeyboardButton(text="👁️ Раскрыть отправителя", callback_data=f"reveal_{message_id}")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="💰 Купить раскрытие", callback_data="premium_menu")
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Подтверждение пересоздания ссылки
def recreate_link_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, пересоздать", callback_data="recreate_link_confirm")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="recreate_link_cancel")]
        ]
    )

# Клавиатура для отправки еще одного сообщения
def send_another_message_keyboard(target_link_uid: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✉️ Написать еще сообщение", callback_data=f"send_another_{target_link_uid}")],
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_main")]
        ]
    )

# Меню платных функций (динамическое на основе price_service)
def premium_menu():
    packages = price_service.get_all_packages()
    buttons = []
    
    for package_id, package in packages.items():
        if package["active"]:
            price_text = price_service.format_price(package["current_price"])
            discount_text = f" 🔥" if package["discount"] > 0 else ""
            button_text = f"👁️ {package['name']} - {price_text}{discount_text}"
            buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"buy_{package_id}")])
    
    buttons.extend([
        [InlineKeyboardButton(text="📊 Мой статус", callback_data="my_status")],
        [InlineKeyboardButton(text="👤 Информация о себе", callback_data="user_info")],
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_main")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Клавиатура для профиля пользователя
def profile_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 Платные функции", callback_data="premium_menu")],
            [InlineKeyboardButton(text="🔗 Моя ссылка", callback_data="my_link")],
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_main")]
        ]
    )

# Клавиатура для админ-управления ценами
def admin_prices_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Текущие цены", callback_data="admin_prices")],
            [InlineKeyboardButton(text="🎯 Управление ценами", callback_data="admin_manage_prices")],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="◀️ В админ-панель", callback_data="admin_panel")]
        ]
    )

# Клавиатура для управления конкретным пакетом
def package_management_menu(package_id: str):
    package = price_service.get_package_info(package_id)
    status_text = "❌ Выключить" if package["active"] else "✅ Включить"
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 Изменить цену", callback_data=f"admin_set_price_{package_id}")],
            [InlineKeyboardButton(text="🔥 Установить скидку", callback_data=f"admin_set_discount_{package_id}")],
            [InlineKeyboardButton(text=status_text, callback_data=f"admin_toggle_{package_id}")],
            [InlineKeyboardButton(text="◀️ Назад к ценам", callback_data="admin_prices")]
        ]
    )
