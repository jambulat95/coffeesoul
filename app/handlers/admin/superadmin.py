from __future__ import annotations

from aiogram import F, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import crud as db
from app import keyboards as kb
from app.utils import cancel_kb

from .router import router
from .states import AddManager, AddSuperAdmin, EditAdmin


@router.message(F.text == "📊 Панель аналитики")
async def analytics_panel(message: types.Message) -> None:
    user = await db.get_user(message.from_user.id)
    if not user or user.role != "superadmin":
        return

    await message.answer(
        "📊 <b>Панель аналитики</b>\n\n"
        "Выберите раздел для просмотра статистики:",
        reply_markup=kb.analytics_panel_kb,
    )


@router.callback_query(F.data == "analytics_back")
async def analytics_back(callback: types.CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or user.role != "superadmin":
        await callback.answer("⛔️ Доступ запрещен.", show_alert=True)
        return

    try:
        await callback.message.edit_text(
            "📊 <b>Панель аналитики</b>\n\n"
            "Выберите раздел для просмотра статистики:",
            reply_markup=kb.analytics_panel_kb,
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            pass  # Игнорируем, если сообщение не изменилось
        else:
            raise
    await callback.answer()


@router.callback_query(F.data == "analytics_admins")
async def show_admins_activity(callback: types.CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or user.role != "superadmin":
        await callback.answer("⛔️ Доступ запрещен.", show_alert=True)
        return

    await callback.answer("⏳ Загрузка...")

    admins_stats = await db.get_all_admins_activity()

    if not admins_stats:
        try:
            await callback.message.edit_text(
                "👔 <b>Активность управленцев</b>\n\n"
                "📉 Управленцы не найдены.",
                reply_markup=kb.analytics_panel_kb,
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for stats in admins_stats:
        admin = stats.get("admin")
        if not admin:
            continue

        shops = stats.get("shops", [])
        shops_text = ", ".join(shops[:1]) if shops else "Нет точек"
        if len(shops) > 1:
            shops_text += f" (+{len(shops) - 1})"

        button_text = f"👤 {admin.full_name} ({shops_text})"
        builder.button(text=button_text, callback_data=f"admin_detail_{admin.tg_id}")

    builder.button(text="🔙 Назад", callback_data="analytics_back")
    builder.adjust(1)

    try:
        await callback.message.edit_text(
            "👔 <b>Активность управленцев</b>\n\n"
            "👇 Выберите управленца для просмотра детальной информации:",
            reply_markup=builder.as_markup(),
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
        else:
            raise


@router.callback_query(F.data.startswith("admin_detail_"))
async def show_admin_detail(callback: types.CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or user.role != "superadmin":
        await callback.answer("⛔️ Доступ запрещен.", show_alert=True)
        return

    await callback.answer("⏳ Загрузка...")

    admin_tg_id = int(callback.data.split("_")[2])
    stats = await db.get_admin_activity_stats(admin_tg_id)

    if not stats:
        await callback.answer("❌ Управленец не найден.", show_alert=True)
        return

    admin = stats.get("admin")
    shops = stats.get("shops", [])
    checklists_count = stats.get("checklists_count", 0)
    workers_count = stats.get("workers_count", 0)
    reports_week = stats.get("reports_count_week", 0)
    last_activity = stats.get("last_activity")

    shops_text = ", ".join(shops) if shops else "Нет точек"

    text_lines = [
        f"👤 <b>{admin.full_name}</b>",
        "➖➖➖➖➖➖➖➖➖➖",
        "",
        f"🏠 <b>Точки:</b> {shops_text}",
        f"📋 <b>Шаблонов:</b> {checklists_count}",
        f"👷 <b>Сотрудников:</b> {workers_count}",
        f"📊 <b>Отчетов (7 дней):</b> {reports_week}",
    ]

    if last_activity:
        from datetime import datetime

        now = datetime.now()
        delta = now - last_activity
        if delta.days == 0:
            hours = delta.seconds // 3600
            if hours == 0:
                minutes = delta.seconds // 60
                last_text = f"{minutes} мин назад" if minutes > 0 else "только что"
            else:
                last_text = f"{hours} ч назад"
        else:
            last_text = f"{delta.days} дн назад"
        text_lines.append(f"🕐 <b>Последняя активность:</b> {last_text}")
    else:
        text_lines.append("🕐 <b>Последняя активность:</b> нет данных")

    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Шаблоны", callback_data=f"admin_checklists_{admin_tg_id}")
    builder.button(text="👷 Сотрудники", callback_data=f"admin_workers_{admin_tg_id}")
    builder.button(text="🔙 Назад к списку", callback_data="analytics_admins")
    builder.adjust(1)

    try:
        await callback.message.edit_text(
            "\n".join(text_lines), reply_markup=builder.as_markup()
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
        else:
            raise


@router.callback_query(F.data.startswith("admin_checklists_"))
async def show_admin_checklists(callback: types.CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or user.role != "superadmin":
        await callback.answer("⛔️ Доступ запрещен.", show_alert=True)
        return

    await callback.answer("⏳ Загрузка...")

    admin_tg_id = int(callback.data.split("_")[2])
    admin = await db.get_user(admin_tg_id)
    if not admin:
        await callback.answer("❌ Управленец не найден.", show_alert=True)
        return

    checklists_stats = await db.get_admin_checklists(admin_tg_id)

    if not checklists_stats:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data=f"admin_detail_{admin_tg_id}")
        try:
            await callback.message.edit_text(
                f"📋 <b>Шаблоны управленца: {admin.full_name}</b>\n\n"
                "📉 Шаблоны не найдены.",
                reply_markup=builder.as_markup(),
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                await callback.answer()
        return

    text_lines = [f"📋 <b>Шаблоны управленца: {admin.full_name}</b>", "➖➖➖➖➖➖➖➖➖➖"]

    for stats in checklists_stats:
        checklist = stats.get("checklist")
        if not checklist:
            continue

        questions_count = stats.get("questions_count", 0)
        reports_count = stats.get("reports_count", 0)
        avg_score = stats.get("avg_score", 0)
        last_use = stats.get("last_use")

        score_icon = "🟢" if avg_score >= 90 else "🟡" if avg_score >= 75 else "🔴"

        text_lines.append(f"\n📝 <b>{checklist.title}</b>")
        text_lines.append(f"   🏠 Точка: {checklist.shop_id or 'Все точки'}")
        text_lines.append(f"   ❓ Вопросов: {questions_count}")
        text_lines.append(f"   📊 Использований: {reports_count}")
        if reports_count > 0:
            text_lines.append(f"   {score_icon} Средний балл: {avg_score}%")

        if last_use:
            from datetime import datetime

            now = datetime.now()
            delta = now - last_use
            if delta.days == 0:
                hours = delta.seconds // 3600
                if hours == 0:
                    minutes = delta.seconds // 60
                    last_text = f"{minutes} мин назад" if minutes > 0 else "только что"
                else:
                    last_text = f"{hours} ч назад"
            else:
                last_text = f"{delta.days} дн назад"
            text_lines.append(f"   🕐 Последнее использование: {last_text}")
        else:
            text_lines.append("   🕐 Последнее использование: не использовался")

    text_lines.append("\n" + "➖➖➖➖➖➖➖➖➖➖")

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data=f"admin_detail_{admin_tg_id}")

    full_text = "\n".join(text_lines)
    try:
        if len(full_text) > 4000:
            first_part = "\n".join(text_lines[:12]) + "\n\n<i>... (продолжение в следующем сообщении)</i>"
            await callback.message.edit_text(first_part, reply_markup=builder.as_markup())
            remaining_lines = text_lines[12:]
            if remaining_lines:
                remaining_text = "\n".join(remaining_lines)
                await callback.message.answer(remaining_text)
        else:
            await callback.message.edit_text(full_text, reply_markup=builder.as_markup())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
        else:
            raise


@router.callback_query(F.data.startswith("admin_workers_"))
async def show_admin_workers(callback: types.CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or user.role != "superadmin":
        await callback.answer("⛔️ Доступ запрещен.", show_alert=True)
        return

    await callback.answer("⏳ Загрузка...")

    admin_tg_id = int(callback.data.split("_")[2])
    admin = await db.get_user(admin_tg_id)
    if not admin:
        await callback.answer("❌ Управленец не найден.", show_alert=True)
        return

    workers_stats = await db.get_admin_workers(admin_tg_id)

    if not workers_stats:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data=f"admin_detail_{admin_tg_id}")
        try:
            await callback.message.edit_text(
                f"👷 <b>Сотрудники управленца: {admin.full_name}</b>\n\n"
                "📉 Сотрудники не найдены.",
                reply_markup=builder.as_markup(),
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                await callback.answer()
        return

    # Сортируем по активности
    workers_stats.sort(key=lambda x: x.get("total_reports", 0), reverse=True)

    text_lines = [f"👷 <b>Сотрудники управленца: {admin.full_name}</b>", "➖➖➖➖➖➖➖➖➖➖"]

    for stats in workers_stats:
        worker = stats.get("worker")
        if not worker:
            continue

        total_reports = stats.get("total_reports", 0)
        avg_score = stats.get("avg_score", 0)
        reports_week = stats.get("reports_count_week", 0)
        last_activity = stats.get("last_activity")

        score_icon = "🟢" if avg_score >= 90 else "🟡" if avg_score >= 75 else "🔴"

        text_lines.append(f"\n👤 <b>{worker.full_name}</b>")
        text_lines.append(f"   🏠 {worker.shop_id or 'Без точки'}")
        text_lines.append(f"   💼 {worker.position}")
        text_lines.append(f"   📊 Всего отчетов: {total_reports}")
        text_lines.append(f"   {score_icon} Средний балл: {avg_score}%")
        text_lines.append(f"   📈 Отчетов (7 дней): {reports_week}")

        if last_activity:
            from datetime import datetime

            now = datetime.now()
            delta = now - last_activity
            if delta.days == 0:
                hours = delta.seconds // 3600
                if hours == 0:
                    minutes = delta.seconds // 60
                    last_text = f"{minutes} мин назад" if minutes > 0 else "только что"
                else:
                    last_text = f"{hours} ч назад"
            else:
                last_text = f"{delta.days} дн назад"
            text_lines.append(f"   🕐 Последняя активность: {last_text}")
        else:
            text_lines.append("   🕐 Последняя активность: нет данных")

    text_lines.append("\n" + "➖➖➖➖➖➖➖➖➖➖")

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data=f"admin_detail_{admin_tg_id}")

    full_text = "\n".join(text_lines)
    try:
        if len(full_text) > 4000:
            first_part = "\n".join(text_lines[:15]) + "\n\n<i>... (продолжение в следующем сообщении)</i>"
            await callback.message.edit_text(first_part, reply_markup=builder.as_markup())
            remaining_lines = text_lines[15:]
            if remaining_lines:
                remaining_text = "\n".join(remaining_lines)
                await callback.message.answer(remaining_text)
        else:
            await callback.message.edit_text(full_text, reply_markup=builder.as_markup())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
        else:
            raise


@router.callback_query(F.data == "analytics_workers")
async def show_workers_activity(callback: types.CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or user.role != "superadmin":
        await callback.answer("⛔️ Доступ запрещен.", show_alert=True)
        return

    await callback.answer("⏳ Загрузка...")

    shops = await db.get_workers_shops()

    if not shops:
        try:
            await callback.message.edit_text(
                "👷 <b>Активность сотрудников</b>\n\n"
                "📉 Точки с сотрудниками не найдены.",
                reply_markup=kb.analytics_panel_kb,
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for shop in shops:
        # Подсчитываем количество сотрудников для этой точки
        workers_count = 0
        if shop == "Без точки":
            workers_stats, total = await db.get_workers_by_shop(None, offset=0, limit=1)
            workers_count = total
        else:
            workers_stats, total = await db.get_workers_by_shop(shop, offset=0, limit=1)
            workers_count = total
        
        button_text = f"🏠 {shop} ({workers_count})"
        # Используем shop как callback_data, но для "Без точки" используем специальное значение
        shop_callback = "worker_shop_none" if shop == "Без точки" else f"worker_shop_{shop}"
        builder.button(text=button_text, callback_data=shop_callback)

    builder.button(text="🔙 Назад", callback_data="analytics_back")
    builder.adjust(1)

    try:
        await callback.message.edit_text(
            "👷 <b>Активность сотрудников</b>\n\n"
            "👇 Выберите точку для просмотра сотрудников:",
            reply_markup=builder.as_markup(),
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
        else:
            raise


@router.callback_query(F.data.startswith("worker_shop_"))
async def show_workers_by_shop(callback: types.CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or user.role != "superadmin":
        await callback.answer("⛔️ Доступ запрещен.", show_alert=True)
        return

    await callback.answer("⏳ Загрузка...")

    callback_data = callback.data
    offset = 0
    base_shop_callback = callback_data
    
    # Проверяем, есть ли offset в callback_data (для пагинации)
    if "_offset_" in callback_data:
        parts = callback_data.split("_offset_")
        base_shop_callback = parts[0]
        offset = int(parts[1])
    
    if base_shop_callback == "worker_shop_none":
        shop_id = None
        shop_name = "Без точки"
    else:
        shop_id = base_shop_callback.replace("worker_shop_", "", 1)
        shop_name = shop_id

    workers_stats, total_count = await db.get_workers_by_shop(shop_id, offset=offset, limit=5)

    if not workers_stats:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад к точкам", callback_data="analytics_workers")
        try:
            await callback.message.edit_text(
                f"👷 <b>Сотрудники точки: {shop_name}</b>\n\n"
                "📉 Сотрудники не найдены.",
                reply_markup=builder.as_markup(),
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                await callback.answer()
        return

    text_lines = [f"👷 <b>Сотрудники точки: {shop_name}</b>", "➖➖➖➖➖➖➖➖➖➖"]

    for stats in workers_stats:
        worker = stats.get("worker")
        if not worker:
            continue

        total_reports = stats.get("total_reports", 0)
        avg_score = stats.get("avg_score", 0)
        reports_week = stats.get("reports_count_week", 0)
        last_activity = stats.get("last_activity")

        score_icon = "🟢" if avg_score >= 90 else "🟡" if avg_score >= 75 else "🔴"

        text_lines.append(f"\n👤 <b>{worker.full_name}</b>")
        text_lines.append(f"   💼 {worker.position}")
        text_lines.append(f"   📊 Всего отчетов: {total_reports}")
        text_lines.append(f"   {score_icon} Средний балл: {avg_score}%")
        text_lines.append(f"   📈 Отчетов (7 дней): {reports_week}")

        if last_activity:
            from datetime import datetime

            now = datetime.now()
            delta = now - last_activity
            if delta.days == 0:
                hours = delta.seconds // 3600
                if hours == 0:
                    minutes = delta.seconds // 60
                    last_text = f"{minutes} мин назад" if minutes > 0 else "только что"
                else:
                    last_text = f"{hours} ч назад"
            else:
                last_text = f"{delta.days} дн назад"
            text_lines.append(f"   🕐 Последняя активность: {last_text}")
        else:
            text_lines.append("   🕐 Последняя активность: нет данных")

    text_lines.append("\n" + "➖➖➖➖➖➖➖➖➖➖")
    
    if offset + len(workers_stats) < total_count:
        text_lines.append(f"\n<i>Показано {offset + 1}-{offset + len(workers_stats)} из {total_count}</i>")
    else:
        text_lines.append(f"\n<i>Показано {offset + 1}-{total_count} из {total_count}</i>")

    builder = InlineKeyboardBuilder()
    
    # Кнопка "Далее" если есть еще сотрудники
    if offset + len(workers_stats) < total_count:
        next_offset = offset + 5
        next_callback = f"{base_shop_callback}_offset_{next_offset}"
        builder.button(text="➡️ Далее", callback_data=next_callback)
    
    # Кнопка "Назад" если не на первой странице
    if offset > 0:
        prev_offset = max(0, offset - 5)
        if prev_offset == 0:
            prev_callback = base_shop_callback
        else:
            prev_callback = f"{base_shop_callback}_offset_{prev_offset}"
        builder.button(text="⬅️ Назад", callback_data=prev_callback)
    
    builder.button(text="🔙 Назад к точкам", callback_data="analytics_workers")
    builder.adjust(2, 1)

    full_text = "\n".join(text_lines)
    try:
        if len(full_text) > 4000:
            first_part = "\n".join(text_lines[:15]) + "\n\n<i>... (продолжение в следующем сообщении)</i>"
            await callback.message.edit_text(first_part, reply_markup=builder.as_markup())
            remaining_lines = text_lines[15:]
            if remaining_lines:
                remaining_text = "\n".join(remaining_lines)
                await callback.message.answer(remaining_text)
        else:
            await callback.message.edit_text(full_text, reply_markup=builder.as_markup())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
        else:
            raise


@router.callback_query(F.data == "analytics_checklists")
async def show_checklists_stats(callback: types.CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or user.role != "superadmin":
        await callback.answer("⛔️ Доступ запрещен.", show_alert=True)
        return

    await callback.answer("⏳ Загрузка...")

    shops = await db.get_checklists_shops()

    if not shops:
        try:
            await callback.message.edit_text(
                "📋 <b>Все чек-листы</b>\n\n"
                "📉 Точки с чек-листами не найдены.",
                reply_markup=kb.analytics_panel_kb,
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for shop in shops:
        # Подсчитываем количество чек-листов для этой точки
        checklists_count = 0
        if shop == "Все точки":
            checklists_count = len(await db.get_checklists_by_shop(None))
        else:
            checklists_count = len(await db.get_checklists_by_shop(shop))
        
        button_text = f"🏠 {shop} ({checklists_count})"
        # Используем shop как callback_data, но для "Все точки" используем специальное значение
        shop_callback = "shop_all" if shop == "Все точки" else f"shop_{shop}"
        builder.button(text=button_text, callback_data=shop_callback)

    builder.button(text="🔙 Назад", callback_data="analytics_back")
    builder.adjust(1)

    try:
        await callback.message.edit_text(
            "📋 <b>Все чек-листы</b>\n\n"
            "👇 Выберите точку для просмотра чек-листов:",
            reply_markup=builder.as_markup(),
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
        else:
            raise


@router.callback_query(F.data.startswith("shop_"))
async def show_checklists_by_shop(callback: types.CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or user.role != "superadmin":
        await callback.answer("⛔️ Доступ запрещен.", show_alert=True)
        return

    await callback.answer("⏳ Загрузка...")

    shop_callback = callback.data
    if shop_callback == "shop_all":
        shop_id = None
        shop_name = "Все точки"
    else:
        shop_id = shop_callback.replace("shop_", "", 1)
        shop_name = shop_id

    checklists_stats = await db.get_checklists_by_shop(shop_id)

    if not checklists_stats:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="analytics_checklists")
        try:
            await callback.message.edit_text(
                f"📋 <b>Чек-листы точки: {shop_name}</b>\n\n"
                "📉 Чек-листы не найдены.",
                reply_markup=builder.as_markup(),
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                await callback.answer()
        return

    # Сортируем по количеству использований (самые популярные сверху)
    checklists_stats.sort(key=lambda x: x.get("reports_count", 0), reverse=True)

    text_lines = [f"📋 <b>Чек-листы точки: {shop_name}</b>", "➖➖➖➖➖➖➖➖➖➖"]

    for stats in checklists_stats:
        checklist = stats.get("checklist")
        if not checklist:
            continue

        questions_count = stats.get("questions_count", 0)
        reports_count = stats.get("reports_count", 0)
        avg_score = stats.get("avg_score", 0)
        last_use = stats.get("last_use")
        creator = stats.get("creator", "Неизвестно")

        score_icon = "🟢" if avg_score >= 90 else "🟡" if avg_score >= 75 else "🔴"

        text_lines.append(f"\n📝 <b>{checklist.title}</b>")
        if checklist.target_position:
            text_lines.append(f"   💼 Для: {checklist.target_position}")
        text_lines.append(f"   👤 Создатель: {creator}")
        text_lines.append(f"   ❓ Вопросов: {questions_count}")
        text_lines.append(f"   📊 Использований: {reports_count}")
        if reports_count > 0:
            text_lines.append(f"   {score_icon} Средний балл: {avg_score}%")

        if last_use:
            from datetime import datetime

            now = datetime.now()
            delta = now - last_use
            if delta.days == 0:
                hours = delta.seconds // 3600
                if hours == 0:
                    minutes = delta.seconds // 60
                    last_text = f"{minutes} мин назад" if minutes > 0 else "только что"
                else:
                    last_text = f"{hours} ч назад"
            else:
                last_text = f"{delta.days} дн назад"
            text_lines.append(f"   🕐 Последнее использование: {last_text}")
        else:
            text_lines.append("   🕐 Последнее использование: не использовался")

    text_lines.append("\n" + "➖➖➖➖➖➖➖➖➖➖")

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад к точкам", callback_data="analytics_checklists")

    full_text = "\n".join(text_lines)
    try:
        if len(full_text) > 4000:
            first_part = "\n".join(text_lines[:12]) + "\n\n<i>... (продолжение в следующем сообщении)</i>"
            await callback.message.edit_text(first_part, reply_markup=builder.as_markup())
            remaining_lines = text_lines[12:]
            if remaining_lines:
                remaining_text = "\n".join(remaining_lines)
                await callback.message.answer(remaining_text)
        else:
            await callback.message.edit_text(full_text, reply_markup=builder.as_markup())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
        else:
            raise


@router.callback_query(F.data == "analytics_overview")
async def show_network_overview(callback: types.CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or user.role != "superadmin":
        await callback.answer("⛔️ Доступ запрещен.", show_alert=True)
        return

    await callback.answer("⏳ Загрузка...")

    overview = await db.get_network_overview_stats()

    text_lines = [
        "📈 <b>Общая статистика сети</b>",
        "➖➖➖➖➖➖➖➖➖➖",
        "",
        "👥 <b>Пользователи:</b>",
        f"   👔 Управленцев: {overview.get('admins_count', 0)}",
        f"   👷 Сотрудников: {overview.get('workers_count', 0)}",
        "",
        "📋 <b>Контент:</b>",
        f"   📝 Чек-листов: {overview.get('checklists_count', 0)}",
        f"   📊 Всего отчетов: {overview.get('reports_count', 0)}",
        "",
        "📈 <b>Активность:</b>",
        f"   📊 Отчетов сегодня: {overview.get('reports_today', 0)}",
        f"   📊 Отчетов за 7 дней: {overview.get('reports_week', 0)}",
        "",
        "🎯 <b>Показатели:</b>",
    ]

    avg_score = overview.get("avg_score", 0)
    score_icon = "🟢" if avg_score >= 90 else "🟡" if avg_score >= 75 else "🔴"
    text_lines.append(f"   {score_icon} Средний балл: {avg_score}%")

    shops_count = overview.get("shops_count", 0)
    text_lines.append(f"   🏠 Уникальных точек: {shops_count}")

    text_lines.append("\n" + "➖➖➖➖➖➖➖➖➖➖")

    try:
        await callback.message.edit_text("\n".join(text_lines), reply_markup=kb.analytics_panel_kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
        else:
            raise


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


@router.message(F.text == "👥 Управление админами")
async def manage_admins_menu(message: types.Message) -> None:
    user = await db.get_user(message.from_user.id)
    if not user or user.role != "superadmin":
        return

    admins = await db.get_all_admins()
    if not admins:
        await message.answer("👥 <b>Список администраторов пуст.</b>")
        return

    builder = InlineKeyboardBuilder()
    for admin in admins:
        # Check roles to ensure we don't list superadmins if get_all_admins includes them (it shouldn't based on query)
        if admin.role == "superadmin":
            continue
            
        shops = await db.get_admin_shops(admin.tg_id)
        shops_text = ", ".join(shops[:1]) if shops else "Нет точек"
        if len(shops) > 1:
            shops_text += f" (+{len(shops) - 1})"
        
        builder.button(
            text=f"👤 {admin.full_name} ({shops_text})",
            callback_data=f"manage_admin_{admin.id}"
        )
    builder.adjust(1)
    
    await message.answer(
        "👥 <b>Управление администраторами</b>\n\n"
        "👇 Выберите администратора для управления:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("manage_admin_"))
async def show_admin_manage_menu(callback: types.CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or user.role != "superadmin":
        await callback.answer("⛔️ Доступ запрещен.", show_alert=True)
        return

    await callback.answer("⏳ Загрузка...")

    admin_id = int(callback.data.split("_")[2])
    admin = await db.get_user_by_pk(admin_id)
    
    if not admin or admin.role != "admin":
        await callback.answer("❌ Администратор не найден.", show_alert=True)
        return

    shops = await db.get_admin_shops(admin.tg_id)
    shops_text = ", ".join(shops) if shops else "Нет точек"

    text_lines = [
        f"👤 <b>{admin.full_name}</b>",
        "➖➖➖➖➖➖➖➖➖➖",
        "",
        f"🆔 <b>Telegram ID:</b> {admin.tg_id}",
        f"🏠 <b>Точки:</b> {shops_text}",
    ]

    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Редактировать", callback_data=f"edit_admin_{admin_id}")
    builder.button(text="❌ Удалить", callback_data=f"del_admin_{admin_id}")
    builder.button(text="🔙 Назад к списку", callback_data="back_to_admins_list")
    builder.adjust(1)

    try:
        await callback.message.edit_text(
            "\n".join(text_lines),
            reply_markup=builder.as_markup()
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
        else:
            raise


@router.callback_query(F.data == "back_to_admins_list")
async def back_to_admins_list(callback: types.CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or user.role != "superadmin":
        await callback.answer("⛔️ Доступ запрещен.", show_alert=True)
        return

    admins = await db.get_all_admins()
    if not admins:
        try:
            await callback.message.edit_text("👥 <b>Список администраторов пуст.</b>")
        except TelegramBadRequest:
            pass
        return

    builder = InlineKeyboardBuilder()
    for admin in admins:
        if admin.role == "superadmin":
            continue
            
        shops = await db.get_admin_shops(admin.tg_id)
        shops_text = ", ".join(shops[:1]) if shops else "Нет точек"
        if len(shops) > 1:
            shops_text += f" (+{len(shops) - 1})"
        
        builder.button(
            text=f"👤 {admin.full_name} ({shops_text})",
            callback_data=f"manage_admin_{admin.id}"
        )
    builder.adjust(1)
    
    try:
        await callback.message.edit_text(
            "👥 <b>Управление администраторами</b>\n\n"
            "👇 Выберите администратора для управления:",
            reply_markup=builder.as_markup()
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
        else:
            raise


@router.callback_query(F.data.regexp(r"^edit_admin_\d+$"))
async def start_edit_admin(callback: types.CallbackQuery, state: FSMContext) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or user.role != "superadmin":
        await callback.answer("⛔️ Доступ запрещен.", show_alert=True)
        return

    # callback_data format: "edit_admin_{admin_id}"
    admin_id = int(callback.data.split("_")[2])
    admin = await db.get_user_by_pk(admin_id)
    
    if not admin or admin.role != "admin":
        await callback.answer("❌ Администратор не найден.", show_alert=True)
        return

    await state.update_data(admin_id=admin_id, current_tg_id=admin.tg_id)

    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить имя", callback_data=f"edit_admin_name_{admin_id}")
    builder.button(text="🆔 Изменить ID", callback_data=f"edit_admin_tg_id_{admin_id}")
    builder.button(text="🔙 Назад", callback_data=f"manage_admin_{admin_id}")
    builder.adjust(1)

    try:
        await callback.message.edit_text(
            f"✏️ <b>Редактирование администратора</b>\n\n"
            f"👤 <b>Имя:</b> {admin.full_name}\n"
            f"🆔 <b>ID:</b> {admin.tg_id}\n\n"
            "Выберите, что хотите изменить:",
            reply_markup=builder.as_markup()
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
        else:
            raise


@router.callback_query(F.data.startswith("edit_admin_name_"))
async def start_edit_admin_name(callback: types.CallbackQuery, state: FSMContext) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or user.role != "superadmin":
        await callback.answer("⛔️ Доступ запрещен.", show_alert=True)
        return

    # callback_data format: "edit_admin_name_{admin_id}"
    admin_id = int(callback.data.split("_")[3])
    await state.update_data(admin_id=admin_id)
    await state.set_state(EditAdmin.edit_name)

    try:
        await callback.message.edit_text(
            "✏️ <b>Редактирование имени</b>\n\n"
            "Введите новое имя администратора:",
            reply_markup=cancel_kb()
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
        else:
            raise
    await callback.answer()


@router.message(EditAdmin.edit_name)
async def save_admin_name(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    admin_id = data.get("admin_id")
    
    if not admin_id:
        await message.answer("❌ Ошибка. Попробуйте снова.")
        await state.clear()
        return

    success = await db.update_user(admin_id, full_name=message.text)
    
    if success:
        admin = await db.get_user_by_pk(admin_id)
        await message.answer(
            f"✅ Имя администратора успешно изменено на <b>{admin.full_name}</b>."
        )
    else:
        await message.answer("❌ Ошибка при обновлении имени.")
    
    await state.clear()


@router.callback_query(F.data.startswith("edit_admin_tg_id_"))
async def start_edit_admin_tg_id(callback: types.CallbackQuery, state: FSMContext) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or user.role != "superadmin":
        await callback.answer("⛔️ Доступ запрещен.", show_alert=True)
        return

    # callback_data format: "edit_admin_tg_id_{admin_id}"
    # split("_") gives: ["edit", "admin", "tg", "id", "{admin_id}"]
    admin_id = int(callback.data.split("_")[4])
    await state.update_data(admin_id=admin_id)
    await state.set_state(EditAdmin.edit_tg_id)

    try:
        await callback.message.edit_text(
            "🆔 <b>Редактирование Telegram ID</b>\n\n"
            "Введите новый Telegram ID (только цифры):",
            reply_markup=cancel_kb()
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
        else:
            raise
    await callback.answer()


@router.message(EditAdmin.edit_tg_id)
async def save_admin_tg_id(message: types.Message, state: FSMContext) -> None:
    if not (message.text and message.text.isdigit()):
        await message.answer("⚠️ Только цифры! Введите Telegram ID:", reply_markup=cancel_kb())
        return

    data = await state.get_data()
    admin_id = data.get("admin_id")
    new_tg_id = int(message.text)
    
    if not admin_id:
        await message.answer("❌ Ошибка. Попробуйте снова.")
        await state.clear()
        return

    success = await db.update_user(admin_id, tg_id=new_tg_id)
    
    if success:
        await message.answer(
            f"✅ Telegram ID администратора успешно изменен на <b>{new_tg_id}</b>."
        )
    else:
        await message.answer("❌ Ошибка при обновлении ID. Возможно, этот ID уже занят другим пользователем.")
    
    await state.clear()


@router.callback_query(F.data.startswith("del_admin_"))
async def confirm_delete_admin(callback: types.CallbackQuery) -> None:
    # Double check permissions
    user = await db.get_user(callback.from_user.id)
    if not user or user.role != "superadmin":
        await callback.answer("⛔️ Доступ запрещен.", show_alert=True)
        return

    admin_id = int(callback.data.split("_")[2])
    
    # Prevent deleting self if somehow listed (shouldn't happen)
    target_user = await db.get_user_by_pk(admin_id)
    if target_user and target_user.tg_id == callback.from_user.id:
        await callback.answer("Нельзя удалить самого себя!", show_alert=True)
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"confirm_del_admin_{admin_id}")
    builder.button(text="❌ Отмена", callback_data=f"manage_admin_{admin_id}")
    builder.adjust(1)

    try:
        await callback.message.edit_text(
            f"⚠️ <b>Подтверждение удаления</b>\n\n"
            f"Вы уверены, что хотите удалить администратора <b>{target_user.full_name}</b>?\n\n"
            "⚠️ Это действие также удалит привязку к точкам, но не удалит сами точки.",
            reply_markup=builder.as_markup()
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
        else:
            raise
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del_admin_"))
async def delete_admin_handler(callback: types.CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or user.role != "superadmin":
        await callback.answer("⛔️ Доступ запрещен.", show_alert=True)
        return

    admin_id = int(callback.data.split("_")[3])
    
    deleted = await db.delete_user(admin_id)
    
    if deleted:
        await callback.answer("✅ Администратор удален.", show_alert=True)
        # Возвращаемся к списку
        await back_to_admins_list(callback)
    else:
        await callback.answer("❌ Ошибка при удалении.", show_alert=True)


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
