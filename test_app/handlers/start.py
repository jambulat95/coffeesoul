from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
import database as db
import keyboards as kb

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    tg_id = message.from_user.id
    user = await db.get_user(tg_id)

    # Сценарий "Чужак"
    if not user:
        await message.answer(
            f"👋 <b>Здравствуйте!</b>\n\n"

            f"К сожалению, вас нет в системе.\n\n"
            f"🆔 Ваш ID: <code>{tg_id}</code>\n"
            f"<i>Отправьте этот код управляющему, чтобы получить доступ.</i>\n"
            f"<i>После этого нажмите на /start</i>"
        )
        return

    # Сценарий "Свой"
    await message.answer(f"Добро пожаловать, <b>{user.full_name}</b>!")
    
    if user.role == "superadmin":
        await message.answer("Вы вошли как Гендиректор.", reply_markup=kb.superadmin_kb)
    elif user.role == "admin":
        await message.answer(f"Вы вошли как Управляющий.\nТочка: <b>{user.shop_id}</b>", reply_markup=kb.admin_kb)
    elif user.role == "worker":
        await message.answer(f"💼 Работаем.\n🏠 Точка: <b>{user.shop_id}</b>", reply_markup=kb.worker_kb)