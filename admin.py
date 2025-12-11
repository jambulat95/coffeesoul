import os
import asyncio
from openpyxl import Workbook
from aiogram import Router, F, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
import keyboards as kb

router = Router()

# --- МАШИНА СОСТОЯНИЙ ---
class CreateChecklist(StatesGroup):
    title = State()
    assign_worker = State()
    question_text = State()
    question_type = State()
    question_photo = State()
    next_action = State()

# Вспомогательная клавиатура для отмены создания
def cancel_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_creation")
    return builder.as_markup()

# --- ОБРАБОТКА ОТМЕНЫ ---
@router.callback_query(F.data == "cancel_creation")
async def cancel_process(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Создание чек-листа отменено.")

# --- КОНСТРУКТОР ---

@router.message(F.text == "📝 Создать чек-лист")
async def start_creation(message: types.Message, state: FSMContext):
    await message.answer("🛠 <b>Конструктор чек-листов</b>\n\nВведите название для нового списка:", reply_markup=cancel_kb())
    await state.set_state(CreateChecklist.title)

@router.message(CreateChecklist.title)
async def set_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    workers = await db.get_all_workers()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🌍 Для всех сотрудников", callback_data="assign_all")
    for w in workers:
        builder.button(text=f"👤 {w.full_name} ({w.shop_id})", callback_data=f"assign_{w.tg_id}")
    builder.adjust(1)
    builder.button(text="❌ Отмена", callback_data="cancel_creation") # Кнопка отмены
    
    await message.answer(f"📋 Название: <b>{message.text}</b>\n👇 <b>Кому будет доступен этот чек-лист?</b>", reply_markup=builder.as_markup())
    await state.set_state(CreateChecklist.assign_worker)

@router.callback_query(CreateChecklist.assign_worker)
async def set_assignee(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "cancel_creation": return # Обработается выше
    
    choice = callback.data.split("_")[1]
    title = (await state.get_data())['title']
    assigned_to = int(choice) if choice != "all" else None
    
    checklist_id = await db.create_checklist(title, assigned_to)
    await state.update_data(checklist_id=checklist_id)
    
    await callback.message.edit_text(
        f"✅ Чек-лист <b>«{title}»</b> создан.\n👇 Введите текст <b>первого вопроса</b>:",
        reply_markup=cancel_kb()
    )
    await state.set_state(CreateChecklist.question_text)

@router.message(CreateChecklist.question_text)
async def set_q_text(message: types.Message, state: FSMContext):
    await state.update_data(q_text=message.text)
    await message.answer(f"❓ Вопрос: <b>{message.text}</b>\nВыберите формат ответа:", reply_markup=kb.type_kb)
    await state.set_state(CreateChecklist.question_type)

@router.callback_query(CreateChecklist.question_type)
async def set_q_type(callback: types.CallbackQuery, state: FSMContext):
    q_type = callback.data.split("_")[1]
    await state.update_data(q_type=q_type)
    await callback.message.edit_text("📸 Нужно ли сотруднику обязательно прикреплять <b>фото</b>?", reply_markup=kb.photo_kb)
    await state.set_state(CreateChecklist.question_photo)

@router.callback_query(CreateChecklist.question_photo)
async def set_q_photo(callback: types.CallbackQuery, state: FSMContext):
    needs_photo = True if callback.data == "photo_yes" else False
    data = await state.get_data()
    await db.add_question(data['checklist_id'], data['q_text'], data['q_type'], needs_photo)
    await callback.message.edit_text(f"✨ Вопрос <b>«{data['q_text']}»</b> добавлен!", reply_markup=kb.after_question_kb)
    await state.set_state(CreateChecklist.next_action)

@router.callback_query(CreateChecklist.next_action)
async def next_step(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "add_more":
        await callback.message.answer("👇 Введите текст следующего вопроса:", reply_markup=cancel_kb())
        await state.set_state(CreateChecklist.question_text)
    else:
        await callback.message.edit_text("🎉 <b>Готово!</b> Чек-лист сохранен.")
        await state.clear()

# --- СТАТИСТИКА ---

@router.message(F.text == "📊 Статистика")
async def cmd_stats(message: types.Message):
    await message.answer("📈 <b>Раздел аналитики</b>\nВыберите формат отчета:", reply_markup=kb.stats_type_kb)

# Хендлер для кнопки "Назад" (возврат к выбору Excel/Чат)
@router.callback_query(F.data == "back_to_stats_main")
async def back_to_stats_main(callback: types.CallbackQuery):
    await callback.message.edit_text("📈 <b>Раздел аналитики</b>\nВыберите формат отчета:", reply_markup=kb.stats_type_kb)

@router.callback_query(F.data == "stats_excel")
async def stats_excel_handler(callback: types.CallbackQuery):
    await callback.message.edit_text("⏳ <b>Генерирую Excel файл...</b>")
    data = await db.get_all_reports_data()
    if not data:
        # Добавляем кнопку назад, даже если пусто
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="back_to_stats_main")
        await callback.message.edit_text("📂 В базе пока нет отчетов.", reply_markup=builder.as_markup())
        return
    
    # ... (код генерации excel такой же) ...
    wb = Workbook()
    ws = wb.active
    ws.title = "Отчеты"
    ws.append(["Дата", "Точка", "Сотрудник", "Чек-лист", "Ответы"])
    for row in data:
        ws.append([row["date"], row["shop"], row["employee"], row["checklist"], row["answers"]])
    ws.column_dimensions['E'].width = 50
    filename = f"report_{callback.from_user.id}.xlsx"
    wb.save(filename)
    await callback.message.answer_document(FSInputFile(filename), caption="📊 <b>Полная выгрузка данных</b>")
    os.remove(filename)
    
    # Возвращаем меню после отправки файла
    await callback.message.answer("Выберите формат отчета:", reply_markup=kb.stats_type_kb)

@router.callback_query(F.data == "stats_chat")
async def stats_chat_select_checklist(callback: types.CallbackQuery):
    today_checklists = await db.get_checklists_today()
    builder = InlineKeyboardBuilder()
    if today_checklists:
        for ch in today_checklists:
            builder.button(text=f"🔥 {ch.title}", callback_data=f"view_ch_{ch.id}")
    
    builder.button(text="📂 История (Все чек-листы)", callback_data="stats_history")
    # Кнопка НАЗАД
    builder.button(text="🔙 Назад", callback_data="back_to_stats_main")
    builder.adjust(1)
    
    text = "📊 <b>Оперативная сводка за сегодня:</b>"
    if not today_checklists: text = "💤 <b>Сегодня отчетов еще не было.</b>"
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
    
    # Кнопка НАЗАД (ведет к сводке за сегодня)
    builder.button(text="🔙 Назад", callback_data="stats_chat")
    builder.adjust(1)
    await callback.message.edit_text("📂 <b>Архив всех чек-листов:</b>", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("view_ch_"))
async def stats_show_reports_list(callback: types.CallbackQuery):
    checklist_id = int(callback.data.split("_")[2])
    reports_data = await db.get_reports_by_checklist_id(checklist_id)
    
    if not reports_data:
        # Если пусто, даем кнопку назад
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="stats_chat")
        await callback.message.edit_text("📭 По этому чек-листу еще нет проверок.", reply_markup=builder.as_markup())
        return

    builder = InlineKeyboardBuilder()
    for report, user in reports_data:
        time_str = report.created_at.strftime("%d.%m %H:%M")
        btn_text = f"{time_str} | {user.full_name}"
        builder.button(text=btn_text, callback_data=f"show_rep_{report.id}")
    
    # Кнопка НАЗАД (ведет к списку чек-листов)
    builder.button(text="🔙 Назад", callback_data="stats_chat")
    builder.adjust(1)
    await callback.message.edit_text(f"🕑 <b>Последние 10 проверок:</b>", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("show_rep_"))
async def show_full_report(callback: types.CallbackQuery):
    report_id = int(callback.data.split("_")[2])
    data = await db.get_report_details(report_id)
    report = data['report']
    user = data['user']
    checklist = data['checklist']
    answers = data['answers']
    
    text_lines = [
        f"📑 <b>ОТЧЕТ: {checklist.title.upper()}</b>",
        f"➖➖➖➖➖➖➖➖",
        f"👤 <b>Сотрудник:</b> {user.full_name}",
        f"🏠 <b>Точка:</b> {user.shop_id}",
        f"📅 <b>Дата:</b> {report.created_at.strftime('%d.%m.%Y %H:%M')}",
        f"➖➖➖➖➖➖➖➖\n"
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
            text_lines.append(f"   └ 📎 <i>Приложено фото (см. ниже)</i>")
            photos_queue.append({'id': answer.photo_id, 'caption': f"📸 <b>Вопрос №{i}:</b> {question.text}"})
        text_lines.append("")
    
    final_text = "\n".join(text_lines)
    try:
        await callback.message.answer(final_text)
        if photos_queue:
            await callback.message.answer("⬇️ <b>Фотографии к отчету:</b>")
            for photo in photos_queue:
                await callback.message.answer_photo(photo=photo['id'], caption=photo['caption'])
                await asyncio.sleep(0.3)
    except Exception as e:
        await callback.message.answer(f"⚠️ Ошибка: {e}")
    await callback.answer()

# --- СОТРУДНИКИ ---

@router.message(F.text == "👥 Сотрудники")
async def cmd_employees_list(message: types.Message):
    shops = await db.get_all_shops()
    if not shops:
        await message.answer("👥 В базе пока нет сотрудников.")
        return
    builder = InlineKeyboardBuilder()
    for shop in shops:
        builder.button(text=f"🏠 {shop}", callback_data=f"shop_users_{shop}")
    builder.adjust(2)
    await message.answer("👥 <b>Управление персоналом</b>\nВыберите точку:", reply_markup=builder.as_markup())

# Хендлер для кнопки "Назад к точкам"
@router.callback_query(F.data == "back_to_shops")
async def back_to_shops(callback: types.CallbackQuery):
    # Вызываем логику показа точек, но через редактирование сообщения
    shops = await db.get_all_shops()
    builder = InlineKeyboardBuilder()
    for shop in shops:
        builder.button(text=f"🏠 {shop}", callback_data=f"shop_users_{shop}")
    builder.adjust(2)
    await callback.message.edit_text("👥 <b>Управление персоналом</b>\nВыберите точку:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("shop_users_"))
async def show_shop_employees(callback: types.CallbackQuery):
    target_shop = callback.data.split("_", 2)[2]
    users = await db.get_employees_by_shop(target_shop)
    
    text_lines = [f"🏠 <b>Точка: {target_shop}</b>", f"👥 Всего: {len(users)}", f"➖➖➖➖➖➖➖➖➖➖"]
    for i, user in enumerate(users, 1):
        role_icon = "👔" if user.role == 'admin' else "☕"
        text_lines.append(f"<b>{i}. {role_icon} {user.full_name}</b>")
        text_lines.append(f"   └ 💼 {user.position}")
        text_lines.append("")
    
    # Кнопка НАЗАД (к списку точек)
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад к точкам", callback_data="back_to_shops")
    
    await callback.message.edit_text("\n".join(text_lines), reply_markup=builder.as_markup())