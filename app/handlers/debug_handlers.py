from aiogram import F, Router, types
from aiogram.filters import Command

router = Router()

@router.message(Command("debug"))
async def debug_command(message: types.Message):
    """Команда для отладки"""
    await message.answer(
        f"🔄 <b>Debug информация:</b>\n\n"
        f"👤 ID: {message.from_user.id}\n"
        f"📝 Текст: {message.text}\n"
        f"🏷️ Username: @{message.from_user.username}\n"
        f"📅 Дата: {message.date}",
        parse_mode="HTML"
    )

# УБРАЛИ общий обработчик callback_query()
