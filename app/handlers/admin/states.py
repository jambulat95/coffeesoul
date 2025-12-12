from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class CreateChecklist(StatesGroup):
    title = State()
    assign_worker = State()  # выбор должности
    question_text = State()
    question_type = State()
    question_photo = State()
    next_action = State()


class AddWorker(StatesGroup):
    tg_id = State()
    full_name = State()
    position = State()


class AddManager(StatesGroup):
    tg_id = State()
    full_name = State()
    shop_name = State()


class AddSuperAdmin(StatesGroup):
    tg_id = State()
    full_name = State()

