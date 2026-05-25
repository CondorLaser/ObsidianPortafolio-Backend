import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.asset import AssetKind
from app.schemas.asset_price import AssetPriceRead


class AssetBase(BaseModel):
    symbol: str
    name: str
    kind: AssetKind
    currency: str = Field(default="USD", min_length=3, max_length=3)


class AssetCreate(AssetBase):
    pass


class AssetRead(AssetBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class AssetDetailRead(AssetRead):
    """Estilo Eduardo: detalle por id con prices embebidos."""

    prices: list[AssetPriceRead] = []
