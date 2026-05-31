"""Endpoint de onboarding del doc: POST /risk_profile en root.

Setea (o actualiza) el risk_profile del usuario actual. Funcionalmente
equivalente a PATCH /profile/risk-profile y PUT /user/risk_profile, pero
expuesto en path simple para el flujo de onboarding del frontend.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import user_repo
from app.schemas.user import RiskProfileUpdate

router = APIRouter(tags=["onboarding"])


@router.post("/risk_profile")
async def post_risk_profile(
    payload: RiskProfileUpdate,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    updated = await user_repo.update_risk_profile(db, user, payload.risk_profile)
    return {"risk_profile": updated.risk_profile.value if updated.risk_profile else None}
