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
    shop_id: str | None = None,
    target_position: str | None = None,
) -> None:
    async with async_session() as session:
        checklist = await session.get(Checklist, checklist_id)
        if not checklist:
            return

        if title is not None:
            checklist.title = title
        if shop_id is not None:
            checklist.shop_id = shop_id
        if target_position is not None:
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


async def get_questions(checklist_id: int, include_deleted: bool = False) -> list[Question]:
    async with async_session() as session:
        query = select(Question).where(Question.checklist_id == checklist_id)
        if not include_deleted:
            query = query.where(Question.is_deleted == False)
        result = await session.execute(query)
        return list(result.scalars().all())


async def get_checklist(checklist_id: int) -> Checklist | None:
    async with async_session() as session:
        return await session.get(Checklist, checklist_id)


async def get_question(question_id: int, include_deleted: bool = False) -> Question | None:
    async with async_session() as session:
        question = await session.get(Question, question_id)
        if question and not include_deleted and question.is_deleted:
            return None
        return question


async def update_question(
    question_id: int,
    text: str | None = None,
    type: str | None = None,
    needs_photo: bool | None = None,
) -> None:
    async with async_session() as session:
        question = await session.get(Question, question_id)
        if not question:
            return

        if text is not None:
            question.text = text
        if type is not None:
            question.type = type
        if needs_photo is not None:
            question.needs_photo = needs_photo
        await session.commit()


async def delete_question(question_id: int) -> None:
    """Мягкое удаление вопроса - помечает как удаленный вместо физического удаления"""
    async with async_session() as session:
        question = await session.get(Question, question_id)
        if question:
            question.is_deleted = True
            await session.commit()


async def delete_checklist(checklist_id: int) -> tuple[bool, str]:
    """
    Удаляет чек-лист. Возвращает (успех, сообщение).
    Если есть отчеты, возвращает False и предупреждение.
    """
    from app.models import Report
    from sqlalchemy import func
    
    async with async_session() as session:
        # Проверяем, есть ли отчеты для этого чек-листа
        reports_count = await session.scalar(
            select(func.count(Report.id)).where(Report.checklist_id == checklist_id)
        )
        
        if reports_count and reports_count > 0:
            return (
                False,
                f"⚠️ Невозможно удалить шаблон: найдено {reports_count} отчетов. "
                "Сначала удалите все отчеты или используйте архивацию."
            )
        
        checklist = await session.get(Checklist, checklist_id)
        if not checklist:
            return (False, "Шаблон не найден.")
        
        await session.delete(checklist)
        await session.commit()
        return (True, f"✅ Шаблон '{checklist.title}' успешно удален.")


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
