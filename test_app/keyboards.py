from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- ГЛАВНЫЕ МЕНЮ (Reply) ---

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- МЕНЮ СУПЕР-АДМИНА ---
superadmin_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="➕ Создать Управляющего")],
    [KeyboardButton(text="📊 Полный Отчет (Месяц)")]
], resize_keyboard=True)

# --- МЕНЮ УПРАВЛЯЮЩЕГО (ADMIN) ---
# У него нет кнопки "Создать точку", он управляет только своей
admin_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="📝 Создать шаблон"), KeyboardButton(text="🗄 Архив")],
    [KeyboardButton(text="👥 Мои сотрудники")] 
], resize_keyboard=True)

# --- МЕНЮ СОТРУДНИКА ---
worker_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="✅ Начать проверку")],
    [KeyboardButton(text="👤 Мой профиль")]
], resize_keyboard=True)

# ... (Остальные инлайн-клавиатуры типа checklists_mode_kb оставляем как были) ...
checklists_mode_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👤 По сотрудникам", callback_data="mode_by_employee")],
    [InlineKeyboardButton(text="📋 По шаблонам", callback_data="stats_chat")],
    [InlineKeyboardButton(text="📊 Сводка за месяц", callback_data="show_general_stats")],
    [InlineKeyboardButton(text="❌ Закрыть меню", callback_data="close_archive_menu")] 
])

# Меню управления сотрудниками (Для Админа)
employees_manage_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Добавить сотрудника", callback_data="emp_add")],
    [InlineKeyboardButton(text="➖ Удалить сотрудника", callback_data="emp_del_start")],
    [InlineKeyboardButton(text="📋 Список команды", callback_data="emp_list")],
    [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_archive_menu")]
])


# --- КНОПКИ КОНСТРУКТОРА (Inline) ---

# 3. Выбор типа вопроса
type_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔘 Да / Нет", callback_data="type_binary")],
    [InlineKeyboardButton(text="🔢 Оценка 1-10", callback_data="type_scale")],
    [InlineKeyboardButton(text="✏️ Текст", callback_data="type_text")],
])

# 4. Нужно ли фото?
photo_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📸 Фото обязательно", callback_data="photo_yes")],
    [InlineKeyboardButton(text="❌ Без фото", callback_data="photo_no")],
])

# 5. Меню после добавления вопроса
after_question_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Добавить еще вопрос", callback_data="add_more")],
    [InlineKeyboardButton(text="💾 Завершить и сохранить", callback_data="finish_checklist")],
])

# 6. Выбор типа статистики
stats_type_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📥 Скачать Excel файл", callback_data="stats_excel")],
    [InlineKeyboardButton(text="📱 Смотреть в чате", callback_data="stats_chat")],
])

def days_selection_kb(selected_days: list):
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    builder = InlineKeyboardBuilder()
    
    for i, day_name in enumerate(days):
        # Если день выбран, ставим галочку
        label = f"✅ {day_name}" if str(i) in selected_days else day_name
        builder.button(text=label, callback_data=f"toggle_day_{i}")
        
    builder.adjust(7) # 7 кнопок в ряд
    
    # Кнопки управления
    builder.row(InlineKeyboardButton(text="Выбрать все", callback_data="days_all"))
    builder.row(InlineKeyboardButton(text="🧹 Очистить", callback_data="days_clear"))
    builder.row(InlineKeyboardButton(text="💾 Готово (Далее)", callback_data="days_done"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_assign"))
    
    return builder.as_markup()