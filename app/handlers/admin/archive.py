from __future__ import annotations

import asyncio

from aiogram import F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import crud as db
from app import keyboards as kb

from .router import router


@router.message(F.text == "🗄 Архив")
async def cmd_archive_menu(message: types.Message) -> None:
    await message.answer("🗄 <b>Архив проверок</b>", reply_markup=kb.checklists_mode_kb)


@router.callback_query(F.data == "close_archive_menu")
async def close_archive_menu(callback: types.CallbackQuery) -> None:
    await callback.message.delete()


@router.callback_query(F.data == "back_to_modes")
async def back_to_modes(callback: types.CallbackQuery) -> None:
    await callback.message.edit_text("🗄 <b>Архив проверок</b>", reply_markup=kb.checklists_mode_kb)


@router.callback_query(F.data == "show_general_stats")
async def show_general_stats(callback: types.CallbackQuery) -> None:
    stats = await db.get_monthly_stats_by_shop()
    if not stats:
        await callback.answer("Данных нет.", show_alert=True)
        return

    text_lines = ["📊 <b>Сводка эффективности (Текущий месяц)</b>", "➖➖➖➖➖➖➖➖➖➖"]
    for shop, avg_score, _count in stats:
        score = int(avg_score)
        icon = "🟢" if score >= 90 else "🟡" if score >= 75 else "🔴"
        text_lines.append(f"🏠 <b>{shop}</b>")
        text_lines.append(f"   📈 Результат: <b>{icon} {score}%</b>")
        text_lines.append("")

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="back_to_modes")
    await callback.message.edit_text("\n".join(text_lines), reply_markup=builder.as_markup())


@router.callback_query(F.data == "stats_chat")
async def mode_by_checklist(callback: types.CallbackQuery) -> None:
    today_checklists = await db.get_checklists_today()
    builder = InlineKeyboardBuilder()
    if today_checklists:
        for ch in today_checklists:
            builder.button(text=f"🔥 {ch.title}", callback_data=f"view_ch_{ch.id}")
    builder.button(text="📂 История", callback_data="stats_history")
    builder.button(text="🔙 Назад", callback_data="back_to_modes")
    builder.adjust(1)
    text = (
        "📋 <b>Активные сегодня шаблоны:</b>"
        if today_checklists
        else "📋 Сегодня отчетов еще не было."
    )
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "stats_history")
async def stats_history_list(callback: types.CallbackQuery) -> None:
    checklists = await db.get_checklists()
    builder = InlineKeyboardBuilder()
    if checklists:
        for ch in checklists:
            builder.button(text=f"📋 {ch.title}", callback_data=f"view_ch_{ch.id}")
    else:
        await callback.answer("Пусто", show_alert=True)

    builder.button(text="🔙 Назад", callback_data="stats_chat")
    builder.adjust(1)
    await callback.message.edit_text("📂 <b>Архив всех шаблонов:</b>", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("view_ch_"))
async def stats_show_reports_list(callback: types.CallbackQuery, state: FSMContext) -> None:
    checklist_id = int(callback.data.split("_")[2])
    await state.update_data(parent_menu=f"view_ch_{checklist_id}")

    reports_data = await db.get_reports_by_checklist_id(checklist_id)
    if not reports_data:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="stats_chat")
        await callback.message.edit_text("📭 Нет проверок.", reply_markup=builder.as_markup())
        return

    builder = InlineKeyboardBuilder()
    for report, user in reports_data:
        time_str = report.created_at.strftime("%d.%m %H:%M")
        builder.button(text=f"{time_str} | {user.full_name}", callback_data=f"show_rep_{report.id}")
    builder.button(text="🔙 Назад", callback_data="stats_chat")
    builder.adjust(1)
    await callback.message.edit_text("🕑 <b>Последние 10 проверок:</b>", reply_markup=builder.as_markup())


@router.callback_query(F.data == "mode_by_employee")
async def mode_by_employee(callback: types.CallbackQuery) -> None:
    users = await db.get_employees_with_reports()
    if not users:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="back_to_modes")
        await callback.message.edit_text("📭 Нет отчетов.", reply_markup=builder.as_markup())
        return

    builder = InlineKeyboardBuilder()
    for user in users:
        builder.button(text=f"👤 {user.full_name}", callback_data=f"hist_user_{user.tg_id}")
    builder.button(text="🔙 Назад", callback_data="back_to_modes")
    builder.adjust(1)
    await callback.message.edit_text("👤 <b>Выберите сотрудника:</b>", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("hist_user_"))
async def show_employee_history(callback: types.CallbackQuery, state: FSMContext) -> None:
    target_tg_id = int(callback.data.split("_")[2])
    await state.update_data(parent_menu=f"hist_user_{target_tg_id}")

    reports_data = await db.get_reports_by_user_tg_id(target_tg_id)
    if not reports_data:
        await callback.answer("Данных нет.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for report, checklist in reports_data:
        time_str = report.created_at.strftime("%d.%m %H:%M")
        builder.button(text=f"{time_str} | {checklist.title}", callback_data=f"show_rep_{report.id}")
    builder.button(text="🔙 Назад", callback_data="mode_by_employee")
    builder.adjust(1)
    await callback.message.edit_text("👤 <b>История сотрудника:</b>", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("show_rep_"))
async def show_full_report(callback: types.CallbackQuery, state: FSMContext) -> None:
    try:
        report_id = int(callback.data.split("_")[2])
    except Exception:
        return

    data = await db.get_report_details(report_id)
    if not data or not data.get("report"):
        await callback.answer("Ошибка.", show_alert=True)
        return

    report = data["report"]
    user = data["user"]
    checklist = data["checklist"]
    answers = data["answers"]

    text_lines = [
        f"📑 <b>ОТЧЕТ: {checklist.title.upper()}</b>",
        "➖➖➖➖➖➖➖➖",
        f"👤 <b>Сотрудник:</b> {user.full_name}",
        f"🏠 <b>Точка:</b> {user.shop_id}",
        f"📅 <b>Дата:</b> {report.created_at.strftime('%d.%m.%Y %H:%M')}",
        f"📊 <b>Результат:</b> {report.score_percent}%",
        "➖➖➖➖➖➖➖➖\n",
    ]

    photos_queue: list[dict[str, str]] = []
    for i, (answer, question) in enumerate(answers, 1):
        text_lines.append(f"<b>{i}. {question.text}</b>")
        ans_text = answer.answer_text if answer.answer_text else "—"
        if ans_text == "Фото":
            ans_text = "📸 <i>(См. фото)</i>"
        elif ans_text == "Да":
            ans_text = "✅ Да"
        elif ans_text == "Нет":
            ans_text = "❌ Нет"

        text_lines.append(f"   └ 💬 Ответ: {ans_text}")
        if answer.photo_id:
            text_lines.append("   └ 📎 <i>Приложено фото</i>")
            photos_queue.append(
                {"id": answer.photo_id, "caption": f"📸 <b>Вопрос №{i}:</b> {question.text}"}
            )
        text_lines.append("")

    final_text = "\n".join(text_lines)
    try:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад к списку", callback_data="cleanup_and_back")
        await callback.message.edit_text(final_text, reply_markup=builder.as_markup())

        sent_photo_ids: list[int] = []
        if photos_queue:
            await callback.message.answer("⬇️ <b>Фотографии к отчету:</b>")
            for photo in photos_queue:
                msg = await callback.message.answer_photo(
                    photo=photo["id"], caption=photo["caption"]
                )
                sent_photo_ids.append(msg.message_id)
                await asyncio.sleep(0.3)

        await state.update_data(sent_photo_ids=sent_photo_ids)
    except Exception as e:
        await callback.message.answer(f"⚠️ Ошибка: {e}")

    await callback.answer()


@router.callback_query(F.data == "cleanup_and_back")
async def cleanup_and_back(callback: types.CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    photo_ids = data.get("sent_photo_ids", [])
    parent_menu = data.get("parent_menu")

    if photo_ids:
        for mid in photo_ids:
            try:
                await callback.message.bot.delete_message(
                    chat_id=callback.message.chat.id, message_id=mid
                )
            except Exception:
                pass

        # delete the "Фотографии к отчету" message (heuristic)
        try:
            await callback.message.bot.delete_message(
                chat_id=callback.message.chat.id, message_id=photo_ids[0] - 1
            )
        except Exception:
            pass

    if not parent_menu:
        await cmd_archive_menu(callback.message)
        return

    if parent_menu.startswith("hist_user_"):
        callback.data = parent_menu
        await show_employee_history(callback, state)
    elif parent_menu.startswith("view_ch_"):
        callback.data = parent_menu
        await stats_show_reports_list(callback, state)
    else:
        await cmd_archive_menu(callback.message)

