import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.account import Account
from app.schemas.account import AccountCreate


async def list_for_user(session: AsyncSession, user_id: uuid.UUID) -> list[Account]:
    result = await session.execute(
        select(Account).where(Account.user_id == user_id).order_by(Account.created_at)
    )
    return list(result.scalars().all())


async def create(
    session: AsyncSession,
    user_id: uuid.UUID,
    payload: AccountCreate,
) -> Account:
    account = Account(user_id=user_id, **payload.model_dump())
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


async def get_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
) -> Account | None:
    result = await session.execute(
        select(Account).where(
            Account.id == account_id, Account.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def get_for_user_with_detail(
    session: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
) -> Account | None:
    result = await session.execute(
        select(Account)
        .where(Account.id == account_id, Account.user_id == user_id)
        .options(
            selectinload(Account.transactions),
            selectinload(Account.dividends),
        )
    )
    return result.scalar_one_or_none()
