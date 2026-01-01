from __future__ import annotations

from sqlalchemy import delete, select

from app.db import async_session
from app.models import AdminShop, User


async def get_user(tg_id: int) -> User | None:
    async with async_session() as session:
        return await session.scalar(select(User).where(User.tg_id == tg_id))


async def get_user_by_pk(user_id: int) -> User | None:
    async with async_session() as session:
        return await session.get(User, user_id)


async def add_user(
    tg_id: int,
    full_name: str,
    role: str,
    shop_id: str,
    position: str,
) -> None:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if user:
            return

        session.add(
            User(
                tg_id=tg_id,
                full_name=full_name,
                role=role,
                shop_id=shop_id,
                position=position,
            )
        )
        await session.commit()


async def add_admin_shop(admin_tg_id: int, shop_name: str) -> None:
    """Attach a shop to an admin (avoids duplicates)."""
    async with async_session() as session:
        exists = await session.scalar(
            select(AdminShop).where(
                (AdminShop.admin_tg_id == admin_tg_id) & (AdminShop.shop_name == shop_name)
            )
        )
        if exists:
            return

        session.add(AdminShop(admin_tg_id=admin_tg_id, shop_name=shop_name))
        await session.commit()


async def get_admin_shops(admin_tg_id: int) -> list[str]:
    """Return all shop names attached to the admin."""
    async with async_session() as session:
        result = await session.execute(
            select(AdminShop.shop_name).where(AdminShop.admin_tg_id == admin_tg_id)
        )
        return list(result.scalars().all())


async def update_user(user_id: int, full_name: str | None = None, tg_id: int | None = None) -> bool:
    """Обновить данные пользователя."""
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return False

        if full_name is not None:
            user.full_name = full_name
        if tg_id is not None:
            # Проверяем, что новый tg_id не занят другим пользователем
            existing_user = await session.scalar(select(User).where(User.tg_id == tg_id))
            if existing_user and existing_user.id != user_id:
                return False
            # Если это админ, обновляем admin_shops
            if user.role == "admin":
                old_tg_id = user.tg_id
                user.tg_id = tg_id
                # Обновляем admin_shops
                from sqlalchemy import update
                await session.execute(
                    update(AdminShop)
                    .where(AdminShop.admin_tg_id == old_tg_id)
                    .values(admin_tg_id=tg_id)
                )
            else:
                user.tg_id = tg_id

        await session.commit()
        return True


async def delete_user(user_id: int) -> bool:
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return False

        if user.role == "admin":
            await session.execute(delete(AdminShop).where(AdminShop.admin_tg_id == user.tg_id))

        await session.delete(user)
        await session.commit()
        return True


async def get_all_positions() -> list[str]:
    async with async_session() as session:
        query = select(User.position).where(User.role == "worker").distinct()
        result = await session.execute(query)
        return list(result.scalars().all())


async def get_all_workers() -> list[User]:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.role == "worker"))
        return list(result.scalars().all())


async def get_all_shops() -> list[str]:
    async with async_session() as session:
        result = await session.execute(
            select(User.shop_id).where(User.shop_id.is_not(None)).distinct()
        )
        return [s for s in result.scalars().all() if s]


async def get_all_worker_shops() -> list[str]:
    """Get all unique shop IDs that have workers assigned."""
    async with async_session() as session:
        result = await session.execute(
            select(User.shop_id)
            .where(User.role == "worker")
            .where(User.shop_id.is_not(None))
            .distinct()
        )
        return sorted([s for s in result.scalars().all() if s])


async def get_all_admins() -> list[User]:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.role == "admin").order_by(User.full_name)
        )
        return list(result.scalars().all())


async def get_employees_by_shop(shop_id: str) -> list[User]:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.shop_id == shop_id).order_by(User.full_name)
        )
        return list(result.scalars().all())


async def get_employees_with_reports() -> list[User]:
    # NOTE: implemented in reports.py to avoid circular joins.
    from app.models import Report

    async with async_session() as session:
        query = select(User).join(Report, User.id == Report.user_id).distinct()
        result = await session.execute(query)
        return list(result.scalars().all())
