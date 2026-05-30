import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import position_repo
from app.schemas.position import PositionDerived

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("", response_model=list[PositionDerived])
async def list_positions(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await position_repo.list_for_user(db, user.clerk_id)

@router.get("/{position_id}/metrics")
async def get_metrics(
    position_id: uuid.UUID,
    _user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    daily_result = await db.execute(
        text("""
            SELECT *
            FROM position_daily_metrics
            WHERE position_id = :position_id
            ORDER BY date DESC
        """),
        {"position_id": str(position_id)},
    )

    return {
        "daily": [dict(row._mapping) for row in daily_result]
    }