import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import account_repo
from app.schemas.account import AccountCreate, AccountDetailRead, AccountRead

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountRead])
async def list_accounts(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await account_repo.list_for_user(db, user.clerk_id)


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
