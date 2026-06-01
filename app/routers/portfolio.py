from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import portfolio_repo
from app.schemas.portfolio import PortfolioDashboard

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


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
