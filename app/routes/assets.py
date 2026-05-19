from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import get_db
from app.schemas import AssetsResponse, AssetDetailResponse

router = APIRouter()


@router.get("/assets", response_model=list[AssetsResponse])
def get_assets(
    symbol: str | None = None,
    kind: str | None = None,
    currency: str | None = None,
    search: str | None = Query(default=None),

    db: Session = Depends(get_db)
):
    sql = """
        SELECT * FROM assets WHERE 1=1
    """

    params = {}

    if symbol:
        sql += " AND symbol = :symbol"
        params["symbol"] = symbol
    if kind:
        sql += " AND kind = :kind"
        params["kind"] = kind
    if currency:
        sql += " AND currency = :currency"
        params["currency"] = currency
    if search:
        sql += """
            AND (
                symbol ILIKE :search
                OR name ILIKE :search
            )
        """
        params["search"] = f"%{search}%"

    result = db.execute(text(sql), params)
    assets = result.mappings().all()

    return assets


@router.get(
    "/assets/{asset_id}",
    response_model=AssetDetailResponse
)
def get_asset_by_id(
    asset_id: UUID,
    db: Session = Depends(get_db)
):
    asset_result = db.execute(
        text("""
            SELECT * FROM assets WHERE id = :asset_id
        """),
        {"asset_id": str(asset_id)}
    )

    asset_row = asset_result.mappings().first()

    if not asset_row:
        raise HTTPException(
            status_code=404,
            detail="Asset not found"
        )
    
    asset = dict(asset_row)
    
    prices_result = db.execute(
        text("""
            SELECT *
            FROM asset_prices
            WHERE asset_id = :asset_id
            ORDER BY date DESC
        """),
        {"asset_id": str(asset_id)}
    )

    asset["prices"] = prices_result.mappings().all()

    return asset