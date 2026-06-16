import uuid
from datetime import date as date_type
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

class PortfolioDailyMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    portfolio_id: uuid.UUID
    date: date_type | None
    pnl: Decimal | None
    max_drawdown: Decimal | None
    volatility: Decimal | None
    fx_decomposition: dict | None = None


class PortfolioMonthlyMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    portfolio_id: uuid.UUID
    date: date_type | None
    twr: Decimal | None
    dietz: Decimal | None
    var: Decimal | None
    accounts_correlation: Decimal | None = None