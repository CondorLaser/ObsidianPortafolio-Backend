from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.repositories import asset_price_repo, asset_repo
from app.schemas.asset_price import AssetPriceCreate, AssetPriceRead

router = APIRouter(prefix="/assets", tags=["prices"])


@router.get("/{symbol}/prices", response_model=list[AssetPriceRead])
async def list_prices(
    symbol: str,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await asset_repo.get_by_symbol(db, symbol)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return await asset_price_repo.list_range(db, asset.id, date_from, date_to)


@router.post("/{symbol}/prices", response_model=AssetPriceRead, status_code=201)
async def upsert_price(
    symbol: str,
    payload: AssetPriceCreate,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await asset_repo.get_by_symbol(db, symbol)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return await asset_price_repo.upsert(db, asset.id, payload)
