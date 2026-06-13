from http.client import HTTPException

from sqlalchemy import text
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import position_repo
from app.schemas.position import PositionDerived, PositionRead

from app.metrics.positions import calculate_position_daily_metrics

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("", response_model=list[PositionDerived])
async def list_positions(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Máx. registros retornar"),
):
    return await position_repo.list_for_user(db, user.clerk_id, skip=skip, limit=limit)


@router.post("/metrics/daily/{position_id}")
async def post_daily_positions_metrics(
    position_id: uuid.UUID,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text("""
            SELECT
                p.*,
                ap.close AS current_price
            FROM positions p
            JOIN accounts a
                ON a.id = p.account_id
            JOIN asset_prices ap
                ON ap.asset_id = p.asset_id
            WHERE p.id = :position_id
              AND a.user_id = :user_id
            ORDER BY ap.date DESC
            LIMIT 1
        """),
        {
            "position_id": position_id,
            "user_id": user.clerk_id,
        },
    )

    row = result.mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Position not found")

    current_price = row["current_price"]

    position = PositionRead(
        id=row["id"],
        account_id=row["account_id"],
        asset_id=row["asset_id"],
        quantity=row["quantity"],
        avg_cost=row["avg_cost"],
        realized_pnl=row["realized_pnl"],
        total_dividends=row["total_dividends"],
        total_fees=row["total_fees"],
        last_transaction_at=row["last_transaction_at"],
        updated_at=row["updated_at"],
    )

    metrics = calculate_position_daily_metrics(position, current_price)

    await db.execute(
        text("""
            INSERT INTO position_daily_metrics (id, position_id, date, unrealized_pnl, total_pnl)
            VALUES (:id, :position_id, :date, :unrealized_pnl, :total_pnl)
        """),
        {
            "id": str(uuid.uuid4()),
            "position_id": position_id,
            "date": metrics["date"],
            "unrealized_pnl": metrics["unrealized_pnl"],
            "total_pnl": metrics["total_pnl"],
        },
    )

    await db.commit()

    return metrics
    

@router.get("/metrics/daily/{position_id}")
async def get_daily_positions_metrics(
    position_id: uuid.UUID,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text("""
            SELECT pdm.*
            FROM position_daily_metrics pdm
            JOIN positions p
                ON p.id = pdm.position_id
            JOIN accounts a
                ON a.id = p.account_id
            WHERE pdm.position_id = :position_id
              AND a.user_id = :user_id
            ORDER BY pdm.date DESC
            LIMIT 1
        """),
        {
            "position_id": position_id,
            "user_id": user.clerk_id,
        },
    )

    metric = result.mappings().first()

    if not metric:
        raise HTTPException(
            status_code=404,
            detail="Position daily metrics not found"
        )

    return metric