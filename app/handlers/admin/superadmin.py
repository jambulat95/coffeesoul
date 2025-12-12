from __future__ import annotations

from aiogram import F, types
from aiogram.fsm.context import FSMContext

from app import crud as db
from app.utils import cancel_kb

from .router import router
from .states import AddManager


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
    await message.answer(
        "🏠 Введите <b>Название точки</b> (Локации), которой он будет управлять:",
        reply_markup=cancel_kb(),
    )
    await state.set_state(AddManager.shop_name)


@router.message(AddManager.shop_name)
async def set_manager_shop(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    shop_name = message.text

    await db.add_user(
        tg_id=data["tg_id"],
        full_name=data["full_name"],
        role="admin",
        shop_id=shop_name,
        position="Управляющий",
    )
    await message.answer(
        (
            "✅ <b>Управляющий назначен!</b>\n\n"
            f"👤 {data['full_name']}\n"
            f"🏠 Точка: <b>{shop_name}</b>\n\n"
            "Теперь он может создавать сотрудников."
        )
    )
    await state.clear()

