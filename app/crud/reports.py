from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, func, select

from app.db import async_session
from app.models import Answer, Checklist, Question, Report, User


async def create_report(user_tg_id: int, checklist_id: int) -> int:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == user_tg_id))
        report = Report(user_id=user.id, checklist_id=checklist_id, score_percent=0)
        session.add(report)
        await session.commit()
        await session.refresh(report)
        return report.id


async def save_answer_with_points(
    report_id: int,
    question_id: int,
    answer_text: str | None,
    photo_id: str | None,
    points: int,
) -> None:
    async with async_session() as session:
        session.add(
            Answer(
                report_id=report_id,
                question_id=question_id,
                answer_text=answer_text,
                photo_id=photo_id,
                points=points,
            )
        )
        await session.commit()


async def finish_report_calculation(report_id: int) -> int:
    async with async_session() as session:
        sum_points = (
            await session.scalar(
                select(func.sum(Answer.points)).where(Answer.report_id == report_id)
            )
            or 0
        )
        report = await session.get(Report, report_id)
        # Для расчета баллов учитываем только не удаленные вопросы
        questions = await session.scalars(
            select(Question)
            .where(Question.checklist_id == report.checklist_id)
            .where(Question.is_deleted == False)
        )

        max_points = 0
        for q in questions:
            if q.type == "binary":
                max_points += 1
            elif q.type == "scale":
                max_points += 10

        percent = 0
        if max_points > 0:
            percent = int((sum_points / max_points) * 100)

        report.score_percent = percent
        await session.commit()
        return percent


async def get_monthly_stats_by_shop():
    async with async_session() as session:
        today = datetime.now()
        start_month = today.replace(day=1, hour=0, minute=0, second=0)
        query = (
            select(User.shop_id, func.avg(Report.score_percent), func.count(Report.id))
            .join(User, Report.user_id == User.id)
            .where(Report.created_at >= start_month)
            .group_by(User.shop_id)
        )
        result = await session.execute(query)
        return result.all()


async def get_today_completed_checklist_ids(tg_id: int) -> list[int]:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return []

        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await session.execute(
            select(Report.checklist_id)
            .where(Report.user_id == user.id)
            .where(Report.created_at >= today_start)
        )
        return list(result.scalars().all())


async def get_all_reports_data():
    async with async_session() as session:
        query = select(Report).order_by(desc(Report.created_at))
        result = await session.execute(query)
        reports = result.scalars().all()

        export_data = []
        for report in reports:
            user = await session.scalar(select(User).where(User.id == report.user_id))
            checklist = await session.scalar(
                select(Checklist).where(Checklist.id == report.checklist_id)
            )
            answers_result = await session.execute(
                select(Answer, Question)
                .join(Question, Answer.question_id == Question.id)
                .where(Answer.report_id == report.id)
            )
            answers = answers_result.all()

            formatted_answers = []
            for ans, quest in answers:
                val = ans.answer_text if ans.answer_text else "-"
                formatted_answers.append(f"{quest.text}: {val} ({ans.points}б)")

            export_data.append(
                {
                    "date": report.created_at.strftime("%Y-%m-%d %H:%M"),
                    "shop": user.shop_id,
                    "employee": user.full_name,
                    "checklist": checklist.title,
                    "answers": " || ".join(formatted_answers),
                }
            )

        return export_data


async def get_checklists_today() -> list[Checklist]:
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


async def get_reports_by_checklist_id(checklist_id: int):
    async with async_session() as session:
        query = (
            select(Report, User)
            .join(User, Report.user_id == User.id)
            .where(Report.checklist_id == checklist_id)
            .order_by(desc(Report.created_at))
            .limit(10)
        )
        result = await session.execute(query)
        return result.all()


async def get_report_details(report_id: int):
    async with async_session() as session:
        report = await session.get(Report, report_id)
        user = await session.get(User, report.user_id)
        checklist = await session.get(Checklist, report.checklist_id)
        answers_res = await session.execute(
            select(Answer, Question)
            .join(Question, Answer.question_id == Question.id)
            .where(Answer.report_id == report_id)
        )
        answers = answers_res.all()

        return {
            "report": report,
            "user": user,
            "checklist": checklist,
            "answers": answers,
        }


async def get_reports_by_user_tg_id(tg_id: int):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return []

        query = (
            select(Report, Checklist)
            .join(Checklist, Report.checklist_id == Checklist.id)
            .where(Report.user_id == user.id)
            .order_by(desc(Report.created_at))
            .limit(10)
        )
        result = await session.execute(query)
        return result.all()
