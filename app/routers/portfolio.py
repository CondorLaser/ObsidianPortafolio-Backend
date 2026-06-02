import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

@router.get("/{portfolio_id}/metrics")
async def get_metrics(
    portfolio_id: uuid.UUID,
    _user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    daily_result = await db.execute(
        text("""
            SELECT *
            FROM portfolio_daily_metrics
            WHERE portfolio_id = :portfolio_id
            ORDER BY date DESC
        """),
        {"portfolio_id": str(portfolio_id)},
    )

    monthly_result = await db.execute(
        text("""
            SELECT *
            FROM portfolio_monthly_metrics
            WHERE portfolio_id = :portfolio_id
            ORDER BY date DESC
        """),
        {"portfolio_id": str(portfolio_id)},
    )

    return {
        "daily": [dict(row._mapping) for row in daily_result],
        "monthly": [dict(row._mapping) for row in monthly_result],
    }
