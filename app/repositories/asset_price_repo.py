import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset_price import AssetPrice
from app.schemas.asset_price import AssetPriceCreate


async def list_range(
    session: AsyncSession,
    asset_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[AssetPrice]:
    stmt = select(AssetPrice).where(AssetPrice.asset_id == asset_id)
    if date_from is not None:
        stmt = stmt.where(AssetPrice.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(AssetPrice.date <= date_to)
    stmt = stmt.order_by(AssetPrice.date)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def upsert(
    session: AsyncSession,
    asset_id: uuid.UUID,
    payload: AssetPriceCreate,
) -> AssetPrice:
    values = {"asset_id": asset_id, **payload.model_dump()}
    stmt = (
        insert(AssetPrice)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["asset_id", "date"],
            set_={
                "close": values["close"],
                "currency": values["currency"],
                "source": values["source"],
            },
        )
    )
    await session.execute(stmt)
    await session.commit()
    result = await session.execute(
        select(AssetPrice).where(
            AssetPrice.asset_id == asset_id,
            AssetPrice.date == payload.date,
        )
    )
    return result.scalar_one()
