from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import user_repo
from app.schemas.user import RiskProfileUpdate, UserRead

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=UserRead)
async def get_profile(user: Profile = Depends(get_current_user)) -> Profile:
    return user


@router.put("", response_model=UserRead)
async def update_profile(
    payload: RiskProfileUpdate,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Profile:
    """PUT /profile del doc — hoy solo permite editar risk_profile (lo único
    mutable en profiles aparte de email que viene de Clerk)."""
    return await user_repo.update_risk_profile(db, user, payload.risk_profile)
