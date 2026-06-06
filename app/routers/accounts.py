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
    """Métricas (daily + monthly) de una cuenta. Tablas existen pero hoy están
    vacías; el cómputo es trabajo pendiente."""
    if await account_repo.get_for_user(db, user.clerk_id, account_id) is None:
        raise HTTPException(status_code=404, detail="Account not found")
    daily = await account_metrics_repo.list_daily_for_account(db, account_id)
    monthly = await account_metrics_repo.list_monthly_for_account(db, account_id)
    return AccountMetricsRead(daily=daily, monthly=monthly)


@router.get("/positions/{account_id}", response_model=list[PositionRead])
async def get_account_positions(
    account_id: uuid.UUID,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await account_repo.get_for_user_with_detail(db, user.clerk_id, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account.positions


@router.get("/transactions/{account_id}", response_model=list[TransactionRead])
async def get_account_transactions(
    account_id: uuid.UUID,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Máx. registros retornar"),
):
    account = await account_repo.get_for_user_with_detail(db, user.clerk_id, account_id, skip=skip, limit=limit)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account.transactions


@router.get("/dividends/{account_id}", response_model=list[DividendRead])
async def get_account_dividends(
    account_id: uuid.UUID,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Máx. registros retornar"),
):
    account = await account_repo.get_for_user_with_detail(db, user.clerk_id, account_id, skip=skip, limit=limit)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account.dividends


@router.get("/{account_id}", response_model=AccountDetailRead)
async def get_account(
    account_id: uuid.UUID,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await account_repo.get_for_user_with_detail(db, user.clerk_id, account_id)
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
