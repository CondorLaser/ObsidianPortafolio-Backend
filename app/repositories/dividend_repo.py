import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.dividend import Dividend


async def list_for_user(
    session: AsyncSession, clerk_id: str
) -> list[Dividend]:
    stmt = (
        select(Dividend)
        .join(Account, Account.id == Dividend.account_id)
        .where(Account.user_id == clerk_id)
        .order_by(Dividend.date.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_for_account(
    session: AsyncSession, account_id: uuid.UUID
) -> list[Dividend]:
    stmt = (
        select(Dividend)
        .where(Dividend.account_id == account_id)
        .order_by(Dividend.date.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
