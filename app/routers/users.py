from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import user_repo
from app.schemas.user import RiskProfileUpdate, UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def me(user: Profile = Depends(get_current_user)) -> Profile:
    return user


@router.patch("/me/risk-profile", response_model=UserRead)
async def update_risk_profile(
    payload: RiskProfileUpdate,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Profile:
    return await user_repo.update_risk_profile(db, user, payload.risk_profile)
