from __future__ import annotations

from aiogram import F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import crud as db
from app import keyboards as kb
from app.utils import cancel_kb

from .router import router
from .states import AddWorker


@router.message(F.text == "👥 Мои сотрудники")
async def cmd_my_employees(message: types.Message) -> None:
    admin = await db.get_user(message.from_user.id)
    if not admin or admin.role != "admin":
        return

    await message.answer(
        f"👥 <b>Сотрудники точки «{admin.shop_id}»</b>\nВыберите действие:",
        reply_markup=kb.employees_manage_kb,
    )


@router.callback_query(F.data == "emp_list")
async def show_my_employees_list(callback: types.CallbackQuery) -> None:
    admin = await db.get_user(callback.from_user.id)
    if not admin:
        return

    users = await db.get_employees_by_shop(admin.shop_id)
    if not users:
        await callback.answer("Список пуст.", show_alert=True)
        return

    text_lines = [
        f"🏠 <b>{admin.shop_id}</b>",
        f"👥 Команда: {len(users)} чел.",
        "➖➖➖➖➖➖➖➖➖➖",
    ]
    i = 0
    for user in users:
        if user.role == "admin":
            continue
        i += 1
        text_lines.append(f"<b>{i}. ☕ {user.full_name}</b>")
        text_lines.append(f"   └ 💼 {user.position}")
        text_lines.append("")

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="back_to_emp_menu")
    await callback.message.edit_text("\n".join(text_lines), reply_markup=builder.as_markup())


@router.callback_query(F.data == "back_to_emp_menu")
async def back_to_emp_menu_handler(callback: types.CallbackQuery) -> None:
    admin = await db.get_user(callback.from_user.id)
    if not admin:
        return
    await callback.message.edit_text(
        f"👥 <b>Сотрудники точки «{admin.shop_id}»</b>", reply_markup=kb.employees_manage_kb
    )


@router.callback_query(F.data == "emp_del_start")
async def start_del_employee(callback: types.CallbackQuery) -> None:
    admin = await db.get_user(callback.from_user.id)
    if not admin:
        return

    users = await db.get_employees_by_shop(admin.shop_id)
    worker_list = [u for u in users if u.role == "worker"]

    if not worker_list:
        await callback.answer("Нет сотрудников для удаления.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for user in worker_list:
        builder.button(text=f"❌ {user.full_name}", callback_data=f"confirm_del_{user.id}")

    builder.button(text="🔙 Назад", callback_data="back_to_emp_menu")
    builder.adjust(1)
    await callback.message.edit_text(
        "🗑 <b>Кого уволить?</b>\nНажмите, чтобы удалить:", reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("confirm_del_"))
async def process_delete(callback: types.CallbackQuery) -> None:
    user_id = int(callback.data.split("_")[2])
    await db.delete_user(user_id)
    await callback.answer("✅ Удалено.", show_alert=True)
    await start_del_employee(callback)


@router.callback_query(F.data == "emp_add")
async def start_add_worker(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(
        "🆕 <b>Новый сотрудник</b>\n\nВведите <b>Telegram ID</b>:",
        reply_markup=cancel_kb(),
    )
    await state.set_state(AddWorker.tg_id)


@router.message(AddWorker.tg_id)
async def set_worker_id(message: types.Message, state: FSMContext) -> None:
    if not (message.text and message.text.isdigit()):
        await message.answer("⚠️ Только цифры!", reply_markup=cancel_kb())
        return

    await state.update_data(tg_id=int(message.text))
    await message.answer("👤 Введите <b>ФИО сотрудника</b>:", reply_markup=cancel_kb())
    await state.set_state(AddWorker.full_name)


@router.message(AddWorker.full_name)
async def set_worker_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(full_name=message.text)
    await message.answer(
        "💼 Введите <b>Должность</b> (например: Бариста):", reply_markup=cancel_kb()
    )
    await state.set_state(AddWorker.position)


@router.message(AddWorker.position)
async def set_worker_pos(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    position = message.text

    admin = await db.get_user(message.from_user.id)
    if not admin:
        return

    shop_id = admin.shop_id
    await db.add_user(
        tg_id=data["tg_id"],
        full_name=data["full_name"],
        role="worker",
        shop_id=shop_id,
        position=position,
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 В меню сотрудников", callback_data="back_to_emp_menu")

    await message.answer(
        f"🎉 <b>Сотрудник добавлен в «{shop_id}»!</b>\n"
        f"👤 {data['full_name']} ({position})",
        reply_markup=builder.as_markup(),
    )
    await state.clear()

