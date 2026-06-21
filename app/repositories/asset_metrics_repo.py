import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset_metrics import AssetDailyMetric, AssetMonthlyMetric


async def get_latest_daily_metric(
    session: AsyncSession, asset_id: uuid.UUID
) -> AssetDailyMetric | None:
    result = await session.execute(
        select(AssetDailyMetric)
        .where(AssetDailyMetric.asset_id == asset_id)
        .order_by(desc(AssetDailyMetric.date))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_monthly_metric(
    session: AsyncSession, asset_id: uuid.UUID
) -> AssetMonthlyMetric | None:
    result = await session.execute(
        select(AssetMonthlyMetric)
        .where(AssetMonthlyMetric.asset_id == asset_id)
        .order_by(desc(AssetMonthlyMetric.date))
        .limit(1)
    )
    return result.scalar_one_or_none()