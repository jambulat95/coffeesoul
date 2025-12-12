import asyncio
import logging
import sys
from pathlib import Path

# Allow running as a script: `python app/main.py`
# (adds repo root to sys.path so `import config` works)
if __package__ is None or __package__ == "":
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from app import crud as db
from app.db import init_db
from app.handlers.admin import router as admin_router
from app.handlers.start import router as start_router
from app.handlers.worker import router as worker_router


async def main():
    
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
    if not settings.bot_token:
        raise ValueError(
            "BOT token is not set. Put it into .env as BOT_TOKEN=... (or set bot_token env var)."
        )

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
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