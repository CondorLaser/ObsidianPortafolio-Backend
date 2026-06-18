import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import account_metrics_repo, account_repo
from app.schemas.account import AccountCreate, AccountDetailRead, AccountRead
from app.schemas.account_metrics import AccountMetricsRead
from app.schemas.dividend import DividendRead
from app.schemas.position import PositionRead
from app.schemas.transaction import TransactionRead

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountRead])
async def list_accounts(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Máx. registros retornar"),
):
    return await account_repo.list_for_user(db, user.clerk_id, skip=skip, limit=limit)


# Las rutas nested (/accounts/<sub>/{id}) van ANTES de /{account_id} para que
# FastAPI no las matchee con el path catch-all del detail.

@router.get("/metrics/{account_id}", response_model=AccountMetricsRead)
async def get_account_metrics(
    account_id: uuid.UUID,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Obtiene solo el par de últimas metricas daily y monthly para esa cuenta

    # Validación de la cuenta
    if await account_repo.get_for_user(db, user.clerk_id, account_id) is None:
        raise HTTPException(status_code=404, detail="Account not found")
    # Obtener metricas
    latest_daily = await account_metrics_repo.get_latest_daily_metric_for_account(db, account_id)
    latest_monthly = await account_metrics_repo.get_latest_monthly_metric_for_account(db, account_id)
    return AccountMetricsRead(daily=latest_daily, monthly=latest_monthly)


@router.post("/metrics/daily")
async def post_daily_account_metrics(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Recalcula (idempotente) las métricas diarias de TODAS las cuentas del user.
    # Pensado para llamarse tras subir un PDF (ver routers/pdf.py), como espejo
    # de post_daily_portfolio_metrics.
    n = await account_metrics_repo.compute_and_store_daily_for_user(db, user.clerk_id)
    return {"accounts_updated": n}


@router.post("/metrics/monthly")
async def post_monthly_account_metrics(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Recalcula (idempotente) las métricas mensuales de TODAS las cuentas del user.
    n = await account_metrics_repo.compute_and_store_monthly_for_user(db, user.clerk_id)
    return {"accounts_updated": n}


@router.get("/positions/{account_id}", response_model=list[PositionRead])
async def get_account_positions(
    account_id: uuid.UUID,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Máx. registros retornar"),
):
    account_positions = await account_repo.get_positions_by_account(db, user.clerk_id, account_id, skip=skip, limit=limit)
    if account_positions is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account_positions


@router.get("/transactions/{account_id}", response_model=list[TransactionRead])
async def get_account_transactions(
    account_id: uuid.UUID,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Máx. registros retornar"),
):
    account_transactions = await account_repo.get_transactions_by_account(db, user.clerk_id, account_id, skip=skip, limit=limit)
    if account_transactions is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account_transactions


@router.get("/dividends/{account_id}", response_model=list[DividendRead])
async def get_account_dividends(
    account_id: uuid.UUID,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Máx. registros retornar"),
):
    account_dividends = await account_repo.get_dividends_by_account(db, user.clerk_id, account_id, skip=skip, limit=limit)
    if account_dividends is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account_dividends


@router.get("/{account_id}", response_model=AccountRead)
async def get_account(
    account_id: uuid.UUID,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await account_repo.get_for_user(db, user.clerk_id, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.post("", response_model=AccountRead, status_code=201)
async def create_account(
    payload: AccountCreate,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await account_repo.create(db, user.clerk_id, payload)
