from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import user_preference_repo
from app.schemas.user_preference import UserPreferenceRead, UserPreferenceUpdate
from scripts.warnings_module import warnings as recalc_warnings

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=UserPreferenceRead)
async def get_preferences(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pref = await user_preference_repo.get_for_user(db, user.clerk_id)
    if pref is None:
        raise HTTPException(status_code=404, detail="Preferences not set")
    return pref


@router.put("", response_model=UserPreferenceRead)
async def upsert_preferences(
    payload: UserPreferenceUpdate,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Crea si no existe; actualiza solo los campos enviados si existe.

    También recalcula las alertas/warnings del usuario con los nuevos umbrales.
    """
    pref = await user_preference_repo.upsert_for_user(db, user.clerk_id, payload)
    await recalc_warnings(db, user.clerk_id, send_mail=False)
    return pref
