import uuid
import json
from datetime import date as date_type

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import text

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import portfolio_repo
from app.repositories import portfolio_metrics_repo
from app.schemas.portfolio import PortfolioDashboard, PortfolioSummaryResponse, TrendPoint
from app.schemas.portfolio_metrics import PortfolioDailyMetricRead, PortfolioMonthlyMetricRead

from app.metrics.portfolio import calculate_portfolio_daily_metrics, calculate_portfolio_monthly_metrics

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
    n_pos = await portfolio_repo.replace_positions(db, user, pos)
    return RebuildResult(snapshots_persisted=n_snaps, positions_persisted=n_pos)


@router.get("/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_repo.get_portfolio_summary_data(db, user.clerk_id)

@router.get("/trend", response_model=list[TrendPoint])
async def get_portfolio_trend(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    trend_from: date_type | None = Query(None, description="Filtra desde esta fecha inclusive (YYYY-MM-DD)."),
    trend_to: date_type | None = Query(None, description="Filtra hasta esta fecha inclusive (YYYY-MM-DD)."),
):
    return await portfolio_repo.get_portfolio_trend_data(
        db, user.clerk_id, trend_from=trend_from, trend_to=trend_to
    )

# Para obtener positions asociados al portafolio total/usuario dejaré el GET /positions
# del router positions

@router.post("/metrics/daily")
async def post_daily_portfolio_metrics(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    print("posteadas daily!")

    result = await db.execute(
        text("""
            SELECT *
            FROM portfolio_snapshots
            WHERE user_id = :user_id
            ORDER BY date ASC
        """),
        {"user_id": user.clerk_id},
    )

    snapshots = result.mappings().all()
    metrics = calculate_portfolio_daily_metrics(snapshots)
    metric_id = str(uuid.uuid4())

    await db.execute(
        text("""
            INSERT INTO portfolio_daily_metrics (id, user_id, date, pnl, max_drawdown, volatility)
            VALUES (:id, :user_id, :date, :pnl, :max_drawdown, :volatility)
        """),
        {
            "id": metric_id,
            "user_id": user.clerk_id,
            "date": metrics["date"],
            "pnl": json.dumps(metrics["pnl"]),
            "max_drawdown": json.dumps(metrics["max_drawdown"]),
            "volatility": json.dumps(metrics["volatility"]),
        },
    )
    await db.commit()

    return metrics

@router.get("/metrics/daily", response_model=PortfolioDailyMetricRead)
async def get_latest_daily_metric(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    metric = await portfolio_metrics_repo.get_latest_daily_metric(db, user.clerk_id)
    if metric is None:
        raise HTTPException(status_code=404, detail="No daily metrics found for this portfolio")
    return metric

@router.get("/metrics/daily/all")
async def get_daily_portfolio_metrics(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    trend_from: date_type | None = Query(None), 
    trend_to: date_type | None = Query(None)
):
    query = """
        SELECT *
        FROM portfolio_daily_metrics
        WHERE user_id = :user_id
    """

    params = {"user_id": user.clerk_id}

    if trend_from:
        query += " AND date >= :trend_from"
        params["trend_from"] = trend_from

    if trend_to:
        query += " AND date <= :trend_to"
        params["trend_to"] = trend_to

    query += " ORDER BY date DESC"

    result = await db.execute(
        text(query),
        params,
    )

    return result.mappings().all()

@router.post("/metrics/monthly")
async def post_monthly_portfolio_metrics(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    print("posteadas monthly!")

    result = await db.execute(
        text("""
            SELECT *
            FROM portfolio_snapshots
            WHERE user_id = :user_id
            ORDER BY date ASC
        """),
        {"user_id": user.clerk_id},
    )

    snapshots = result.mappings().all()
    metrics = calculate_portfolio_monthly_metrics(snapshots)
    metric_id = str(uuid.uuid4())

    await db.execute(
        text("""
            INSERT INTO portfolio_monthly_metrics (id, user_id, date, twr, var)
            VALUES (:id, :user_id, :date, :twr, :var)
        """),
        {
            "id": metric_id,
            "user_id": user.clerk_id,
            "date": metrics["date"],
            "twr": json.dumps(metrics["twr"]),
            "var": json.dumps(metrics["var"]),
        },
    )
    await db.commit()

    return metrics

@router.get("/metrics/monthly", response_model=PortfolioMonthlyMetricRead)
async def get_latest_monthly_metric(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    metric = await portfolio_metrics_repo.get_latest_monthly_metric(db, user.clerk_id)
    if metric is None:
        raise HTTPException(status_code=404, detail="No monthly metrics found for this portfolio")
    return metric

@router.get("/metrics/monthly/all")
async def get_monthly_portfolio_metrics(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    trend_from: date_type | None = Query(None),
    trend_to: date_type | None = Query(None),
):
    query = """
        SELECT *
        FROM portfolio_monthly_metrics
        WHERE user_id = :user_id
    """

    params = {"user_id": user.clerk_id}

    if trend_from:
        query += " AND date >= :trend_from"
        params["trend_from"] = trend_from

    if trend_to:
        query += " AND date <= :trend_to"
        params["trend_to"] = trend_to

    query += " ORDER BY date DESC"

    result = await db.execute(
        text(query),
        params,
    )

    return result.mappings().all()
