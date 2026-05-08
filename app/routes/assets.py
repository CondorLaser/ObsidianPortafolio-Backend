from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.db.database import get_db
from app.db.models import Asset
from app.schemas import (
    AssetResponse,
    AssetDetailResponse
)

router = APIRouter()


@router.get("/assets", response_model=list[AssetResponse])
def get_assets(
    symbol: str | None = None,
    kind: str | None = None,
    currency: str | None = None,
    search: str | None = Query(default=None),

    db: Session = Depends(get_db)
):
    query = db.query(Asset)

    if symbol:
        query = query.filter(Asset.symbol == symbol)

    if kind:
        query = query.filter(Asset.kind == kind)

    if currency:
        query = query.filter(Asset.currency == currency)

    if search:
        query = query.filter(
            or_(
                Asset.symbol.ilike(f"%{search}%"),
                Asset.name.ilike(f"%{search}%")
            )
        )

    assets = query.all()

    return assets


@router.get(
    "/assets/{asset_id}",
    response_model=AssetDetailResponse
)
def get_asset_by_id(
    asset_id: UUID,
    db: Session = Depends(get_db)
):

    asset = (
        db.query(Asset)
        .options(
            joinedload(Asset.prices),
            joinedload(Asset.dividends),
            joinedload(Asset.transactions)
        )
        .filter(Asset.id == asset_id)
        .first()
    )

    if not asset:
        raise HTTPException(
            status_code=404,
            detail="Asset not found"
        )

    return asset