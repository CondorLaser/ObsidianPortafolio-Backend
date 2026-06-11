import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.account import Account
from app.models.position import Position
from app.models.transaction import Transaction
from app.models.dividend import Dividend
from app.schemas.account import AccountCreate


async def list_for_user(
    session: AsyncSession, clerk_id: str,
    skip: int = 0,
    limit: int = 10,
) -> list[Account]:
    """ORDER BY created_at DESC — matchea contrato Eduardo (más reciente primero)."""
    result = await session.execute(
        select(Account)
        .where(Account.user_id == clerk_id)
        .order_by(Account.created_at.desc())
        .offset(skip)
        .limit(limit)
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


async def rename(
    session: AsyncSession,
    clerk_id: str,
    account_id: uuid.UUID,
    new_name: str,
) -> Account | None:
    """Renombra una cuenta si pertenece al usuario. Devuelve None si no es del user."""
    account = await get_for_user(session, clerk_id, account_id)
    if account is None:
        return None
    account.name = new_name
    await session.commit()
    await session.refresh(account)
    return account


async def get_positions_by_account(
    session: AsyncSession,
    clerk_id: str,
    account_id: uuid.UUID,
    skip: int = 0,
    limit: int = 10,
) -> list[Position] | None:
    # Verificar que la cuenta exista y sea del usuario
    account_exists = await session.execute(
        select(Account.id).where(
            Account.id == account_id, Account.user_id == clerk_id
        )
    )
    if not account_exists.scalar_one_or_none():
        return None
    # Obtener Positions paginadas + ordenadas
    result = await session.execute(
        select(Position)
        .join(Account, Account.id == Position.account_id)
        .where(Position.account_id == account_id)
        .options(selectinload(Position.asset))
        .order_by(Position.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_transactions_by_account(
    session: AsyncSession,
    clerk_id: str,
    account_id: uuid.UUID,
    skip: int = 0,
    limit: int = 10,
) -> list[Position] | None:
    # Verificar que la cuenta exista y sea del usuario
    account_exists = await session.execute(
        select(Account.id).where(
            Account.id == account_id, Account.user_id == clerk_id
        )
    )
    if not account_exists.scalar_one_or_none():
        return None
    # Obtener Transactions paginadas + ordenadas
    result = await session.execute(
        select(Transaction)
        .where(Transaction.account_id == account_id)
        .options(selectinload(Transaction.asset))
        .order_by(Transaction.executed_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())

async def get_dividends_by_account(
    session: AsyncSession,
    clerk_id: str,
    account_id: uuid.UUID,
    skip: int = 0,
    limit: int = 10,
) -> list[Position] | None:
    # Verificar que la cuenta exista y sea del usuario
    account_exists = await session.execute(
        select(Account.id).where(
            Account.id == account_id, Account.user_id == clerk_id
        )
    )
    if not account_exists.scalar_one_or_none():
        return None
    # Obtener Dividends paginadas + ordenadas
    result = await session.execute(
        select(Dividend)
        .where(Dividend.account_id == account_id)
        .options(selectinload(Dividend.asset))
        .order_by(Dividend.date.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())