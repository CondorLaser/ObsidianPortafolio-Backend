from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.repositories import dividend_repo
from app.schemas.dividend import DividendRead

router = APIRouter(prefix="/dividends", tags=["dividends"])


@router.get("", response_model=list[DividendRead])
async def list_dividends(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await dividend_repo.list_for_user(db, user.id)
