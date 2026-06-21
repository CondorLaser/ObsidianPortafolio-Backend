import uuid
from datetime import date as date_type
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

class PortfolioDailyMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    date: date_type | None
    pnl: dict | None
    max_drawdown: dict | None
    volatility: dict | None


class PortfolioMonthlyMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    date: date_type | None
    twr: dict | None
    var: dict | None