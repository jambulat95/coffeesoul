from __future__ import annotations

from aiogram import F, types
from aiogram.fsm.context import FSMContext

from .router import router


@router.callback_query(F.data == "cancel_creation")
async def cancel_process(callback: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.")

