from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.asset import AssetKind
from app.models.user import User
from app.repositories import asset_repo
from app.schemas.asset import AssetCreate, AssetRead

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[AssetRead])
async def list_assets(
    symbol: str | None = Query(default=None, description="filtro ilike sobre symbol"),
    kind: AssetKind | None = Query(default=None),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    search: str | None = Query(default=None, description="ilike sobre symbol o name"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await asset_repo.list_all(
        db,
        symbol_like=symbol,
        kind=kind,
        currency=currency,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/{symbol}", response_model=AssetRead)
async def get_asset(
    symbol: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await asset_repo.get_by_symbol(db, symbol)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


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
