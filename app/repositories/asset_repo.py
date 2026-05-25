import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset, AssetKind
from app.schemas.asset import AssetCreate


async def list_all(
    session: AsyncSession,
    symbol_like: str | None = None,
    kind: AssetKind | None = None,
    currency: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Asset]:
    stmt = select(Asset).order_by(Asset.symbol).limit(limit).offset(offset)
    if symbol_like:
        stmt = stmt.where(Asset.symbol.ilike(f"%{symbol_like}%"))
    if kind is not None:
        stmt = stmt.where(Asset.kind == kind)
    if currency:
        stmt = stmt.where(Asset.currency == currency)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Asset.symbol.ilike(like), Asset.name.ilike(like)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_by_symbol(session: AsyncSession, symbol: str) -> Asset | None:
    """Devuelve el primer asset con ese symbol. Symbols pueden repetirse para
    asset_kind distintos (ej. "A" stock vs "A" fund). Para disambiguar usar
    `get_by_symbol_and_kind`."""
    result = await session.execute(
        select(Asset).where(Asset.symbol == symbol).limit(1)
    )
    return result.scalar_one_or_none()


async def get_by_symbol_and_kind(
    session: AsyncSession, symbol: str, kind: AssetKind
) -> Asset | None:
    result = await session.execute(
        select(Asset).where(Asset.symbol == symbol, Asset.kind == kind)
    )
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, asset_id: uuid.UUID) -> Asset | None:
    result = await session.execute(select(Asset).where(Asset.id == asset_id))
    return result.scalar_one_or_none()


async def get_by_id_with_prices(
    session: AsyncSession, asset_id: uuid.UUID
) -> Asset | None:
    """Estilo Eduardo: detalle por id con prices embebidos (ordenados desc por fecha)."""
    result = await session.execute(
        select(Asset)
        .where(Asset.id == asset_id)
        .options(selectinload(Asset.prices))
    )
    return result.scalar_one_or_none()


async def create(session: AsyncSession, payload: AssetCreate) -> Asset:
    asset = Asset(**payload.model_dump())
    session.add(asset)
    await session.commit()
    await session.refresh(asset)
    return asset
