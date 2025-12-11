import os
import asyncio
from aiogram import Router, F, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
import keyboards as kb

router = Router()

# --- МАШИНЫ СОСТОЯНИЙ ---

# 1. Создание чек-листа (Убрали select_days)
class CreateChecklist(StatesGroup):
    title = State()
    assign_worker = State() # Выбор должности
    question_text = State()
    question_type = State()
    question_photo = State()
    next_action = State()

# 2. Добавление СОТРУДНИКА (Для Управляющего)
class AddWorker(StatesGroup):
    tg_id = State()
    full_name = State()
    position = State()

# 3. Добавление УПРАВЛЯЮЩЕГО (Для Супер-Админа)
class AddManager(StatesGroup):
    tg_id = State()
    full_name = State()
    shop_name = State()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def cancel_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_creation")
    return builder.as_markup()

def nav_kb(back_callback: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data=back_callback)
    builder.button(text="❌ Отмена", callback_data="cancel_creation")
    builder.adjust(1)
    return builder.as_markup()

@router.callback_query(F.data == "cancel_creation")
async def cancel_process(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.")


# ==========================================================
# 👑 БЛОК СУПЕР-АДМИНА (Гендиректор)
# ==========================================================

@router.message(F.text == "📊 Полный Отчет (Месяц)")
async def superadmin_monthly_report(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if user.role != 'superadmin': return

    stats = await db.get_monthly_stats_by_shop()
    if not stats:
        await message.answer("📉 Отчетов в этом месяце нет.")
        return

    text_lines = ["📊 <b>Глобальный отчет по сети</b>", "➖➖➖➖➖➖➖➖➖➖"]
    for shop, avg_score, count in stats:
        score = int(avg_score)
        icon = "🟢" if score >= 90 else "🟡" if score >= 75 else "🔴"
        text_lines.append(f"🏠 <b>{shop}</b>")
        text_lines.append(f"   📈 Эфф: <b>{icon} {score}%</b>")
        text_lines.append("")
    await message.answer("\n".join(text_lines))

@router.message(F.text == "➕ Создать Управляющего")
async def start_add_manager(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if user.role != 'superadmin': return

    await message.answer(
        "👑 <b>Назначение Управляющего точкой</b>\n\nВведите <b>Telegram ID</b> человека:",
        reply_markup=cancel_kb()
    )
    await state.set_state(AddManager.tg_id)

@router.message(AddManager.tg_id)
async def set_manager_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Только цифры!", reply_markup=cancel_kb())
        return
    await state.update_data(tg_id=int(message.text))
    await message.answer("👤 Введите <b>ФИО Управляющего</b>:", reply_markup=cancel_kb())
    await state.set_state(AddManager.full_name)

@router.message(AddManager.full_name)
async def set_manager_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer("🏠 Введите <b>Название точки</b> (Локации), которой он будет управлять:", reply_markup=cancel_kb())
    await state.set_state(AddManager.shop_name)

@router.message(AddManager.shop_name)
async def set_manager_shop(message: types.Message, state: FSMContext):
    data = await state.get_data()
    shop_name = message.text
    await db.add_user(
        tg_id=data['tg_id'],
        full_name=data['full_name'],
        role='admin',
        shop_id=shop_name,
        position="Управляющий"
    )
    await message.answer(
        f"✅ <b>Управляющий назначен!</b>\n\n👤 {data['full_name']}\n🏠 Точка: <b>{shop_name}</b>\n\nТеперь он может создавать сотрудников."
    )
    await state.clear()


# ==========================================================
# ☕ БЛОК УПРАВЛЯЮЩЕГО (Админ точки)
# ==========================================================

@router.message(F.text == "👥 Мои сотрудники")
async def cmd_my_employees(message: types.Message):
    admin = await db.get_user(message.from_user.id)
    if not admin or admin.role != 'admin': return

    await message.answer(
        f"👥 <b>Сотрудники точки «{admin.shop_id}»</b>\nВыберите действие:", 
        reply_markup=kb.employees_manage_kb
    )

@router.callback_query(F.data == "emp_list")
async def show_my_employees_list(callback: types.CallbackQuery):
    admin = await db.get_user(callback.from_user.id)
    users = await db.get_employees_by_shop(admin.shop_id)
    
    if not users:
        await callback.answer("Список пуст.", show_alert=True)
        return

    text_lines = [f"🏠 <b>{admin.shop_id}</b>", f"👥 Команда: {len(users)} чел.", "➖➖➖➖➖➖➖➖➖➖"]
    for i, user in enumerate(users, 1):
        if user.role == 'admin': continue 
        text_lines.append(f"<b>{i}. ☕ {user.full_name}</b>")
        text_lines.append(f"   └ 💼 {user.position}")
        text_lines.append("")
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="back_to_emp_menu")
    await callback.message.edit_text("\n".join(text_lines), reply_markup=builder.as_markup())

@router.callback_query(F.data == "back_to_emp_menu")
async def back_to_emp_menu_handler(callback: types.CallbackQuery):
    admin = await db.get_user(callback.from_user.id)
    await callback.message.edit_text(f"👥 <b>Сотрудники точки «{admin.shop_id}»</b>", reply_markup=kb.employees_manage_kb)

@router.callback_query(F.data == "emp_del_start")
async def start_del_employee(callback: types.CallbackQuery):
    admin = await db.get_user(callback.from_user.id)
    users = await db.get_employees_by_shop(admin.shop_id)
    worker_list = [u for u in users if u.role == 'worker']

    if not worker_list:
        await callback.answer("Нет сотрудников для удаления.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for user in worker_list:
        builder.button(text=f"❌ {user.full_name}", callback_data=f"confirm_del_{user.id}")
    
    builder.button(text="🔙 Назад", callback_data="back_to_emp_menu")
    builder.adjust(1)
    await callback.message.edit_text("🗑 <b>Кого уволить?</b>\nНажмите, чтобы удалить:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("confirm_del_"))
async def process_delete(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    await db.delete_user(user_id)
    await callback.answer("✅ Удалено.", show_alert=True)
    await start_del_employee(callback)

@router.callback_query(F.data == "emp_add")
async def start_add_worker(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🆕 <b>Новый сотрудник</b>\n\nВведите <b>Telegram ID</b>:",
        reply_markup=cancel_kb()
    )
    await state.set_state(AddWorker.tg_id)

@router.message(AddWorker.tg_id)
async def set_worker_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Только цифры!", reply_markup=cancel_kb())
        return
    await state.update_data(tg_id=int(message.text))
    await message.answer("👤 Введите <b>ФИО сотрудника</b>:", reply_markup=cancel_kb())
    await state.set_state(AddWorker.full_name)

@router.message(AddWorker.full_name)
async def set_worker_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer("💼 Введите <b>Должность</b> (например: Бариста):", reply_markup=cancel_kb())
    await state.set_state(AddWorker.position)

@router.message(AddWorker.position)
async def set_worker_pos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    position = message.text
    
    admin = await db.get_user(message.from_user.id)
    shop_id = admin.shop_id
    
    await db.add_user(
        tg_id=data['tg_id'],
        full_name=data['full_name'],
        role='worker',
        shop_id=shop_id,
        position=position
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 В меню сотрудников", callback_data="back_to_emp_menu")
    
    await message.answer(
        f"🎉 <b>Сотрудник добавлен в «{shop_id}»!</b>\n"
        f"👤 {data['full_name']} ({position})",
        reply_markup=builder.as_markup()
    )
    await state.clear()


# ==========================================================
# 🛠 КОНСТРУКТОР ЧЕК-ЛИСТОВ (БЕЗ РАСПИСАНИЯ)
# ==========================================================

@router.message(F.text == "📝 Создать шаблон")
async def start_creation(message: types.Message, state: FSMContext):
    await message.answer("🛠 <b>Конструктор</b>\nВведите название шаблона:", reply_markup=cancel_kb())
    await state.set_state(CreateChecklist.title)

@router.callback_query(F.data == "back_to_title")
async def back_to_title(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🛠 <b>Шаг 1.</b>\nВведите название шаблона:", reply_markup=cancel_kb())
    await state.set_state(CreateChecklist.title)

@router.message(CreateChecklist.title)
async def set_title(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if 'checklist_id' in data:
        await db.update_checklist(data['checklist_id'], title=message.text)
    
    await state.update_data(title=message.text)
    await show_assign_position_menu(message, state, is_edit=False)

async def show_assign_position_menu(message_or_callback, state: FSMContext, is_edit=False):
    positions = await db.get_all_positions()
    data = await state.get_data()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🌍 Для всех должностей", callback_data="assign_all")
    for pos in positions:
        builder.button(text=f"👔 {pos}", callback_data=f"assign_pos_{pos}")
    builder.adjust(1)
    
    builder.row(
        types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_title"),
        types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_creation")
    )
    
    text = f"📋 Название: <b>{data['title']}</b>\n👇 <b>Выберите должность:</b>"
    if is_edit: await message_or_callback.message.edit_text(text, reply_markup=builder.as_markup())
    else: await message_or_callback.answer(text, reply_markup=builder.as_markup())
    await state.set_state(CreateChecklist.assign_worker)

@router.callback_query(F.data == "back_to_assign")
async def back_to_assign(callback: types.CallbackQuery, state: FSMContext):
    await show_assign_position_menu(callback, state, is_edit=True)

# ИЗМЕНЕНИЕ: Сразу переходим к созданию вопросов (без дней недели)
@router.callback_query(CreateChecklist.assign_worker)
async def set_assignee(callback: types.CallbackQuery, state: FSMContext):
    if callback.data.startswith("back") or callback.data == "cancel_creation": return
    choice_type = callback.data.split("_")[1]
    target_position = None
    if choice_type == "pos":
        target_position = callback.data.split("_", 2)[2]

    data = await state.get_data()
    
    # Привязываем к точке админа
    admin_user = await db.get_user(callback.from_user.id)
    shop_id = admin_user.shop_id if admin_user else "Главный офис"
    
    if 'checklist_id' in data:
         await db.update_checklist(data['checklist_id'], title=data['title'], target_position=target_position)
         checklist_id = data['checklist_id']
    else:
        checklist_id = await db.create_checklist(data['title'], shop_id, target_position)
        await state.update_data(checklist_id=checklist_id)
    
    pos_text = target_position if target_position else "Все должности"
    
    await callback.message.edit_text(
        f"✅ Шаблон создан.\n🎯 Для: <b>{pos_text}</b>\n\n👇 Введите текст <b>первого вопроса</b>:",
        reply_markup=nav_kb("back_to_assign")
    )
    await state.set_state(CreateChecklist.question_text)

# ... (Вопросы и типы - стандартный код) ...
@router.callback_query(F.data == "back_to_q_text")
async def back_to_q_text(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✏️ <b>Исправление вопроса.</b>\nВведите текст заново:", reply_markup=cancel_kb())
    await state.set_state(CreateChecklist.question_text)

@router.message(CreateChecklist.question_text)
async def set_q_text(message: types.Message, state: FSMContext):
    await state.update_data(q_text=message.text)
    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(kb.type_kb))
    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_q_text"))
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_creation"))
    await message.answer(f"❓ Вопрос: <b>{message.text}</b>\nВыберите формат:", reply_markup=builder.as_markup())
    await state.set_state(CreateChecklist.question_type)

@router.callback_query(F.data == "back_to_q_type")
async def back_to_q_type(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(kb.type_kb))
    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_q_text"))
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_creation"))
    await callback.message.edit_text(f"❓ Вопрос: <b>{data['q_text']}</b>\nВыберите формат:", reply_markup=builder.as_markup())
    await state.set_state(CreateChecklist.question_type)

@router.callback_query(CreateChecklist.question_type)
async def set_q_type(callback: types.CallbackQuery, state: FSMContext):
    if callback.data.startswith("back") or callback.data == "cancel_creation": return
    q_type = callback.data.split("_")[1]
    await state.update_data(q_type=q_type)
    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(kb.photo_kb))
    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_q_type"))
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_creation"))
    await callback.message.edit_text("📸 Нужно ли фото?", reply_markup=builder.as_markup())
    await state.set_state(CreateChecklist.question_photo)

@router.callback_query(CreateChecklist.question_photo)
async def set_q_photo(callback: types.CallbackQuery, state: FSMContext):
    if callback.data.startswith("back") or callback.data == "cancel_creation": return
    needs_photo = True if callback.data == "photo_yes" else False
    data = await state.get_data()
    await db.add_question(data['checklist_id'], data['q_text'], data['q_type'], needs_photo)
    await callback.message.edit_text(f"✨ Вопрос добавлен!", reply_markup=kb.after_question_kb)
    await state.set_state(CreateChecklist.next_action)

@router.callback_query(CreateChecklist.next_action)
async def next_step(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "add_more":
        await callback.message.answer("👇 Введите текст следующего вопроса:", reply_markup=cancel_kb())
        await state.set_state(CreateChecklist.question_text)
    else:
        await callback.message.edit_text("🎉 <b>Готово!</b> Шаблон сохранен.")
        await state.clear()


# ==========================================
# 4. РАЗДЕЛ "АРХИВ"
# ==========================================

@router.message(F.text == "🗄 Архив")
async def cmd_archive_menu(message: types.Message):
    await message.answer("🗄 <b>Архив проверок</b>", reply_markup=kb.checklists_mode_kb)

@router.callback_query(F.data == "close_archive_menu")
async def close_archive_menu(callback: types.CallbackQuery):
    await callback.message.delete()

@router.callback_query(F.data == "back_to_modes")
async def back_to_modes(callback: types.CallbackQuery):
    await callback.message.edit_text("🗄 <b>Архив проверок</b>", reply_markup=kb.checklists_mode_kb)

@router.callback_query(F.data == "show_general_stats")
async def show_general_stats(callback: types.CallbackQuery):
    stats = await db.get_monthly_stats_by_shop()
    if not stats:
        await callback.answer("Данных нет.", show_alert=True)
        return
    text_lines = ["📊 <b>Сводка эффективности (Текущий месяц)</b>", "➖➖➖➖➖➖➖➖➖➖"]
    for shop, avg_score, count in stats:
        score = int(avg_score)
        icon = "🟢" if score >= 90 else "🟡" if score >= 75 else "🔴"
        text_lines.append(f"🏠 <b>{shop}</b>")
        text_lines.append(f"   📈 Результат: <b>{icon} {score}%</b>")
        text_lines.append("")
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="back_to_modes")
    await callback.message.edit_text("\n".join(text_lines), reply_markup=builder.as_markup())

@router.callback_query(F.data == "stats_chat")
async def mode_by_checklist(callback: types.CallbackQuery):
    today_checklists = await db.get_checklists_today()
    builder = InlineKeyboardBuilder()
    if today_checklists:
        for ch in today_checklists:
            builder.button(text=f"🔥 {ch.title}", callback_data=f"view_ch_{ch.id}")
    builder.button(text="📂 История", callback_data="stats_history")
    builder.button(text="🔙 Назад", callback_data="back_to_modes")
    builder.adjust(1)
    text = "📋 <b>Активные сегодня шаблоны:</b>" if today_checklists else "📋 Сегодня отчетов еще не было."
    await callback.message.edit_text(text, reply_markup=builder.as_markup())

@router.callback_query(F.data == "stats_history")
async def stats_history_list(callback: types.CallbackQuery):
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
async def stats_show_reports_list(callback: types.CallbackQuery, state: FSMContext):
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
    await callback.message.edit_text(f"🕑 <b>Последние 10 проверок:</b>", reply_markup=builder.as_markup())

@router.callback_query(F.data == "mode_by_employee")
async def mode_by_employee(callback: types.CallbackQuery):
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
async def show_employee_history(callback: types.CallbackQuery, state: FSMContext):
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
    await callback.message.edit_text(f"👤 <b>История сотрудника:</b>", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("show_rep_"))
async def show_full_report(callback: types.CallbackQuery, state: FSMContext):
    try: report_id = int(callback.data.split("_")[2])
    except: return
    data = await db.get_report_details(report_id)
    if not data or not data['report']:
        await callback.answer("Ошибка.", show_alert=True)
        return
    report, user, checklist, answers = data['report'], data['user'], data['checklist'], data['answers']
    
    text_lines = [
        f"📑 <b>ОТЧЕТ: {checklist.title.upper()}</b>", "➖➖➖➖➖➖➖➖",
        f"👤 <b>Сотрудник:</b> {user.full_name}",
        f"🏠 <b>Точка:</b> {user.shop_id}",
        f"📅 <b>Дата:</b> {report.created_at.strftime('%d.%m.%Y %H:%M')}",
        f"📊 <b>Результат:</b> {report.score_percent}%", "➖➖➖➖➖➖➖➖\n"
    ]
    photos_queue = []
    for i, (answer, question) in enumerate(answers, 1):
        text_lines.append(f"<b>{i}. {question.text}</b>")
        ans_text = answer.answer_text if answer.answer_text else "—"
        if ans_text == "Фото": ans_text = "📸 <i>(См. фото)</i>"
        elif ans_text == "Да": ans_text = "✅ Да"
        elif ans_text == "Нет": ans_text = "❌ Нет"
        text_lines.append(f"   └ 💬 Ответ: {ans_text}")
        if answer.photo_id:
            text_lines.append(f"   └ 📎 <i>Приложено фото</i>")
            photos_queue.append({'id': answer.photo_id, 'caption': f"📸 <b>Вопрос №{i}:</b> {question.text}"})
        text_lines.append("") 

    final_text = "\n".join(text_lines)
    try:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад к списку", callback_data="cleanup_and_back")
        await callback.message.edit_text(final_text, reply_markup=builder.as_markup())
        
        sent_photo_ids = []
        if photos_queue:
            await callback.message.answer("⬇️ <b>Фотографии к отчету:</b>")
            for photo in photos_queue:
                msg = await callback.message.answer_photo(photo=photo['id'], caption=photo['caption'])
                sent_photo_ids.append(msg.message_id)
                await asyncio.sleep(0.3)
        await state.update_data(sent_photo_ids=sent_photo_ids)
    except Exception as e:
        await callback.message.answer(f"⚠️ Ошибка: {e}")
    await callback.answer()

@router.callback_query(F.data == "cleanup_and_back")
async def cleanup_and_back(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photo_ids = data.get('sent_photo_ids', [])
    parent_menu = data.get('parent_menu')
    if photo_ids:
        for mid in photo_ids:
            try: await callback.message.bot.delete_message(chat_id=callback.message.chat.id, message_id=mid)
            except: pass
        try: await callback.message.bot.delete_message(chat_id=callback.message.chat.id, message_id=photo_ids[0]-1)
        except: pass
    if not parent_menu: await cmd_archive_menu(callback.message); return
    if parent_menu.startswith("hist_user_"): callback.data = parent_menu; await show_employee_history(callback, state)
    elif parent_menu.startswith("view_ch_"): callback.data = parent_menu; await stats_show_reports_list(callback, state)
    else: await cmd_archive_menu(callback.message)