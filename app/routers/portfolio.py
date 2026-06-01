from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import portfolio_repo
from app.schemas.portfolio import PortfolioDashboard

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class RebuildResult(BaseModel):
    """Response de POST /portfolio/rebuild."""

    snapshots_persisted: int
    positions_persisted: int


@router.get("/dashboard", response_model=PortfolioDashboard)
async def get_dashboard(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard agregado del portafolio del usuario.

    Combina:
    - summary: último snapshot (total_value, invested, pnl, retorno vs anterior)
    - trend: serie histórica completa (date + total_value)
    - account_distribution: peso de cada cuenta sobre el total en el último snapshot
    - positions: posiciones derivadas en runtime desde transactions + asset_prices

    Si el user no tiene snapshots todavía (job no corrió), devuelve summary en
    cero pero positions derivadas (que sí se calculan on-the-fly).
    """
    return await portfolio_repo.get_dashboard_data(db, user.clerk_id)


@router.post("/rebuild", response_model=RebuildResult)
async def rebuild_portfolio(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Recomputa snapshots + positions del user al instante.

    Pensado para que el frontend lo dispare después de subir un PDF (cuando
    se crearon transactions nuevas y el cron diario todavía no corrió).

    Sync: espera ~3-7s en Neon para un user típico. Idempotente (DELETE +
    INSERT scoped por user). Scoped al `clerk_id` del JWT — nunca toca otro
    user.
    """
    snaps, pos = await portfolio_repo.compute_user_series(db, user.clerk_id)
    n_snaps = await portfolio_repo.replace_snapshots(db, user.clerk_id, snaps)
    n_pos = await portfolio_repo.replace_positions(db, user.clerk_id, pos)
    return RebuildResult(snapshots_persisted=n_snaps, positions_persisted=n_pos)
