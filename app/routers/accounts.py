import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

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
):
    return await account_repo.list_for_user(db, user.clerk_id)


# Las rutas nested (/accounts/<sub>/{id}) van ANTES de /{account_id} para que
# FastAPI no las matchee con el path catch-all del detail.

@router.get("/{account_id}/metrics")
async def get_metrics(
    account_id: uuid.UUID,
    _user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    daily_result = await db.execute(
        text("""
            SELECT *
            FROM account_daily_metrics
            WHERE account_id = :account_id
            ORDER BY date DESC
        """),
        {"account_id": str(account_id)},
    )

    monthly_result = await db.execute(
        text("""
            SELECT *
            FROM account_monthly_metrics
            WHERE account_id = :account_id
            ORDER BY date DESC
        """),
        {"account_id": str(account_id)},
    )

    return {
        "daily": [dict(row._mapping) for row in daily_result],
        "monthly": [dict(row._mapping) for row in monthly_result],
    }

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
):
    account = await account_repo.get_for_user_with_detail(db, user.clerk_id, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account.transactions


@router.get("/dividends/{account_id}", response_model=list[DividendRead])
async def get_account_dividends(
    account_id: uuid.UUID,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await account_repo.get_for_user_with_detail(db, user.clerk_id, account_id)
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
