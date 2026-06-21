import uuid
from datetime import date as date_type

from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.position import PositionWrite
from app.metrics.positions import calculate_position_daily_metrics


async def create_daily_metrics(
    session: AsyncSession,
    clerk_id: str,
    position_id: uuid.UUID,
):
    """Calcula y crea una nueva métrica diaria para una posición."""
    result = await session.execute(
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
            "user_id": clerk_id,
        },
    )
    row = result.mappings().first()
    if not row:
        return None

    current_price = row["current_price"]
    position = PositionWrite(
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
    await session.execute(
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
    await session.commit()
    return metrics


async def list_daily_metrics(
    session: AsyncSession,
    clerk_id: str,
    position_id: uuid.UUID,
    trend_from: date_type | None = None,
    trend_to: date_type | None = None,
):
    """Lista métricas diarias de una posición con filtros opcionales de rango de fechas."""
    query = """
        SELECT pdm.*
        FROM position_daily_metrics pdm
        JOIN positions p
            ON p.id = pdm.position_id
        JOIN accounts a
            ON a.id = p.account_id
        WHERE pdm.position_id = :position_id
          AND a.user_id = :user_id
    """
    params = {
        "position_id": position_id,
        "user_id": clerk_id,
    }

    if trend_from:
        query += " AND pdm.date >= :trend_from"
        params["trend_from"] = trend_from
    if trend_to:
        query += " AND pdm.date <= :trend_to"
        params["trend_to"] = trend_to

    query += " ORDER BY pdm.date DESC"
    result = await session.execute(text(query), params)
    metrics = result.mappings().all()
    return list(metrics) if metrics else []


async def get_latest_daily_metric(
    session: AsyncSession,
    clerk_id: str,
    position_id: uuid.UUID,
):
    """Retorna la última (más reciente) métrica diaria de una posición."""
    result = await session.execute(
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
            "user_id": clerk_id,
        },
    )

    return result.mappings().first()