import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.asset import AssetKind
from app.models.user import Profile
from app.repositories import asset_repo
from app.schemas.asset import AssetCreate, AssetDetailRead, AssetRead

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[AssetRead])
async def list_assets(
    symbol: str | None = Query(default=None, description="exact match (Eduardo)"),
    kind: AssetKind | None = Query(default=None),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    search: str | None = Query(default=None, description="ilike sobre symbol o name"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """1:1 con contrato Eduardo: `symbol` es exact match (no ilike).
    Para búsqueda fuzzy usar `search` (ilike sobre symbol o name)."""
    return await asset_repo.list_all(
        db,
        symbol_exact=symbol,
        kind=kind,
        currency=currency,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/{asset_id}", response_model=AssetDetailRead)
async def get_asset(
    asset_id: uuid.UUID,
    _user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Estilo Eduardo: detalle por UUID con prices embebidos."""
    asset = await asset_repo.get_by_id_with_prices(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset

# Nota Eduardo: Yo prefiero hacer consultas SQL manuales, personalmente lo encuentro más cómodo
@router.get("/{asset_id}/metrics/daily")
async def get_metric(
    asset_id: uuid.UUID,
    _user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = text("""
        SELECT *
        FROM asset_daily_metrics
        WHERE asset_id = :asset_id
        ORDER BY date DESC
    """)

    result = await db.execute(
        query,
        {"asset_id": str(asset_id)},
    )

    return [dict(row._mapping) for row in result]

@router.get("/{asset_id}/metrics/monthly")
async def get_metric(
    asset_id: uuid.UUID,
    _user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = text("""
        SELECT *
        FROM asset_monthly_metrics
        WHERE asset_id = :asset_id
        ORDER BY date DESC
    """)

    result = await db.execute(
        query,
        {"asset_id": str(asset_id)},
    )

    return [dict(row._mapping) for row in result]

@router.post("", response_model=AssetRead, status_code=201)
async def create_asset(
    payload: AssetCreate,
    _user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await asset_repo.get_by_symbol(db, payload.symbol)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Asset symbol already exists")
    return await asset_repo.create(db, payload)
