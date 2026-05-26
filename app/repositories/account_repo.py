import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.account import Account
from app.schemas.account import AccountCreate


async def list_for_user(session: AsyncSession, clerk_id: str) -> list[Account]:
    """ORDER BY created_at DESC — matchea contrato Eduardo (más reciente primero)."""
    result = await session.execute(
        select(Account)
        .where(Account.user_id == clerk_id)
        .order_by(Account.created_at.desc())
    )
    return list(result.scalars().all())


async def create(
    session: AsyncSession,
    clerk_id: str,
    payload: AccountCreate,
) -> Account:
    account = Account(user_id=clerk_id, **payload.model_dump())
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


async def get_for_user(
    session: AsyncSession,
    clerk_id: str,
    account_id: uuid.UUID,
) -> Account | None:
    result = await session.execute(
        select(Account).where(
            Account.id == account_id, Account.user_id == clerk_id
        )
    )
    return result.scalar_one_or_none()


async def get_for_user_with_detail(
    session: AsyncSession,
    clerk_id: str,
    account_id: uuid.UUID,
) -> Account | None:
    """Detalle 1:1 con contrato Eduardo: incluye dividends + positions +
    transactions vía selectinload."""
    result = await session.execute(
        select(Account)
        .where(Account.id == account_id, Account.user_id == clerk_id)
        .options(
            selectinload(Account.transactions),
            selectinload(Account.dividends),
            selectinload(Account.positions),
        )
    )
    return result.scalar_one_or_none()
