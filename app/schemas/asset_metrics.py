import uuid
from datetime import date as date_type
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AssetDailyMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_id: uuid.UUID
    date: date_type | None
    absolute_return: Decimal | None
    volatility: Decimal | None
    max_drawdown: Decimal | None


class AssetMonthlyMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_id: uuid.UUID
    date: date_type | None
    beta: Decimal | None