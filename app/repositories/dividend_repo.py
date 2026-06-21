import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.account import Account
from app.models.dividend import Dividend


async def list_for_user(
    session: AsyncSession, clerk_id: str,
    skip: int = 0,
    limit: int = 10,
) -> list[Dividend]:
    stmt = (
        select(Dividend)
        .join(Account, Account.id == Dividend.account_id)
        .where(Account.user_id == clerk_id)
        .options(selectinload(Dividend.asset))
        .order_by(Dividend.date.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_for_account(
    session: AsyncSession, account_id: uuid.UUID,
    skip: int = 0,
    limit: int = 10,
) -> list[Dividend]:
    stmt = (
        select(Dividend)
        .where(Dividend.account_id == account_id)
        .options(selectinload(Dividend.asset))
        .order_by(Dividend.date.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
