from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AssetPriceBase(BaseModel):
    date: date
    close: Decimal
    currency: str = Field(min_length=3, max_length=3)
    source: str | None = None


class AssetPriceCreate(AssetPriceBase):
    pass


class AssetPriceRead(AssetPriceBase):
    model_config = ConfigDict(from_attributes=True)
