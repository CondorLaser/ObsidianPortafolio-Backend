import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account_metrics import AccountDailyMetric, AccountMonthlyMetric


async def list_daily_for_account(
    session: AsyncSession, account_id: uuid.UUID
) -> list[AccountDailyMetric]:
    result = await session.execute(
        select(AccountDailyMetric)
        .where(AccountDailyMetric.account_id == account_id)
        .order_by(AccountDailyMetric.date.desc())
    )
    return list(result.scalars().all())


async def list_monthly_for_account(
    session: AsyncSession, account_id: uuid.UUID
) -> list[AccountMonthlyMetric]:
    result = await session.execute(
        select(AccountMonthlyMetric)
        .where(AccountMonthlyMetric.account_id == account_id)
        .order_by(AccountMonthlyMetric.date.desc())
    )
    return list(result.scalars().all())
