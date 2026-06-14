import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import alert_repo
from app.schemas.alert import AlertRead, AlertUpdate

router = APIRouter(prefix="/warnings", tags=["warnings"])


@router.get("", response_model=list[AlertRead])
async def list_warnings(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    is_read: bool | None = Query(None, description="Filtrar por avisos leídos"),
    is_active: bool | None = Query(None, description="Filtrar por avisos activos"),
):
    return await alert_repo.list_for_user(
        db,
        clerk_id=user.clerk_id,
        is_read=is_read,
        is_active=is_active,
    )


@router.patch("/{alert_id}", response_model=AlertRead)
async def update_warning(
    alert_id: uuid.UUID,
    payload: AlertUpdate,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    alert = await alert_repo.update_for_user(db, user.clerk_id, alert_id, payload)
    if alert is None:
        raise HTTPException(status_code=404, detail="Warning not found")
    return alert
