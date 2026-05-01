from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.repositories import asset_repo
from app.schemas.asset import AssetCreate, AssetRead

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[AssetRead])
async def list_assets(
    symbol: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await asset_repo.list_all(db, symbol_like=symbol, limit=limit, offset=offset)


@router.post("", response_model=AssetRead, status_code=201)
async def create_asset(
    payload: AssetCreate,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await asset_repo.get_by_symbol(db, payload.symbol)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Asset symbol already exists")
    return await asset_repo.create(db, payload)
