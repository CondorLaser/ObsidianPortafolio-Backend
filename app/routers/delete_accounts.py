import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import Profile
from app.repositories import account_repo
from app.repositories.portfolio_repo import reconstruct_user_portfolio
from app.routers.portfolio import post_daily_portfolio_metrics, post_monthly_portfolio_metrics
from scripts.warnings_module import warnings

router = APIRouter(prefix="/delete", tags=["accounts"])


@router.delete("/accounts/{account_id}")
async def delete_account(
    account_id: uuid.UUID,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await account_repo.delete_for_user(db, user.clerk_id, account_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Account not found")

    try:
        n_snapshots, n_positions = await reconstruct_user_portfolio(db, user)

        # Recompute portfolio metrics (daily + monthly)
        daily_metrics = await post_daily_portfolio_metrics(user, db)
        monthly_metrics = await post_monthly_portfolio_metrics(user, db)

        # Generate warnings
        warnings_found = await warnings(db, user.clerk_id, send_mail=True)

        return {
            "message": "Account deleted and portfolio rebuilt successfully",
            "deleted_account_id": account_id,
            "snapshots_rebuilt": n_snapshots,
            "positions_rebuilt": n_positions,
            "daily_metrics": daily_metrics,
            "monthly_metrics": monthly_metrics,
            "warnings_count": len(warnings_found),
            "warnings": warnings_found,
        }
    except Exception as e:
        return {
            "message": "Account deleted but rebuilding portfolio/metrics failed",
            "deleted_account_id": account_id,
            "error": str(e),
        }
