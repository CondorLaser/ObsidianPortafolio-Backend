"""Endpoints bajo /user/* del doc de frontend.

Alias y vistas livianas sobre profile + accounts. Las rutas canónicas viven en
/profile (PATCH /profile/risk-profile) y /accounts (GET /accounts); estas las
duplican con shapes específicas que el frontend está mockeando.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import account_repo, user_repo
from app.schemas.account_name import AccountNameRead, AccountNameRename
from app.schemas.user import RiskProfileUpdate

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/risk_profile")
async def get_risk_profile(user: Profile = Depends(get_current_user)) -> dict:
    """{risk_profile: 'moderate' | 'conservative' | 'agressive' | null}."""
    return {"risk_profile": user.risk_profile.value if user.risk_profile else None}


@router.put("/risk_profile")
async def update_risk_profile_alias(
    payload: RiskProfileUpdate,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Alias del canónico PATCH /profile/risk-profile, con shape de respuesta
    pequeña esperada por el frontend."""
    updated = await user_repo.update_risk_profile(db, user, payload.risk_profile)
    return {"risk_profile": updated.risk_profile.value if updated.risk_profile else None}


@router.get("/accounts_names", response_model=list[AccountNameRead])
async def list_accounts_names(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Vista liviana: solo (id, name) de cada cuenta del usuario."""
    return await account_repo.list_for_user(db, user.clerk_id)


@router.put("/accounts_names", response_model=list[AccountNameRead])
async def rename_accounts(
    payload: list[AccountNameRename],
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rename en batch: body = [{id, name}, ...]. Devuelve los renombrados."""
    renamed = []
    for item in payload:
        account = await account_repo.rename(db, user.clerk_id, item.id, item.name)
        if account is None:
            raise HTTPException(
                status_code=404,
                detail=f"Account {item.id} not found",
            )
        renamed.append(account)
    return renamed
