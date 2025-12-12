from __future__ import annotations

from sqlalchemy import select

from app.db import async_session
from app.models import Checklist, Question, User


async def create_checklist(title: str, shop_id: str, target_position: str | None = None) -> int:
    async with async_session() as session:
        checklist = Checklist(title=title, shop_id=shop_id, target_position=target_position)
        session.add(checklist)
        await session.commit()
        await session.refresh(checklist)
        return checklist.id


async def update_checklist(
    checklist_id: int,
    title: str | None = None,
    target_position: str | None = None,
) -> None:
    async with async_session() as session:
        checklist = await session.get(Checklist, checklist_id)
        if not checklist:
            return

        if title:
            checklist.title = title
        checklist.target_position = target_position
        await session.commit()


async def get_checklists_for_user(user_tg_id: int) -> list[Checklist]:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == user_tg_id))
        if not user:
            return []

        query = select(Checklist).where(
            ((Checklist.shop_id == user.shop_id) | (Checklist.shop_id == None))
            & ((Checklist.target_position == user.position) | (Checklist.target_position == None))
        )
        result = await session.execute(query)
        return list(result.scalars().all())


async def get_checklists() -> list[Checklist]:
    async with async_session() as session:
        result = await session.execute(select(Checklist))
        return list(result.scalars().all())


async def add_question(
    checklist_id: int,
    text: str,
    type: str,
    needs_photo: bool,
) -> None:
    async with async_session() as session:
        session.add(
            Question(
                checklist_id=checklist_id,
                text=text,
                type=type,
                needs_photo=needs_photo,
            )
        )
        await session.commit()


async def get_questions(checklist_id: int) -> list[Question]:
    async with async_session() as session:
        result = await session.execute(
            select(Question).where(Question.checklist_id == checklist_id)
        )
        return list(result.scalars().all())


async def get_checklists_today() -> list[Checklist]:
    # Implemented in reports.py to keep the join near Report.
    from datetime import datetime
    from app.models import Report

    async with async_session() as session:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        query = (
            select(Checklist)
            .join(Report, Checklist.id == Report.checklist_id)
            .where(Report.created_at >= today_start)
            .distinct()
        )
        result = await session.execute(query)
        return list(result.scalars().all())
