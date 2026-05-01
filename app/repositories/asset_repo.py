from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.schemas.asset import AssetCreate


async def list_all(
    session: AsyncSession,
    symbol_like: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Asset]:
    stmt = select(Asset).order_by(Asset.symbol).limit(limit).offset(offset)
    if symbol_like:
        stmt = stmt.where(Asset.symbol.ilike(f"%{symbol_like}%"))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_by_symbol(session: AsyncSession, symbol: str) -> Asset | None:
    result = await session.execute(select(Asset).where(Asset.symbol == symbol))
    return result.scalar_one_or_none()


async def create(session: AsyncSession, payload: AssetCreate) -> Asset:
    asset = Asset(**payload.model_dump())
    session.add(asset)
    await session.commit()
    await session.refresh(asset)
    return asset
