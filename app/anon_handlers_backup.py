
# Обработчик кнопки "Написать еще сообщение"
@router.callback_query(F.data.startswith("send_another_"))
async def send_another_message(callback: types.CallbackQuery, state: FSMContext):
    target_link_uid = callback.data.replace("send_another_", "")
    
    db = next(get_db())
    try:
        target_user = db.query(User).filter(User.anon_link_uid == target_link_uid).first()
        if not target_user:
            await callback.answer("❌ Пользователь не найден")
            return

        await state.update_data(
            target_user_id=target_user.id,
            target_user_name=target_user.first_name
        )
        await state.set_state(AnonStates.waiting_for_message)

        await callback.message.answer(
            f"💌 Вы снова пишете анонимное сообщение для *{target_user.first_name}*\n\n"
            f"📝 Введите ваше сообщение:",
            parse_mode="Markdown"
        )
        await callback.answer()
    finally:
        db.close()

# Обработчик кнопки "Написать еще сообщение"
