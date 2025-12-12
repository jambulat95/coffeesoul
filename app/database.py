"""Legacy facade.

Раньше в этом модуле были и модели, и engine, и все запросы.
Теперь:
- таблицы: `app/models.py`
- подключение/инициализация БД: `app/db/session.py`
- запросы: `app/crud/*`

Этот файл оставлен для обратной совместимости со старыми импортами.
"""

from __future__ import annotations

from app.crud import *  # noqa: F401,F403
from app.db import init_db


# Backward compatible name used in старом коде.
async_main = init_db


__all__ = [
    *globals().get("__all__", []),
    "init_db",
    "async_main",
]
