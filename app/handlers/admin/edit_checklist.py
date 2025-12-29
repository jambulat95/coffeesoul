from __future__ import annotations

import asyncio

from aiogram import F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import crud as db
from app import keyboards as kb
from app.utils import cancel_kb, nav_kb

from .router import router
from .states import EditChecklist


@router.message(F.text == "✏️ Редактировать шаблон")
async def start_edit_checklist(message: types.Message, state: FSMContext) -> None:
    """Начало редактирования - показываем список чек-листов админа"""
    admin_shops = await db.get_admin_shops(message.from_user.id)
    all_checklists = await db.get_checklists()
    
    # Фильтруем чек-листы, которые принадлежат админу
    my_checklists = [
        ch for ch in all_checklists 
        if ch.shop_id is None or ch.shop_id in admin_shops
    ]
    
    if not my_checklists:
        await message.answer("📭 У вас пока нет созданных шаблонов.")
        return
    
    builder = InlineKeyboardBuilder()
    for ch in my_checklists:
        shop_text = ch.shop_id if ch.shop_id else "Все точки"
        builder.button(
            text=f"📋 {ch.title} ({shop_text})", 
            callback_data=f"edit_ch_{ch.id}"
        )
    builder.button(text="❌ Отмена", callback_data="cancel_edit")
    builder.adjust(1)
    
    await message.answer(
        "✏️ <b>Редактирование шаблона</b>\n👇 Выберите шаблон для редактирования:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(EditChecklist.select_checklist)


@router.callback_query(F.data == "cancel_edit")
async def cancel_edit(callback: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Редактирование отменено.")


@router.callback_query(F.data.startswith("edit_ch_"))
async def show_checklist_menu(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Показываем меню редактирования конкретного чек-листа"""
    checklist_id = int(callback.data.split("_")[2])
    checklist = await db.get_checklist(checklist_id)
    
    if not checklist:
        await callback.answer("Шаблон не найден.", show_alert=True)
        return
    
    await state.update_data(checklist_id=checklist_id)
    
    shop_text = checklist.shop_id if checklist.shop_id else "Все точки"
    pos_text = checklist.target_position if checklist.target_position else "Все должности"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Изменить название", callback_data="edit_title")
    builder.button(text="🏠 Изменить точку", callback_data="edit_shop")
    builder.button(text="👔 Изменить должность", callback_data="edit_position")
    builder.button(text="❓ Управление вопросами", callback_data="edit_questions")
    builder.button(text="🗑 Удалить шаблон", callback_data="delete_checklist")
    builder.button(text="❌ Отмена", callback_data="cancel_edit")
    builder.adjust(1)
    
    text = (
        f"✏️ <b>Редактирование шаблона</b>\n\n"
        f"📋 <b>Название:</b> {checklist.title}\n"
        f"🏠 <b>Точка:</b> {shop_text}\n"
        f"👔 <b>Должность:</b> {pos_text}\n\n"
        f"👇 Выберите что изменить:"
    )
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "edit_title")
async def start_edit_title(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(
        "✏️ <b>Изменение названия</b>\nВведите новое название:",
        reply_markup=cancel_kb("cancel_edit")
    )
    await state.set_state(EditChecklist.edit_title)


@router.message(EditChecklist.edit_title)
async def save_title(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    checklist_id = data["checklist_id"]
    await db.update_checklist(checklist_id, title=message.text)
    await message.answer("✅ Название обновлено!")
    await show_checklist_menu_after_edit(message, state)


async def show_checklist_menu_after_edit(message_or_callback, state: FSMContext, status_text: str | None = None) -> None:
    """Показываем меню редактирования после изменения"""
    data = await state.get_data()
    checklist_id = data["checklist_id"]
    checklist = await db.get_checklist(checklist_id)
    
    if not checklist:
        return
    
    shop_text = checklist.shop_id if checklist.shop_id else "Все точки"
    pos_text = checklist.target_position if checklist.target_position else "Все должности"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Изменить название", callback_data="edit_title")
    builder.button(text="🏠 Изменить точку", callback_data="edit_shop")
    builder.button(text="👔 Изменить должность", callback_data="edit_position")
    builder.button(text="❓ Управление вопросами", callback_data="edit_questions")
    builder.button(text="🗑 Удалить шаблон", callback_data="delete_checklist")
    builder.button(text="❌ Отмена", callback_data="cancel_edit")
    builder.adjust(1)
    
    text = (
        f"✏️ <b>Редактирование шаблона</b>\n\n"
        f"📋 <b>Название:</b> {checklist.title}\n"
        f"🏠 <b>Точка:</b> {shop_text}\n"
        f"👔 <b>Должность:</b> {pos_text}\n\n"
        f"👇 Выберите что изменить:"
    )
    
    if status_text:
        text = f"{status_text}\n\n{text}"
    
    from aiogram.exceptions import TelegramBadRequest
    
    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(text, reply_markup=builder.as_markup())
    else:
        # Пытаемся отредактировать сообщение
        # Игнорируем ошибку "message is not modified" - это нормально, если сообщение уже содержит нужный контент
        try:
            await message_or_callback.message.edit_text(text, reply_markup=builder.as_markup())
        except TelegramBadRequest as e:
            error_msg = str(e).lower()
            if "message is not modified" in error_msg:
                # Сообщение уже в правильном состоянии - это нормально, просто игнорируем
                return
            # Если это другая ошибка, пробрасываем её дальше
            raise


@router.callback_query(F.data == "edit_shop")
async def start_edit_shop(callback: types.CallbackQuery, state: FSMContext) -> None:
    admin_shops = await db.get_admin_shops(callback.from_user.id)
    
    if len(admin_shops) == 1:
        # Если у админа только одна точка, делаем визуальный эффект
        try:
            await callback.message.edit_text("🔄 <b>Обновление...</b>")
        except Exception:
            pass
            
        await asyncio.sleep(0.5)
        
        data = await state.get_data()
        checklist_id = data["checklist_id"]
        new_shop_id = admin_shops[0]
        
        # Обновляем точку
        await db.update_checklist(checklist_id, shop_id=new_shop_id)
        
        # Показываем обновленное меню
        await show_checklist_menu_after_edit(
            callback, 
            state, 
            status_text=f"✅ Точка установлена: <b>{new_shop_id}</b>"
        )
        return
    
    await callback.answer()
    builder = InlineKeyboardBuilder()
    builder.button(text="🌍 Для всех моих точек", callback_data="shop_all")
    for shop in admin_shops:
        builder.button(text=f"🏠 {shop}", callback_data=f"shop_sel_{shop}")
    builder.adjust(1)
    builder.button(text="❌ Отмена", callback_data="cancel_edit")
    
    from aiogram.exceptions import TelegramBadRequest
    try:
        await callback.message.edit_text(
            "📍 <b>Для какой точки этот шаблон?</b>",
            reply_markup=builder.as_markup()
        )
    except TelegramBadRequest as e:
        # Игнорируем ошибку "message is not modified"
        if "message is not modified" not in str(e).lower():
            raise
    
    await state.set_state(EditChecklist.edit_shop)


@router.callback_query(EditChecklist.edit_shop)
async def set_shop(callback: types.CallbackQuery, state: FSMContext) -> None:
    if callback.data == "cancel_edit":
        await cancel_edit(callback, state)
        return
    
    data = await state.get_data()
    checklist_id = data["checklist_id"]
    
    if callback.data == "shop_all":
        shop_id = None
        shop_text = "все точки"
    else:
        shop_name = callback.data.split("_", 2)[2]
        shop_id = shop_name
        shop_text = shop_name
    
    # Проверяем, изменилась ли точка
    checklist = await db.get_checklist(checklist_id)
    shop_changed = not checklist or checklist.shop_id != shop_id
    
    await db.update_checklist(checklist_id, shop_id=shop_id)
    
    status = f"✅ Точка успешно обновлена на: {shop_text}" if shop_changed else f"ℹ️ Точка уже установлена на: {shop_text}"
    await callback.answer()
    
    # Показываем меню редактирования сразу, без промежуточного сообщения
    await show_checklist_menu_after_edit(callback, state, status_text=status)


async def save_shop(callback: types.CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    checklist_id = data["checklist_id"]
    shop_id = data.get("shop_id")
    
    # Обновляем точку (даже если она не изменилась, это безопасно)
    await db.update_checklist(checklist_id, shop_id=shop_id)
    # Показываем меню редактирования (обработка ошибок "message is not modified" уже есть в функции)
    await show_checklist_menu_after_edit(callback, state)


@router.callback_query(F.data == "edit_position")
async def start_edit_position(callback: types.CallbackQuery, state: FSMContext) -> None:
    positions = await db.get_all_positions()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🌍 Для всех должностей", callback_data="assign_all")
    for pos in positions:
        builder.button(text=f"👔 {pos}", callback_data=f"assign_pos_{pos}")
    builder.adjust(1)
    builder.button(text="❌ Отмена", callback_data="cancel_edit")
    
    await callback.message.edit_text(
        "👔 <b>Выберите должность:</b>",
        reply_markup=builder.as_markup()
    )
    await state.set_state(EditChecklist.edit_position)


@router.callback_query(EditChecklist.edit_position)
async def set_position(callback: types.CallbackQuery, state: FSMContext) -> None:
    if callback.data == "cancel_edit":
        await cancel_edit(callback, state)
        return
    
    data = await state.get_data()
    checklist_id = data["checklist_id"]
    
    target_position = None
    if callback.data != "assign_all":
        target_position = callback.data.split("_", 2)[2]
    
    await db.update_checklist(checklist_id, target_position=target_position)
    await callback.message.edit_text("✅ Должность обновлена!")
    await show_checklist_menu_after_edit(callback, state)


@router.callback_query(F.data == "edit_questions")
async def show_questions_list(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Показываем список вопросов для редактирования"""
    data = await state.get_data()
    checklist_id = data["checklist_id"]
    questions = await db.get_questions(checklist_id)
    
    if not questions:
        builder = InlineKeyboardBuilder()
        builder.button(text="➕ Добавить вопрос", callback_data="add_question_edit")
        builder.button(text="🔙 Назад", callback_data="back_to_edit_menu")
        builder.adjust(1)
        await callback.message.edit_text(
            "❓ <b>Вопросы</b>\n\nВ этом шаблоне пока нет вопросов.\n👇 Добавьте первый вопрос:",
            reply_markup=builder.as_markup()
        )
        await state.set_state(EditChecklist.edit_questions_list)
        return
    
    builder = InlineKeyboardBuilder()
    for i, q in enumerate(questions, 1):
        builder.button(
            text=f"{i}. {q.text[:30]}...", 
            callback_data=f"edit_q_{q.id}"
        )
    builder.button(text="➕ Добавить вопрос", callback_data="add_question_edit")
    builder.button(text="🔙 Назад", callback_data="back_to_edit_menu")
    builder.adjust(1)
    
    text = f"❓ <b>Вопросы шаблона</b> ({len(questions)} шт.)\n\n👇 Выберите вопрос для редактирования:"
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await state.set_state(EditChecklist.edit_questions_list)


@router.callback_query(F.data == "back_to_edit_menu")
async def back_to_edit_menu(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Возврат к меню редактирования чек-листа"""
    data = await state.get_data()
    checklist_id = data.get("checklist_id")
    
    if not checklist_id:
        await callback.answer("Ошибка: не найден ID шаблона.", show_alert=True)
        return
    
    # Создаем временный callback с правильным data
    from types import SimpleNamespace
    fake_callback = SimpleNamespace(
        message=callback.message,
        data=f"edit_ch_{checklist_id}",
        from_user=callback.from_user,
        answer=callback.answer
    )
    await show_checklist_menu(fake_callback, state)


@router.callback_query(F.data.startswith("edit_q_"))
async def edit_question_menu(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Меню редактирования конкретного вопроса"""
    question_id = int(callback.data.split("_")[2])
    question = await db.get_question(question_id)
    
    if not question:
        await callback.answer("Вопрос не найден.", show_alert=True)
        return
    
    await state.update_data(question_id=question_id)
    
    type_text = {
        "binary": "Да / Нет",
        "scale": "Оценка 1-10",
        "text": "Текст"
    }.get(question.type, question.type)
    
    photo_text = "📸 Да" if question.needs_photo else "❌ Нет"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить текст", callback_data="edit_q_text")
    builder.button(text="🔄 Изменить тип", callback_data="edit_q_type")
    builder.button(text="📸 Изменить фото", callback_data="edit_q_photo")
    builder.button(text="🗑 Удалить вопрос", callback_data="delete_question")
    builder.button(text="🔙 Назад к списку", callback_data="edit_questions")
    builder.adjust(1)
    
    text = (
        f"❓ <b>Редактирование вопроса</b>\n\n"
        f"📝 <b>Текст:</b> {question.text}\n"
        f"🔄 <b>Тип:</b> {type_text}\n"
        f"📸 <b>Фото:</b> {photo_text}\n\n"
        f"👇 Выберите действие:"
    )
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "edit_q_text")
async def start_edit_q_text(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(
        "✏️ <b>Изменение текста вопроса</b>\nВведите новый текст:",
        reply_markup=cancel_kb("cancel_edit")
    )
    await state.set_state(EditChecklist.edit_question_text)


@router.message(EditChecklist.edit_question_text)
async def save_q_text(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    question_id = data["question_id"]
    await db.update_question(question_id, text=message.text)
    await message.answer("✅ Текст вопроса обновлен!")
    
    # Возвращаемся к меню вопроса
    # Создаем новый callback query с нужным data
    from types import SimpleNamespace
    fake_callback = SimpleNamespace(
        message=message,
        data=f"edit_q_{question_id}",
        from_user=message.from_user,
        answer=lambda **kwargs: None  # Заглушка для answer
    )
    await edit_question_menu(fake_callback, state)


@router.callback_query(F.data == "edit_q_type")
async def start_edit_q_type(callback: types.CallbackQuery, state: FSMContext) -> None:
    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(kb.type_kb))
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit"))
    
    data = await state.get_data()
    question_id = data["question_id"]
    question = await db.get_question(question_id)
    
    await callback.message.edit_text(
        f"🔄 <b>Изменение типа вопроса</b>\n\nТекущий вопрос: <b>{question.text}</b>\n\nВыберите новый тип:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(EditChecklist.edit_question_type)


@router.callback_query(EditChecklist.edit_question_type)
async def save_q_type(callback: types.CallbackQuery, state: FSMContext) -> None:
    if callback.data == "cancel_edit":
        await cancel_edit(callback, state)
        return
    
    data = await state.get_data()
    question_id = data["question_id"]
    q_type = callback.data.split("_")[1]
    
    await db.update_question(question_id, type=q_type)
    await callback.message.edit_text("✅ Тип вопроса обновлен!")
    
    # Возвращаемся к меню вопроса
    # Создаем новый callback query с нужным data
    from types import SimpleNamespace
    fake_callback = SimpleNamespace(
        message=callback.message,
        data=f"edit_q_{question_id}",
        from_user=callback.from_user,
        answer=callback.answer
    )
    await edit_question_menu(fake_callback, state)


@router.callback_query(F.data == "edit_q_photo")
async def start_edit_q_photo(callback: types.CallbackQuery, state: FSMContext) -> None:
    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(kb.photo_kb))
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit"))
    
    await callback.message.edit_text(
        "📸 <b>Нужно ли фото?</b>",
        reply_markup=builder.as_markup()
    )
    await state.set_state(EditChecklist.edit_question_photo)


@router.callback_query(EditChecklist.edit_question_photo)
async def save_q_photo(callback: types.CallbackQuery, state: FSMContext) -> None:
    if callback.data == "cancel_edit":
        await cancel_edit(callback, state)
        return
    
    data = await state.get_data()
    question_id = data["question_id"]
    needs_photo = callback.data == "photo_yes"
    
    await db.update_question(question_id, needs_photo=needs_photo)
    await callback.message.edit_text("✅ Настройка фото обновлена!")
    
    # Возвращаемся к меню вопроса
    # Создаем новый callback query с нужным data
    from types import SimpleNamespace
    fake_callback = SimpleNamespace(
        message=callback.message,
        data=f"edit_q_{question_id}",
        from_user=callback.from_user,
        answer=callback.answer
    )
    await edit_question_menu(fake_callback, state)


@router.callback_query(F.data == "delete_question")
async def confirm_delete_question(callback: types.CallbackQuery, state: FSMContext) -> None:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data="confirm_delete_q")
    builder.button(text="❌ Отмена", callback_data="back_to_q_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "⚠️ <b>Удаление вопроса</b>\n\nВы уверены, что хотите удалить этот вопрос?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "confirm_delete_q")
async def delete_question_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    question_id = data["question_id"]
    checklist_id = data["checklist_id"]
    
    await db.delete_question(question_id)
    await callback.message.edit_text("✅ Вопрос удален!")
    
    # Возвращаемся к списку вопросов
    # Создаем новый callback query с нужным data
    from types import SimpleNamespace
    fake_callback = SimpleNamespace(
        message=callback.message,
        data="edit_questions",
        from_user=callback.from_user,
        answer=callback.answer
    )
    await show_questions_list(fake_callback, state)


@router.callback_query(F.data == "back_to_q_menu")
async def back_to_q_menu(callback: types.CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    question_id = data["question_id"]
    # Создаем новый callback query с нужным data
    from types import SimpleNamespace
    fake_callback = SimpleNamespace(
        message=callback.message,
        data=f"edit_q_{question_id}",
        from_user=callback.from_user,
        answer=callback.answer
    )
    await edit_question_menu(fake_callback, state)


@router.callback_query(F.data == "add_question_edit")
async def start_add_question_edit(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    from aiogram.exceptions import TelegramBadRequest
    
    try:
        await callback.message.edit_text(
            "➕ <b>Добавление вопроса</b>\nВведите текст вопроса:",
            reply_markup=cancel_kb("cancel_edit")
        )
    except TelegramBadRequest as e:
        # Если не удалось отредактировать (сообщение не изменилось), отправляем новое
        if "message is not modified" in str(e).lower():
            await callback.message.answer(
                "➕ <b>Добавление вопроса</b>\nВведите текст вопроса:",
                reply_markup=cancel_kb("cancel_edit")
            )
        else:
            raise
    await state.set_state(EditChecklist.add_new_question_text)


@router.message(EditChecklist.add_new_question_text)
async def set_new_q_text(message: types.Message, state: FSMContext) -> None:
    await state.update_data(q_text=message.text)
    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(kb.type_kb))
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit"))
    
    await message.answer(
        f"❓ Вопрос: <b>{message.text}</b>\nВыберите формат:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(EditChecklist.add_new_question_type)


@router.callback_query(EditChecklist.add_new_question_type)
async def set_new_q_type(callback: types.CallbackQuery, state: FSMContext) -> None:
    if callback.data == "cancel_edit":
        await cancel_edit(callback, state)
        return
    
    q_type = callback.data.split("_")[1]
    await state.update_data(q_type=q_type)
    
    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(kb.photo_kb))
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit"))
    
    await callback.message.edit_text(
        "📸 Нужно ли фото?",
        reply_markup=builder.as_markup()
    )
    await state.set_state(EditChecklist.add_new_question_photo)


@router.callback_query(EditChecklist.add_new_question_photo)
async def set_new_q_photo(callback: types.CallbackQuery, state: FSMContext) -> None:
    if callback.data == "cancel_edit":
        await cancel_edit(callback, state)
        return
    
    needs_photo = callback.data == "photo_yes"
    data = await state.get_data()
    checklist_id = data["checklist_id"]
    q_text = data["q_text"]
    q_type = data["q_type"]
    
    await db.add_question(checklist_id, q_text, q_type, needs_photo)
    await callback.message.edit_text("✅ Вопрос добавлен!")
    
    # Возвращаемся к списку вопросов
    # Создаем новый callback query с нужным data
    from types import SimpleNamespace
    fake_callback = SimpleNamespace(
        message=callback.message,
        data="edit_questions",
        from_user=callback.from_user,
        answer=callback.answer
    )
    await show_questions_list(fake_callback, state)


@router.callback_query(F.data == "delete_checklist")
async def confirm_delete_checklist(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Подтверждение удаления чек-листа"""
    data = await state.get_data()
    checklist_id = data.get("checklist_id")
    
    if not checklist_id:
        await callback.answer("Ошибка: не найден ID шаблона.", show_alert=True)
        return
    
    checklist = await db.get_checklist(checklist_id)
    if not checklist:
        await callback.answer("Шаблон не найден.", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data="confirm_delete_checklist")
    builder.button(text="❌ Отмена", callback_data="back_to_edit_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(
        f"⚠️ <b>Удаление шаблона</b>\n\n"
        f"Вы уверены, что хотите удалить шаблон <b>«{checklist.title}»</b>?\n\n"
        f"⚠️ <b>Внимание:</b> Если у шаблона есть отчеты, удаление будет невозможно.",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "confirm_delete_checklist")
async def delete_checklist_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Обработчик удаления чек-листа"""
    data = await state.get_data()
    checklist_id = data.get("checklist_id")
    
    if not checklist_id:
        await callback.answer("Ошибка: не найден ID шаблона.", show_alert=True)
        return
    
    success, result_message = await db.delete_checklist(checklist_id)
    
    if success:
        await callback.message.edit_text(result_message)
        await state.clear()
        # Возвращаемся к списку чек-листов
        await asyncio.sleep(1.5)
        # Используем callback.message как Message для вызова start_edit_checklist
        await start_edit_checklist(callback.message, state)
    else:
        await callback.answer(result_message, show_alert=True)
        # Возвращаемся к меню редактирования
        from types import SimpleNamespace
        fake_callback = SimpleNamespace(
            message=callback.message,
            data=f"edit_ch_{checklist_id}",
            from_user=callback.from_user,
            answer=callback.answer
        )
        await show_checklist_menu(fake_callback, state)

