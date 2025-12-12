from __future__ import annotations

from aiogram import F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import crud as db
from app import keyboards as kb
from app.utils import cancel_kb, nav_kb

from .router import router
from .states import CreateChecklist


@router.message(F.text == "📝 Создать шаблон")
async def start_creation(message: types.Message, state: FSMContext) -> None:
    await message.answer("🛠 <b>Конструктор</b>\nВведите название шаблона:", reply_markup=cancel_kb())
    await state.set_state(CreateChecklist.title)


@router.callback_query(F.data == "back_to_title")
async def back_to_title(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(
        "🛠 <b>Шаг 1.</b>\nВведите название шаблона:", reply_markup=cancel_kb()
    )
    await state.set_state(CreateChecklist.title)


@router.message(CreateChecklist.title)
async def set_title(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    if "checklist_id" in data:
        await db.update_checklist(data["checklist_id"], title=message.text)

    await state.update_data(title=message.text)
    await show_assign_position_menu(message, state, is_edit=False)


async def show_assign_position_menu(message_or_callback, state: FSMContext, is_edit: bool = False) -> None:
    positions = await db.get_all_positions()
    data = await state.get_data()

    builder = InlineKeyboardBuilder()
    builder.button(text="🌍 Для всех должностей", callback_data="assign_all")
    for pos in positions:
        builder.button(text=f"👔 {pos}", callback_data=f"assign_pos_{pos}")
    builder.adjust(1)

    builder.row(
        types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_title"),
        types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_creation"),
    )

    text = f"📋 Название: <b>{data['title']}</b>\n👇 <b>Выберите должность:</b>"
    if is_edit:
        await message_or_callback.message.edit_text(text, reply_markup=builder.as_markup())
    else:
        await message_or_callback.answer(text, reply_markup=builder.as_markup())

    await state.set_state(CreateChecklist.assign_worker)


@router.callback_query(F.data == "back_to_assign")
async def back_to_assign(callback: types.CallbackQuery, state: FSMContext) -> None:
    await show_assign_position_menu(callback, state, is_edit=True)


@router.callback_query(CreateChecklist.assign_worker)
async def set_assignee(callback: types.CallbackQuery, state: FSMContext) -> None:
    if callback.data.startswith("back") or callback.data == "cancel_creation":
        return

    choice_type = callback.data.split("_")[1]
    target_position = None
    if choice_type == "pos":
        target_position = callback.data.split("_", 2)[2]

    data = await state.get_data()

    # Привязываем к точке админа
    admin_user = await db.get_user(callback.from_user.id)
    shop_id = admin_user.shop_id if admin_user else "Главный офис"

    if "checklist_id" in data:
        await db.update_checklist(
            data["checklist_id"],
            title=data["title"],
            target_position=target_position,
        )
        checklist_id = data["checklist_id"]
    else:
        checklist_id = await db.create_checklist(data["title"], shop_id, target_position)
        await state.update_data(checklist_id=checklist_id)

    pos_text = target_position if target_position else "Все должности"

    await callback.message.edit_text(
        f"✅ Шаблон создан.\n🎯 Для: <b>{pos_text}</b>\n\n👇 Введите текст <b>первого вопроса</b>:",
        reply_markup=nav_kb("back_to_assign"),
    )
    await state.set_state(CreateChecklist.question_text)


@router.callback_query(F.data == "back_to_q_text")
async def back_to_q_text(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(
        "✏️ <b>Исправление вопроса.</b>\nВведите текст заново:", reply_markup=cancel_kb()
    )
    await state.set_state(CreateChecklist.question_text)


@router.message(CreateChecklist.question_text)
async def set_q_text(message: types.Message, state: FSMContext) -> None:
    await state.update_data(q_text=message.text)
    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(kb.type_kb))
    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_q_text"))
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_creation"))
    await message.answer(
        f"❓ Вопрос: <b>{message.text}</b>\nВыберите формат:", reply_markup=builder.as_markup()
    )
    await state.set_state(CreateChecklist.question_type)


@router.callback_query(F.data == "back_to_q_type")
async def back_to_q_type(callback: types.CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(kb.type_kb))
    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_q_text"))
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_creation"))
    await callback.message.edit_text(
        f"❓ Вопрос: <b>{data['q_text']}</b>\nВыберите формат:", reply_markup=builder.as_markup()
    )
    await state.set_state(CreateChecklist.question_type)


@router.callback_query(CreateChecklist.question_type)
async def set_q_type(callback: types.CallbackQuery, state: FSMContext) -> None:
    if callback.data.startswith("back") or callback.data == "cancel_creation":
        return

    q_type = callback.data.split("_")[1]
    await state.update_data(q_type=q_type)

    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(kb.photo_kb))
    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_q_type"))
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_creation"))
    await callback.message.edit_text("📸 Нужно ли фото?", reply_markup=builder.as_markup())
    await state.set_state(CreateChecklist.question_photo)


@router.callback_query(CreateChecklist.question_photo)
async def set_q_photo(callback: types.CallbackQuery, state: FSMContext) -> None:
    if callback.data.startswith("back") or callback.data == "cancel_creation":
        return

    needs_photo = callback.data == "photo_yes"
    data = await state.get_data()
    await db.add_question(data["checklist_id"], data["q_text"], data["q_type"], needs_photo)
    await callback.message.edit_text("✨ Вопрос добавлен!", reply_markup=kb.after_question_kb)
    await state.set_state(CreateChecklist.next_action)


@router.callback_query(CreateChecklist.next_action)
async def next_step(callback: types.CallbackQuery, state: FSMContext) -> None:
    if callback.data == "add_more":
        await callback.message.answer("👇 Введите текст следующего вопроса:", reply_markup=cancel_kb())
        await state.set_state(CreateChecklist.question_text)
    else:
        await callback.message.edit_text("🎉 <b>Готово!</b> Шаблон сохранен.")
        await state.clear()

