from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate


async def list_for_user(
    session: AsyncSession, clerk_id: str
) -> list[Transaction]:
    stmt = (
        select(Transaction)
        .join(Account, Account.id == Transaction.account_id)
        .where(Account.user_id == clerk_id)
        .order_by(Transaction.executed_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_for_user(
    session: AsyncSession,
    clerk_id: str,
    payload: TransactionCreate,
) -> Transaction | None:
    owns_account = await session.execute(
        select(Account.id).where(
            Account.id == payload.account_id, Account.user_id == clerk_id
        )
    )
    if owns_account.scalar_one_or_none() is None:
        return None

    tx = Transaction(**payload.model_dump())
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx
