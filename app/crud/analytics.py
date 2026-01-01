from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import desc, func, select

from app.db import async_session
from app.models import AdminShop, Checklist, Question, Report, User


async def get_admin_activity_stats(admin_tg_id: int) -> dict:
    """Получить статистику активности управленца."""
    async with async_session() as session:
        admin = await session.scalar(select(User).where(User.tg_id == admin_tg_id))
        if not admin:
            return {}

        # Получаем точки админа
        shops_result = await session.execute(
            select(AdminShop.shop_name).where(AdminShop.admin_tg_id == admin_tg_id)
        )
        admin_shops = [row[0] for row in shops_result.all()]

        # Количество чек-листов, созданных для точек админа
        checklists_count = 0
        if admin_shops:
            checklists_result = await session.execute(
                select(func.count(Checklist.id)).where(Checklist.shop_id.in_(admin_shops))
            )
            checklists_count = checklists_result.scalar() or 0

        # Количество сотрудников в точках админа
        workers_count = 0
        if admin_shops:
            workers_result = await session.execute(
                select(func.count(User.id))
                .where(User.role == "worker")
                .where(User.shop_id.in_(admin_shops))
            )
            workers_count = workers_result.scalar() or 0

        # Последняя активность (последний отчет от сотрудников админа)
        last_activity = None
        if admin_shops:
            last_report_result = await session.execute(
                select(Report.created_at)
                .join(User, Report.user_id == User.id)
                .where(User.shop_id.in_(admin_shops))
                .order_by(desc(Report.created_at))
                .limit(1)
            )
            last_activity_row = last_report_result.first()
            if last_activity_row:
                last_activity = last_activity_row[0]

        # Количество отчетов за последние 7 дней
        week_ago = datetime.now() - timedelta(days=7)
        reports_count_week = 0
        if admin_shops:
            reports_result = await session.execute(
                select(func.count(Report.id))
                .join(User, Report.user_id == User.id)
                .where(User.shop_id.in_(admin_shops))
                .where(Report.created_at >= week_ago)
            )
            reports_count_week = reports_result.scalar() or 0

        return {
            "admin": admin,
            "shops": admin_shops,
            "checklists_count": checklists_count,
            "workers_count": workers_count,
            "last_activity": last_activity,
            "reports_count_week": reports_count_week,
        }


async def get_all_admins_activity() -> list[dict]:
    """Получить статистику активности всех управленцев."""
    async with async_session() as session:
        admins = await session.execute(
            select(User).where(User.role == "admin").order_by(User.full_name)
        )
        admins_list = list(admins.scalars().all())

        result = []
        for admin in admins_list:
            stats = await get_admin_activity_stats(admin.tg_id)
            result.append(stats)

        return result


async def get_worker_activity_stats(worker_id: int) -> dict:
    """Получить статистику активности сотрудника."""
    async with async_session() as session:
        worker = await session.get(User, worker_id)
        if not worker or worker.role != "worker":
            return {}

        # Все отчеты сотрудника
        reports_result = await session.execute(
            select(Report)
            .where(Report.user_id == worker.id)
            .order_by(desc(Report.created_at))
        )
        reports = list(reports_result.scalars().all())

        # Статистика
        total_reports = len(reports)
        avg_score = 0
        last_activity = None

        if reports:
            scores = [r.score_percent for r in reports if r.score_percent > 0]
            if scores:
                avg_score = int(sum(scores) / len(scores))
            last_activity = reports[0].created_at

        # Отчеты за последние 7 дней
        week_ago = datetime.now() - timedelta(days=7)
        reports_week = [r for r in reports if r.created_at >= week_ago]
        reports_count_week = len(reports_week)

        return {
            "worker": worker,
            "total_reports": total_reports,
            "avg_score": avg_score,
            "last_activity": last_activity,
            "reports_count_week": reports_count_week,
        }


async def get_all_workers_activity() -> list[dict]:
    """Получить статистику активности всех сотрудников."""
    async with async_session() as session:
        workers = await session.execute(
            select(User).where(User.role == "worker").order_by(User.full_name)
        )
        workers_list = list(workers.scalars().all())

        result = []
        for worker in workers_list:
            stats = await get_worker_activity_stats(worker.id)
            if stats:
                result.append(stats)

        return result


async def get_checklist_usage_stats(checklist_id: int) -> dict:
    """Получить статистику использования чек-листа."""
    async with async_session() as session:
        checklist = await session.get(Checklist, checklist_id)
        if not checklist:
            return {}

        # Количество вопросов
        questions_result = await session.execute(
            select(Question)
            .where(Question.checklist_id == checklist_id)
            .where(Question.is_deleted == False)
        )
        questions = list(questions_result.scalars().all())
        questions_count = len(questions)

        # Количество отчетов
        reports_result = await session.execute(
            select(func.count(Report.id)).where(Report.checklist_id == checklist_id)
        )
        reports_count = reports_result.scalar() or 0

        # Средний балл
        avg_score_result = await session.execute(
            select(func.avg(Report.score_percent))
            .where(Report.checklist_id == checklist_id)
            .where(Report.score_percent > 0)
        )
        avg_score = avg_score_result.scalar()
        avg_score = int(avg_score) if avg_score else 0

        # Последнее использование
        last_use_result = await session.execute(
            select(Report.created_at)
            .where(Report.checklist_id == checklist_id)
            .order_by(desc(Report.created_at))
            .limit(1)
        )
        last_use_row = last_use_result.first()
        last_use = last_use_row[0] if last_use_row else None

        # Определяем создателя (косвенно через shop_id)
        creator = None
        if checklist.shop_id:
            admin_shops_result = await session.execute(
                select(AdminShop.admin_tg_id)
                .where(AdminShop.shop_name == checklist.shop_id)
                .limit(1)
            )
            admin_tg_id_row = admin_shops_result.first()
            if admin_tg_id_row:
                admin_tg_id = admin_tg_id_row[0]
                admin_user = await session.scalar(
                    select(User).where(User.tg_id == admin_tg_id)
                )
                if admin_user:
                    creator = admin_user.full_name

        return {
            "checklist": checklist,
            "questions_count": questions_count,
            "reports_count": reports_count,
            "avg_score": avg_score,
            "last_use": last_use,
            "creator": creator,
        }


async def get_all_checklists_stats() -> list[dict]:
    """Получить статистику всех чек-листов."""
    async with async_session() as session:
        checklists = await session.execute(select(Checklist).order_by(Checklist.id))
        checklists_list = list(checklists.scalars().all())

        result = []
        for checklist in checklists_list:
            stats = await get_checklist_usage_stats(checklist.id)
            if stats:
                result.append(stats)

        return result


async def get_checklists_shops() -> list[str]:
    """Получить список всех уникальных точек, у которых есть чек-листы."""
    async with async_session() as session:
        result = await session.execute(
            select(Checklist.shop_id)
            .where(Checklist.shop_id.is_not(None))
            .distinct()
            .order_by(Checklist.shop_id)
        )
        shops = [row[0] for row in result.all() if row[0]]
        # Добавляем "Все точки" если есть чек-листы без точки
        checklists_without_shop = await session.scalar(
            select(func.count(Checklist.id)).where(Checklist.shop_id.is_(None))
        )
        if checklists_without_shop and checklists_without_shop > 0:
            shops.insert(0, "Все точки")
        return shops


async def get_checklists_by_shop(shop_id: str | None) -> list[dict]:
    """Получить все чек-листы для конкретной точки с статистикой."""
    async with async_session() as session:
        if shop_id == "Все точки":
            query = select(Checklist).where(Checklist.shop_id.is_(None)).order_by(Checklist.id)
        else:
            query = select(Checklist).where(Checklist.shop_id == shop_id).order_by(Checklist.id)
        
        checklists_result = await session.execute(query)
        checklists = list(checklists_result.scalars().all())

        result = []
        for checklist in checklists:
            stats = await get_checklist_usage_stats(checklist.id)
            if stats:
                result.append(stats)

        return result


async def get_admin_checklists(admin_tg_id: int) -> list[dict]:
    """Получить все чек-листы управленца с статистикой."""
    async with async_session() as session:
        admin = await session.scalar(select(User).where(User.tg_id == admin_tg_id))
        if not admin:
            return []

        # Получаем точки админа
        shops_result = await session.execute(
            select(AdminShop.shop_name).where(AdminShop.admin_tg_id == admin_tg_id)
        )
        admin_shops = [row[0] for row in shops_result.all()]

        if not admin_shops:
            return []

        # Получаем чек-листы для точек админа
        checklists_result = await session.execute(
            select(Checklist).where(Checklist.shop_id.in_(admin_shops)).order_by(Checklist.id)
        )
        checklists = list(checklists_result.scalars().all())

        result = []
        for checklist in checklists:
            stats = await get_checklist_usage_stats(checklist.id)
            if stats:
                result.append(stats)

        return result


async def get_admin_workers(admin_tg_id: int) -> list[dict]:
    """Получить всех сотрудников управленца с статистикой."""
    async with async_session() as session:
        admin = await session.scalar(select(User).where(User.tg_id == admin_tg_id))
        if not admin:
            return []

        # Получаем точки админа
        shops_result = await session.execute(
            select(AdminShop.shop_name).where(AdminShop.admin_tg_id == admin_tg_id)
        )
        admin_shops = [row[0] for row in shops_result.all()]

        if not admin_shops:
            return []

        # Получаем сотрудников точек админа
        workers_result = await session.execute(
            select(User)
            .where(User.role == "worker")
            .where(User.shop_id.in_(admin_shops))
            .order_by(User.full_name)
        )
        workers = list(workers_result.scalars().all())

        result = []
        for worker in workers:
            stats = await get_worker_activity_stats(worker.id)
            if stats:
                result.append(stats)

        return result


async def get_network_overview_stats() -> dict:
    """Получить общую статистику по сети."""
    async with async_session() as session:
        # Общее количество админов
        admins_count_result = await session.execute(
            select(func.count(User.id)).where(User.role == "admin")
        )
        admins_count = admins_count_result.scalar() or 0

        # Общее количество сотрудников
        workers_count_result = await session.execute(
            select(func.count(User.id)).where(User.role == "worker")
        )
        workers_count = workers_count_result.scalar() or 0

        # Общее количество чек-листов
        checklists_count_result = await session.execute(
            select(func.count(Checklist.id))
        )
        checklists_count = checklists_count_result.scalar() or 0

        # Общее количество отчетов
        reports_count_result = await session.execute(select(func.count(Report.id)))
        reports_count = reports_count_result.scalar() or 0

        # Средний балл по всем отчетам
        avg_score_result = await session.execute(
            select(func.avg(Report.score_percent)).where(Report.score_percent > 0)
        )
        avg_score = avg_score_result.scalar()
        avg_score = int(avg_score) if avg_score else 0

        # Отчеты за сегодня
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        reports_today_result = await session.execute(
            select(func.count(Report.id)).where(Report.created_at >= today_start)
        )
        reports_today = reports_today_result.scalar() or 0

        # Отчеты за последние 7 дней
        week_ago = datetime.now() - timedelta(days=7)
        reports_week_result = await session.execute(
            select(func.count(Report.id)).where(Report.created_at >= week_ago)
        )
        reports_week = reports_week_result.scalar() or 0

        # Количество уникальных точек
        shops_count_result = await session.execute(
            select(func.count(func.distinct(User.shop_id)))
            .where(User.role == "worker")
            .where(User.shop_id.is_not(None))
        )
        shops_count = shops_count_result.scalar() or 0

        return {
            "admins_count": admins_count,
            "workers_count": workers_count,
            "checklists_count": checklists_count,
            "reports_count": reports_count,
            "avg_score": avg_score,
            "reports_today": reports_today,
            "reports_week": reports_week,
            "shops_count": shops_count,
        }

