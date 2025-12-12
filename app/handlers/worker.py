from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app import crud as db
from app import keyboards as kb

router = Router()

class PassChecklist(StatesGroup):
    choosing = State()
    answering = State()


# 1. Выбор чек-листа (С разделением на Сделано / Не сделано)

@router.message(F.text == "✅ Пройти чек-лист")
async def choose_checklist(message: types.Message):
    # Используем правильную функцию для получения чек-листов
    all_checklists = await db.get_checklists_for_user(message.from_user.id)
    
    if not all_checklists:
        await message.answer("📂 Для вас пока нет доступных чек-листов.")
        return

    completed_ids = await db.get_today_completed_checklist_ids(message.from_user.id)
    builder = InlineKeyboardBuilder()
    
    todo_list = []
    done_list = []
    
    for ch in all_checklists:
        if ch.id in completed_ids:
            done_list.append(ch)
        else:
            todo_list.append(ch)

    # --- СПИСОК "СДЕЛАТЬ" ---
    for ch in todo_list:
        # ИСПРАВЛЕНИЕ ЗДЕСЬ:
        # Проверяем target_position вместо assigned_to
        if ch.target_position:
            # Если для конкретной должности
            label = f"👔 {ch.title} ({ch.target_position})"
        else:
            # Если для всех (сетевой стандарт)
            label = f"🌍 {ch.title}"
            
        builder.button(text=label, callback_data=f"start_{ch.id}")

    # --- СПИСОК "ГОТОВО" ---
    if done_list:
        if todo_list: builder.button(text="⬇️ Выполнено сегодня ⬇️", callback_data="ignore")
        for ch in done_list:
            builder.button(text=f"✅ {ch.title} (Готово)", callback_data=f"start_{ch.id}")
            
    builder.button(text="❌ Закрыть список", callback_data="cancel_worker_selection")

    builder.adjust(1)
    await message.answer("👇 <b>Выберите чек-лист:</b>", reply_markup=builder.as_markup())

# Добавьте этот обработчик ниже
@router.callback_query(F.data == "cancel_worker_selection")
async def cancel_worker_selection(callback: types.CallbackQuery):
    await callback.message.delete() # Просто удаляем сообщение с кнопками

# Маленький хендлер-заглушка, чтобы кнопка-разделитель не выдавала ошибок при нажатии
@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: types.CallbackQuery):
    await callback.answer() # Просто убираем часики

# 2. Старт проверки
@router.callback_query(F.data.startswith("start_"))
async def start_pass(callback: types.CallbackQuery, state: FSMContext):
    checklist_id = int(callback.data.split("_")[1])
    report_id = await db.create_report(callback.from_user.id, checklist_id)
    questions = await db.get_questions(checklist_id)
    
    if not questions:
        await callback.message.answer("⚠️ В этом чек-листе пока нет вопросов.")
        return

    # Очищаем все старые данные
    await state.update_data(report_id=report_id, questions=questions, current_index=0, temp_answer=None)
    await state.set_state(PassChecklist.answering)
    
    await callback.message.edit_text("🚀 <b>Проверка началась!</b>\nОтвечайте честно. Поехали!")
    await send_question(callback.message, state)

# 1. Функция отправки вопроса (почти без изменений)
async def send_question(message, state: FSMContext):
    data = await state.get_data()
    index = data['current_index']
    questions = data['questions']
    
    # ФИНАЛ: Вопросы кончились
    if index >= len(questions):
        # ВАЖНО: Запускаем подсчет итогового процента
        final_percent = await db.finish_report_calculation(data['report_id'])
        
        # Показываем результат сотруднику
        emoji = "🟢" if final_percent >= 90 else "🟡" if final_percent >= 70 else "🔴"
        
        await message.answer(
            f"🏁 <b>Чек-лист завершен!</b>\n"
            f"📊 Ваш результат: {emoji} <b>{final_percent}%</b>\n\n"
            "Данные переданы управляющему.", 
            reply_markup=kb.worker_kb
        )
        await state.clear()
        return

    question = questions[index]
    # ... (дальше код отрисовки кнопок тот же, что был) ...
    text = f"🔹 <b>Вопрос {index + 1} из {len(questions)}</b>\n\n{question.text}"
    if question.needs_photo: text += "\n\n📸 <b>Требуется фото-подтверждение!</b>"
    builder = InlineKeyboardBuilder()
    if question.type == 'binary':
        builder.button(text="👍 Да", callback_data="ans_Да")
        builder.button(text="👎 Нет", callback_data="ans_Нет")
    elif question.type == 'scale':
        for i in range(1, 11):
            builder.button(text=str(i), callback_data=f"ans_{i}")
        builder.adjust(5)
    await message.answer(text, reply_markup=builder.as_markup())


# 2. Функция сохранения ответа (С ПОДСЧЕТОМ)
async def save_step(message_or_callback, state, answer_text, photo_id=None):
    data = await state.get_data()
    question = data['questions'][data['current_index']]
    
    # --- ЛОГИКА БАЛЛОВ ---
    points = 0
    if question.type == 'binary':
        if answer_text == "Да": points = 1
        else: points = 0
    elif question.type == 'scale':
        if answer_text.isdigit(): points = int(answer_text)
    # text вопросы дают 0 баллов
    # ---------------------

    await db.save_answer_with_points(data['report_id'], question.id, answer_text, photo_id, points)
    
    await state.update_data(temp_answer=None, current_index=data['current_index'] + 1)
    
    # Если это был callback
    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.delete()
        await send_question(message_or_callback.message, state)
    else:
        # Если message
        await send_question(message_or_callback, state)

# --- ХЕНДЛЕРЫ ОТВЕТОВ (Используют save_step) ---

@router.callback_query(PassChecklist.answering, F.data.startswith("ans_"))
async def process_button_answer(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    question = data['questions'][data['current_index']]
    answer_value = callback.data.split("_")[1]

    if not question.needs_photo:
        await save_step(callback, state, answer_value)
        return

    await state.update_data(temp_answer=answer_value)
    await callback.message.edit_text(f"✅ Ответ <b>«{answer_value}»</b> принят.\n📸 <b>Пришлите фото:</b>")
    await callback.answer()

@router.message(PassChecklist.answering, F.text)
async def process_text_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    question = data['questions'][data['current_index']]
    
    if question.type != 'text': 
        await message.answer("👇 Нажмите кнопку.")
        return

    if not question.needs_photo:
        await save_step(message, state, message.text)
        return

    await state.update_data(temp_answer=message.text)
    await message.answer(f"✅ Текст принят.\n📸 <b>Пришлите фото:</b>")

@router.message(PassChecklist.answering, F.photo)
async def process_photo_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    question = data['questions'][data['current_index']]
    saved_answer = data.get('temp_answer')

    if not saved_answer and question.type != 'text' and question.needs_photo:
        await message.answer("⚠️ Сначала выберите ответ кнопкой!")
        await send_question(message, state)
        return

    final_text = saved_answer if saved_answer else (message.caption if message.caption else "Фото-отчет")
    photo_id = message.photo[-1].file_id
    
    await save_step(message, state, final_text, photo_id)