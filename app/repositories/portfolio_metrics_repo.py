import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def get_latest_daily_metric(
    session: AsyncSession,
    clerk_id: str,
) -> dict | None:
    """Retorna la última (más reciente) métrica diaria del portafolio del usuario."""
    result = await session.execute(
        text("""
            SELECT pdm.*
            FROM portfolio_daily_metrics pdm
            WHERE pdm.user_id = :user_id
            ORDER BY pdm.date DESC
            LIMIT 1
        """),
        {"user_id": clerk_id},
    )
    return result.mappings().first()


async def get_latest_monthly_metric(
    session: AsyncSession,
    clerk_id: str,
) -> dict | None:
    """Retorna la última (más reciente) métrica mensual del portafolio del usuario."""
    result = await session.execute(
        text("""
            SELECT pmm.*
            FROM portfolio_monthly_metrics pmm
            WHERE pmm.user_id = :user_id
            ORDER BY pmm.date DESC
            LIMIT 1
        """),
        {"user_id": clerk_id},
    )
    return result.mappings().first()