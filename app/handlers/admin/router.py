from __future__ import annotations

from aiogram import Router

router = Router()

# Import modules to register handlers on this router via decorators.
# The imports are intentionally at the bottom to avoid circular imports.
from . import archive as _archive  # noqa: E402,F401
from . import checklist_builder as _checklist_builder  # noqa: E402,F401
from . import common as _common  # noqa: E402,F401
from . import employees as _employees  # noqa: E402,F401
from . import superadmin as _superadmin  # noqa: E402,F401

__all__ = ["router"]

