import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


POSITIONS_SQL = text(
    """
    WITH agg AS (
        SELECT
            t.account_id,
            t.asset_id,
            SUM(CASE
                    WHEN t.kind = 'buy' THEN t.quantity
                    WHEN t.kind = 'sell' THEN -t.quantity
                    ELSE 0
                END) AS quantity,
            CASE
                WHEN SUM(CASE WHEN t.kind = 'buy' THEN t.quantity ELSE 0 END) > 0
                THEN SUM(CASE WHEN t.kind = 'buy' THEN t.quantity * t.price ELSE 0 END)
                     / SUM(CASE WHEN t.kind = 'buy' THEN t.quantity ELSE 0 END)
                ELSE NULL
            END AS avg_cost
        FROM "transaction" t
        JOIN account a ON a.id = t.account_id
        WHERE a.user_id = :user_id
        GROUP BY t.account_id, t.asset_id
    ),
    last_price AS (
        SELECT DISTINCT ON (asset_id) asset_id, close
        FROM asset_price
        ORDER BY asset_id, date DESC
    )
    SELECT
        agg.account_id,
        agg.asset_id,
        ast.symbol,
        ast.name,
        agg.quantity,
        agg.avg_cost,
        lp.close AS last_price,
        CASE WHEN lp.close IS NOT NULL THEN agg.quantity * lp.close ELSE NULL END
            AS market_value,
        CASE
            WHEN lp.close IS NOT NULL AND agg.avg_cost IS NOT NULL
            THEN agg.quantity * (lp.close - agg.avg_cost)
            ELSE NULL
        END AS unrealized_pnl
    FROM agg
    JOIN asset ast ON ast.id = agg.asset_id
    LEFT JOIN last_price lp ON lp.asset_id = agg.asset_id
    WHERE agg.quantity > 0
    ORDER BY ast.symbol;
    """
)


async def list_for_user(session: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    result = await session.execute(POSITIONS_SQL, {"user_id": user_id})
    return [dict(row) for row in result.mappings().all()]
