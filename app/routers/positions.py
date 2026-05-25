from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import position_repo
from app.schemas.position import PositionRead

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("", response_model=list[PositionRead])
async def list_positions(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await position_repo.list_for_user(db, user.clerk_id)
