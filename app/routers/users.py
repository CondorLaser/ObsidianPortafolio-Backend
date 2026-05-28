from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.repositories import user_repo
from app.schemas.user import RiskProfileUpdate

router = APIRouter(prefix="/users", tags=["users"])

@router.patch("/me/risk-profile")
async def update_risk_profile(
    payload: RiskProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await user_repo.update_risk_profile(
        db,
        user.clerk_id,
        payload.risk_profile,
    )