from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import position_repo
from app.schemas.position import PositionDerived, PositionRead
import uuid

router = APIRouter(prefix="/positions", tags=["positions"])

# Obtener las positions no materializadas (realiza cálculos en el momento)
@router.get("/portfolio", response_model=list[PositionDerived])
async def list_positions_portfolio(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Máx. registros retornar"),
):
    return await position_repo.list_for_user_portfolio(db, user.clerk_id, skip=skip, limit=limit)

# Obtener posiciones de un asset específico
@router.get("/asset/{asset_id}", response_model=PositionRead | None)
async def get_position_by_asset(
    asset_id: uuid.UUID,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # El front consume esto como UN objeto (detalle de activo), no una lista.
    return await position_repo.get_for_user_and_asset(db, user.clerk_id, asset_id)

# Obtener positions materializadas (BD) (no calcula en el momento, solo trae de BD)
@router.get("", response_model=list[PositionRead])
async def list_positions(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Máx. registros retornar"),
):
    return await position_repo.list_for_user(db, user.clerk_id, skip=skip, limit=limit)
