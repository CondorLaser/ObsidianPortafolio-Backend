from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import portfolio_repo
from app.schemas.portfolio import PortfolioDashboard

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class RebuildResult(BaseModel):
    snapshots_persisted: int
    positions_persisted: int


@router.get("/dashboard", response_model=PortfolioDashboard)
async def get_dashboard(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    trend_from: date_type | None = Query(
        None, description="Filtra el trend desde esta fecha inclusive (YYYY-MM-DD)."
    ),
    trend_to: date_type | None = Query(
        None, description="Filtra el trend hasta esta fecha inclusive (YYYY-MM-DD)."
    ),
):
    return await portfolio_repo.get_dashboard_data(
        db, user.clerk_id, trend_from=trend_from, trend_to=trend_to,
    )


@router.post("/rebuild", response_model=RebuildResult)
async def rebuild_portfolio(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Pensado para llamar después de subir un PDF, antes del cron diario.
    # Sync porque a 3-7s por user es aceptable y simplifica vs background tasks.
    snaps, pos = await portfolio_repo.compute_user_series(db, user.clerk_id)
    n_snaps = await portfolio_repo.replace_snapshots(db, user.clerk_id, snaps)
    n_pos = await portfolio_repo.replace_positions(db, user.clerk_id, pos)
    return RebuildResult(snapshots_persisted=n_snaps, positions_persisted=n_pos)
