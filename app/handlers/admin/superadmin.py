from __future__ import annotations

from aiogram import F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import crud as db
from app.utils import cancel_kb

from .router import router
from .states import AddManager, AddSuperAdmin


@router.message(F.text == "📊 Полный Отчет (Месяц)")
async def superadmin_monthly_report(message: types.Message) -> None:
    user = await db.get_user(message.from_user.id)
    if not user or user.role != "superadmin":
        return

    stats = await db.get_monthly_stats_by_shop()
    if not stats:
        await message.answer("📉 Отчетов в этом месяце нет.")
        return

    text_lines = ["📊 <b>Глобальный отчет по сети</b>", "➖➖➖➖➖➖➖➖➖➖"]
    for shop, avg_score, _count in stats:
        score = int(avg_score)
        icon = "🟢" if score >= 90 else "🟡" if score >= 75 else "🔴"
        text_lines.append(f"🏠 <b>{shop}</b>")
        text_lines.append(f"   📈 Эфф: <b>{icon} {score}%</b>")
        text_lines.append("")
    await message.answer("\n".join(text_lines))


@router.message(F.text == "➕ Создать Управляющего")
async def start_add_manager(message: types.Message, state: FSMContext) -> None:
    user = await db.get_user(message.from_user.id)
    if not user or user.role != "superadmin":
        return

    await message.answer(
        "👑 <b>Назначение Управляющего точкой</b>\n\nВведите <b>Telegram ID</b> человека:",
        reply_markup=cancel_kb(),
    )
    await state.set_state(AddManager.tg_id)


@router.message(AddManager.tg_id)
async def set_manager_id(message: types.Message, state: FSMContext) -> None:
    if not (message.text and message.text.isdigit()):
        await message.answer("⚠️ Только цифры!", reply_markup=cancel_kb())
        return

    await state.update_data(tg_id=int(message.text))
    await message.answer("👤 Введите <b>ФИО Управляющего</b>:", reply_markup=cancel_kb())
    await state.set_state(AddManager.full_name)


@router.message(AddManager.full_name)
async def set_manager_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(full_name=message.text)
    data = await state.get_data()
    # Создаем пользователя-админа без конкретной точки (точки храним в admin_shops)
    await db.add_user(
        tg_id=data["tg_id"],
        full_name=data["full_name"],
        role="admin",
        shop_id="Управляющий",
        position="Управляющий",
    )
    await message.answer(
        "🏠 Введите точки, которой он будет управлять:",
        reply_markup=cancel_kb(),
    )
    await state.set_state(AddManager.shop_name)


@router.message(AddManager.shop_name)
async def set_manager_shop(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    shop_name = message.text

    await db.add_admin_shop(admin_tg_id=data["tg_id"], shop_name=shop_name)
    shops = data.get("shops", [])
    shops.append(shop_name)
    await state.update_data(shops=shops)

    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить еще точку", callback_data="add_more_shops")
    builder.button(text="✅ Готово, хватит", callback_data="finish_manager")
    builder.adjust(1)

    await message.answer(
        f"✅ Точка <b>«{shop_name}»</b> добавлена.\nЕсть ли еще точки?",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(AddManager.more_shops)


@router.callback_query(AddManager.more_shops)
async def process_more_shops(callback: types.CallbackQuery, state: FSMContext) -> None:
    if callback.data == "add_more_shops":
        await callback.message.edit_text(
            "🏠 Введите название следующей точки:", reply_markup=cancel_kb()
        )
        await state.set_state(AddManager.shop_name)
    else:
        data = await state.get_data()
        shops = data.get("shops", [])
        shops_text = shops[0] if len(shops) == 1 else ", ".join(shops)
        await callback.message.edit_text(
            "✅ Управляющий назначен!\n\n"
            f"👤 {data.get('full_name', '')}\n"
            f"🏠 Точка: {shops_text}\n\n"
            "Теперь он может создавать сотрудников."
        )
        await state.clear()


@router.message(Command("add_superadmin"))
async def start_add_superadmin(message: types.Message, state: FSMContext) -> None:
    user = await db.get_user(message.from_user.id)
    if not user or user.role != "superadmin":
        return

    await message.answer(
        "🚀 <b>Добавление Superadmin</b>\n\nВведите <b>Telegram ID</b> нового администратора:",
        reply_markup=cancel_kb(),
    )
    await state.set_state(AddSuperAdmin.tg_id)


@router.message(AddSuperAdmin.tg_id)
async def set_superadmin_id(message: types.Message, state: FSMContext) -> None:
    if not (message.text and message.text.isdigit()):
        await message.answer("⚠️ Только цифры!", reply_markup=cancel_kb())
        return

    await state.update_data(tg_id=int(message.text))
    await message.answer(
        "👤 Введите <b>ФИО</b> (или имя) нового администратора:", reply_markup=cancel_kb()
    )
    await state.set_state(AddSuperAdmin.full_name)


@router.message(AddSuperAdmin.full_name)
async def set_superadmin_name(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    full_name = message.text

    # shop_id and position are required by DB but irrelevant for superadmin
    await db.add_user(
        tg_id=data["tg_id"],
        full_name=full_name,
        role="superadmin",
        shop_id="GLOBAL",
        position="Superadmin",
    )
    await message.answer(
        (
            "✅ <b>Superadmin добавлен!</b>\n\n"
            f"👤 {full_name}\n"
            f"🆔 {data['tg_id']}\n"
        )
    )
    await state.clear()
