import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.asset import AssetKind
from app.schemas.asset_price import AssetPriceRead


class AssetBase(BaseModel):
    """Para POST: schema mínimo de creación."""

    symbol: str
    name: str
    kind: AssetKind
    currency: str = Field(default="USD", min_length=3, max_length=3)


class AssetCreate(AssetBase):
    pass


class AssetRead(BaseModel):
    """1:1 con AssetsResponse de Eduardo (mismo orden de campos)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    symbol: str
    name: str
    kind: AssetKind
    currency: str
    created_at: datetime


class AssetDetailRead(AssetRead):
    """1:1 con AssetDetailResponse de Eduardo: metadata + prices ordenados DESC by date."""

    prices: list[AssetPriceRead] = []
