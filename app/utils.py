from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def cancel_kb(cancel_callback: str = "cancel_creation") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data=cancel_callback)
    return builder.as_markup()


def nav_kb(back_callback: str, cancel_callback: str = "cancel_creation") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data=back_callback)
    builder.button(text="❌ Отмена", callback_data=cancel_callback)
    builder.adjust(1)
    return builder.as_markup()
