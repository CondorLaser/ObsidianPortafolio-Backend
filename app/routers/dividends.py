from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import dividend_repo
from app.schemas.dividend import DividendRead

router = APIRouter(prefix="/dividends", tags=["dividends"])


@router.get("", response_model=list[DividendRead])
async def list_dividends(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Máx. registros retornar"),
):
    return await dividend_repo.list_for_user(db, user.clerk_id, skip=skip, limit=limit)
