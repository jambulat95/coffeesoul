import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from handlers.admin import router as admin_router
from handlers.start import router as start_router
from handlers.worker import router as worker_router
import database as db

BOT_TOKEN="8213489358:AAEmAe8BR6u2OBe7n2cWEbPzcQCktq0tKOQ"

async def main():
    # Создаем таблицы БД (если их нет)
    await db.async_main()
    
    # --- ВРЕМЕННОЕ РЕШЕНИЕ: Добавляем ВАС как админа ---
    # Замените 123456789 на ваш реальный Telegram ID (его пришлет бот, если вы не в базе)
    # После первого запуска этот блок можно закомментировать
    await db.add_user(
        tg_id=942944230, 
        full_name="Администратор", 
        role="superadmin", 
        shop_id="Пр. Мира, 1", 
        position="Управляющий"
    )

    # ----------------------------------------------------

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    dp.include_router(admin_router)
    dp.include_router(start_router)
    dp.include_router(worker_router)
    
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")