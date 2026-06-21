import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.asset import AssetKind
from app.repositories import asset_repo
from app.schemas.asset import AssetCreate, AssetDetailRead, AssetRead
from app.repositories import asset_metrics_repo
from app.schemas.asset_metrics import AssetDailyMetricRead, AssetMonthlyMetricRead

router = APIRouter(prefix="/assets", tags=["assets"])

# Obtener todos los Assets (filtros y paginación)
@router.get("", response_model=list[AssetRead])
async def list_assets(
    symbol: str | None = Query(default=None, description="exact match"),
    kind: AssetKind | None = Query(default=None),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    search: str | None = Query(default=None, description="ilike sobre symbol o name"),
    limit: int = Query(default=100, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """`symbol` es exact match (no ilike).
    Para búsqueda fuzzy usar `search` (ilike sobre symbol o name)."""
    return await asset_repo.list_all(
        db,
        symbol_exact=symbol,
        kind=kind,
        currency=currency,
        search=search,
        limit=limit,
        skip=skip,
    )


@router.get("/{asset_id}", response_model=AssetDetailRead)
async def get_asset(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """detalle por "asset_id" con prices embebidos."""
    asset = await asset_repo.get_by_id_with_prices(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.post("", response_model=AssetRead, status_code=201)
async def create_asset(
    payload: AssetCreate,
    db: AsyncSession = Depends(get_db),
):
    existing = await asset_repo.get_by_symbol(db, payload.symbol)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Asset symbol already exists")
    return await asset_repo.create(db, payload)

# Retorna la última (más reciente) métrica diaria del asset
@router.get("/metrics/daily/{asset_id}", response_model=AssetDailyMetricRead)
async def get_asset_daily_metrics(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    metric = await asset_metrics_repo.get_latest_daily_metric(db, asset_id)
    if metric is None:
        raise HTTPException(status_code=404, detail="No daily metrics found for this asset")
    return metric

# Retorna la última (más reciente) métrica mensual del asset
@router.get("/metrics/monthly/{asset_id}", response_model=AssetMonthlyMetricRead)
async def get_asset_monthly_metrics(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    metric = await asset_metrics_repo.get_latest_monthly_metric(db, asset_id)
    if metric is None:
        raise HTTPException(status_code=404, detail="No monthly metrics found for this asset")
    return metric